import os
import sys
import json
import pickle
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    roc_auc_score, classification_report,
    confusion_matrix, precision_recall_curve
)
from xgboost import XGBClassifier
import shap

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.utils.logger import get_logger

logger = get_logger('churn_model')

_db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5433/customer_intelligence')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
engine = create_engine(_db_url, pool_size=5, max_overflow=10, pool_pre_ping=True)

MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models_saved')
os.makedirs(MODELS_DIR, exist_ok=True)

CHURN_DAYS_THRESHOLD = 90

def load_features():
    logger.info('Loading features from PostgreSQL...')
    query = '''
        SELECT
            cf.customer_id,
            cf.recency_days,
            cf.frequency,
            cf.monetary,
            cf.avg_order_value,
            cf.return_rate,
            cf.product_diversity,
            cf.rfm_segment,
            c.total_orders,
            c.total_revenue,
            c.first_purchase,
            c.last_purchase
        FROM customer_features cf
        JOIN customers c ON cf.customer_id = c.customer_id
    '''
    df = pd.read_sql(query, engine)
    logger.info(f'Loaded features for {len(df):,} customers')
    return df

def create_churn_label(df):
    logger.info(f'Creating churn labels (threshold: {CHURN_DAYS_THRESHOLD} days)...')
    df['churned'] = (df['recency_days'] > CHURN_DAYS_THRESHOLD).astype(int)
    churn_rate = df['churned'].mean()
    logger.info(f'Churn rate: {churn_rate:.1%} ({df["churned"].sum():,} churned / {len(df):,} total)')
    return df

def engineer_features(df):
    logger.info('Engineering model features...')

    segment_map = {
        'Champions': 8,
        'Loyal Customers': 7,
        'Potential Loyalists': 6,
        'Recent Customers': 5,
        'Promising': 4,
        'At Risk': 3,
        'Cannot Lose Them': 2,
        'Hibernating': 1
    }
    df['segment_score'] = df['rfm_segment'].map(segment_map).fillna(1)

    df['revenue_per_order'] = (df['monetary'] / df['frequency'].clip(lower=1)).round(2)
    df['log_monetary'] = np.log1p(df['monetary'])
    df['log_frequency'] = np.log1p(df['frequency'])
    df['recency_x_frequency'] = df['recency_days'] * df['frequency']
    df['high_value_flag'] = (df['monetary'] > df['monetary'].quantile(0.75)).astype(int)

    feature_cols = [
        'frequency', 'monetary', 'avg_order_value',
        'return_rate', 'product_diversity', 'total_orders', 'total_revenue',
        'segment_score', 'revenue_per_order', 'log_monetary', 'log_frequency',
        'high_value_flag'
    ]

    logger.info(f'Feature count: {len(feature_cols)}')
    return df, feature_cols

def train_model(df, feature_cols):
    logger.info('Training XGBoost churn model...')

    X = df[feature_cols]
    y = df['churned']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    logger.info(f'Train: {len(X_train):,} | Test: {len(X_test):,}')

    scale_pos_weight = (y_train == 0).sum() / (y_train == 1).sum()

    model = XGBClassifier(
        n_estimators=300,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        random_state=42,
        eval_metric='auc',
        early_stopping_rounds=20,
        verbosity=0
    )

    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        verbose=False
    )

    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= 0.5).astype(int)

    auc = roc_auc_score(y_test, y_pred_proba)
    logger.info(f'AUC-ROC: {auc:.4f}')
    logger.info(f'Classification report:\n{classification_report(y_test, y_pred)}')

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(
        XGBClassifier(
            n_estimators=300, max_depth=5, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            scale_pos_weight=scale_pos_weight,
            random_state=42, verbosity=0
        ),
        X, y, cv=cv, scoring='roc_auc'
    )
    logger.info(f'Cross-val AUC: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}')

    return model, X_test, y_test, auc, feature_cols

def compute_shap_values(model, X_train_sample):
    logger.info('Computing SHAP values...')
    explainer = shap.TreeExplainer(model)
    sample = X_train_sample.head(500)
    shap_values = explainer.shap_values(sample)
    logger.info('SHAP values computed for 500 sample customers')
    return explainer, shap_values

def save_model(model, feature_cols, auc):
    logger.info('Saving model to disk...')

    model_path = os.path.join(MODELS_DIR, 'churn_model.pkl')
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)

    meta = {
        'feature_cols': feature_cols,
        'auc': round(auc, 4),
        'churn_threshold_days': CHURN_DAYS_THRESHOLD,
        'model_type': 'XGBClassifier'
    }
    meta_path = os.path.join(MODELS_DIR, 'churn_model_meta.json')
    with open(meta_path, 'w') as f:
        json.dump(meta, f, indent=2)

    logger.info(f'Model saved to {model_path}')
    logger.info(f'Metadata saved to {meta_path}')

def update_churn_scores(model, df, feature_cols):
    logger.info('Updating churn scores in PostgreSQL...')

    X = df[feature_cols]
    df['churn_score'] = model.predict_proba(X)[:, 1].round(4)

    with engine.begin() as conn:
        for _, row in df.iterrows():
            conn.execute(text('''
                UPDATE customer_features
                SET churn_score = :score
                WHERE customer_id = :cid
            '''), {'score': float(row['churn_score']), 'cid': row['customer_id']})

    logger.info(f'Updated churn scores for {len(df):,} customers')

    high_risk = (df['churn_score'] >= 0.7).sum()
    medium_risk = ((df['churn_score'] >= 0.4) & (df['churn_score'] < 0.7)).sum()
    low_risk = (df['churn_score'] < 0.4).sum()
    logger.info(f'Risk distribution:')
    logger.info(f'  High risk   (>=0.7) : {high_risk:,} customers')
    logger.info(f'  Medium risk (0.4-0.7): {medium_risk:,} customers')
    logger.info(f'  Low risk    (<0.4)  : {low_risk:,} customers')

def run():
    logger.info('=== Starting churn model training ===')
    df = load_features()
    df = create_churn_label(df)
    df, feature_cols = engineer_features(df)
    model, X_test, y_test, auc, feature_cols = train_model(df, feature_cols)
    explainer, shap_values = compute_shap_values(model, df[feature_cols])
    save_model(model, feature_cols, auc)
    update_churn_scores(model, df, feature_cols)
    logger.info(f'=== Churn model complete | AUC: {auc:.4f} ===')
    return model, explainer, feature_cols

if __name__ == '__main__':
    model, explainer, feature_cols = run()