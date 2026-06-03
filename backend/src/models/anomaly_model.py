import os
import sys
import json
import pickle
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.utils.logger import get_logger

logger = get_logger('anomaly_model')

_db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5433/customer_intelligence')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
engine = create_engine(_db_url, pool_size=5, max_overflow=10, pool_pre_ping=True)

MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models_saved')
os.makedirs(MODELS_DIR, exist_ok=True)

def load_features():
    logger.info('Loading customer features...')
    query = '''
        SELECT
            cf.customer_id,
            cf.recency_days,
            cf.frequency,
            cf.monetary,
            cf.avg_order_value,
            cf.return_rate,
            cf.product_diversity,
            cf.churn_score,
            cf.clv_12m,
            cf.rfm_segment,
            c.total_revenue,
            c.total_orders
        FROM customer_features cf
        JOIN customers c ON cf.customer_id = c.customer_id
    '''
    df = pd.read_sql(query, engine)
    df['churn_score'] = df['churn_score'].fillna(0.5)
    df['clv_12m'] = df['clv_12m'].fillna(0)
    logger.info(f'Loaded features for {len(df):,} customers')
    return df

def compute_segment_metrics(df):
    logger.info('Computing segment-level metrics...')
    segment_metrics = df.groupby('rfm_segment').agg(
        customer_count=('customer_id', 'count'),
        avg_monetary=('monetary', 'mean'),
        avg_churn_score=('churn_score', 'mean'),
        avg_clv=('clv_12m', 'mean'),
        total_revenue=('total_revenue', 'sum'),
        avg_recency=('recency_days', 'mean'),
        avg_frequency=('frequency', 'mean')
    ).reset_index()

    segment_metrics['avg_monetary'] = segment_metrics['avg_monetary'].round(2)
    segment_metrics['avg_churn_score'] = segment_metrics['avg_churn_score'].round(4)
    segment_metrics['avg_clv'] = segment_metrics['avg_clv'].round(2)
    segment_metrics['total_revenue'] = segment_metrics['total_revenue'].round(2)
    segment_metrics['avg_recency'] = segment_metrics['avg_recency'].round(1)
    segment_metrics['avg_frequency'] = segment_metrics['avg_frequency'].round(2)

    logger.info('Segment metrics:')
    for _, row in segment_metrics.iterrows():
        logger.info(
            f'  {row["rfm_segment"]:<25} '
            f'customers: {row["customer_count"]:>5} | '
            f'avg monetary: GBP {row["avg_monetary"]:>9,.2f} | '
            f'avg churn: {row["avg_churn_score"]:.3f}'
        )
    return segment_metrics

def detect_customer_anomalies(df):
    logger.info('Running Isolation Forest on customer features...')

    feature_cols = [
        'recency_days', 'frequency', 'monetary',
        'avg_order_value', 'return_rate', 'product_diversity',
        'churn_score', 'total_orders'
    ]

    X = df[feature_cols].copy()
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    iso_forest = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42,
        n_jobs=-1
    )
    df['anomaly_score'] = iso_forest.fit_predict(X_scaled)
    df['anomaly_raw_score'] = iso_forest.score_samples(X_scaled)

    anomalies = df[df['anomaly_score'] == -1].copy()
    logger.info(f'Anomalous customers detected: {len(anomalies):,} ({len(anomalies)/len(df)*100:.1f}%)')

    anomalies_sorted = anomalies.nsmallest(10, 'anomaly_raw_score')[
        ['customer_id', 'rfm_segment', 'monetary', 'churn_score', 'return_rate', 'anomaly_raw_score']
    ]
    logger.info('Top 10 most anomalous customers:')
    for _, row in anomalies_sorted.iterrows():
        logger.info(
            f'  Customer {row["customer_id"]} | '
            f'segment: {row["rfm_segment"]:<20} | '
            f'monetary: GBP {row["monetary"]:>10,.2f} | '
            f'churn: {row["churn_score"]:.3f} | '
            f'return_rate: {row["return_rate"]:.3f}'
        )

    return df, iso_forest, scaler, anomalies

def generate_segment_alerts(segment_metrics, df):
    logger.info('Generating segment-level alerts...')
    alerts = []

    high_churn_segments = segment_metrics[segment_metrics['avg_churn_score'] > 0.6]
    for _, seg in high_churn_segments.iterrows():
        alerts.append({
            'alert_type': 'high_churn_risk_segment',
            'segment_name': seg['rfm_segment'],
            'description': f'Segment "{seg["rfm_segment"]}" has high avg churn score of {seg["avg_churn_score"]:.3f}',
            'severity': 'high',
            'metric_name': 'avg_churn_score',
            'metric_value': seg['avg_churn_score'],
            'baseline_value': 0.5,
            'deviation_pct': round((seg['avg_churn_score'] - 0.5) / 0.5 * 100, 2)
        })

    large_segments = segment_metrics[segment_metrics['customer_count'] > 500]
    for _, seg in large_segments.iterrows():
        alerts.append({
            'alert_type': 'large_segment_monitor',
            'segment_name': seg['rfm_segment'],
            'description': f'Segment "{seg["rfm_segment"]}" has {seg["customer_count"]} customers — monitor for drift',
            'severity': 'low',
            'metric_name': 'customer_count',
            'metric_value': seg['customer_count'],
            'baseline_value': segment_metrics['customer_count'].mean(),
            'deviation_pct': round(
                (seg['customer_count'] - segment_metrics['customer_count'].mean()) /
                segment_metrics['customer_count'].mean() * 100, 2
            )
        })

    high_value_churning = df[
        (df['monetary'] > df['monetary'].quantile(0.75)) &
        (df['churn_score'] > 0.6)
    ]
    if len(high_value_churning) > 0:
        alerts.append({
            'alert_type': 'high_value_customers_at_risk',
            'segment_name': 'ALL',
            'description': f'{len(high_value_churning)} high-value customers (top 25% revenue) have churn score > 0.6',
            'severity': 'high',
            'metric_name': 'high_value_churn_count',
            'metric_value': len(high_value_churning),
            'baseline_value': 0,
            'deviation_pct': 100.0
        })

    logger.info(f'Generated {len(alerts)} alerts')
    return alerts

def save_alerts(alerts):
    logger.info('Saving alerts to PostgreSQL...')
    with engine.begin() as conn:
        conn.execute(text('TRUNCATE TABLE alerts'))
        for alert in alerts:
            conn.execute(text('''
                INSERT INTO alerts (
                    alert_type, segment_name, description, severity,
                    metric_name, metric_value, baseline_value, deviation_pct
                ) VALUES (
                    :alert_type, :segment_name, :description, :severity,
                    :metric_name, :metric_value, :baseline_value, :deviation_pct
                )
            '''), alert)
    logger.info(f'Saved {len(alerts)} alerts to database')

def save_model(iso_forest, scaler):
    logger.info('Saving anomaly model...')
    with open(os.path.join(MODELS_DIR, 'anomaly_model.pkl'), 'wb') as f:
        pickle.dump({'model': iso_forest, 'scaler': scaler}, f)
    logger.info('Anomaly model saved')

def run():
    logger.info('=== Starting anomaly detection ===')
    df = load_features()
    segment_metrics = compute_segment_metrics(df)
    df, iso_forest, scaler, anomalies = detect_customer_anomalies(df)
    alerts = generate_segment_alerts(segment_metrics, df)
    save_alerts(alerts)
    save_model(iso_forest, scaler)
    logger.info('=== Anomaly detection complete ===')
    return df, anomalies, alerts

if __name__ == '__main__':
    df, anomalies, alerts = run()
    print(f'\nSummary:')
    print(f'  Total customers   : {len(df):,}')
    print(f'  Anomalies flagged : {len(anomalies):,}')
    print(f'  Alerts generated  : {len(alerts):,}')