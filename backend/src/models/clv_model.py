import os
import sys
import json
import dill as pickle
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from lifetimes import BetaGeoFitter, GammaGammaFitter
from lifetimes.utils import summary_data_from_transaction_data

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.utils.logger import get_logger

logger = get_logger('clv_model')

_db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5433/customer_intelligence')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
engine = create_engine(_db_url, pool_size=5, max_overflow=10, pool_pre_ping=True)

MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'models_saved')
os.makedirs(MODELS_DIR, exist_ok=True)

def load_transactions():
    logger.info('Loading transactions...')
    query = '''
        SELECT customer_id, invoice_date, total_price, invoice_no
        FROM transactions
        WHERE total_price > 0
    '''
    df = pd.read_sql(query, engine)
    df['invoice_date'] = pd.to_datetime(df['invoice_date'], utc=True)
    df['invoice_date'] = df['invoice_date'].dt.tz_localize(None)
    logger.info(f'Loaded {len(df):,} transactions')
    return df

def build_rfm_summary(df):
    logger.info('Building RFM summary for BG/NBD model...')
    snapshot_date = df['invoice_date'].max() + pd.Timedelta(days=1)

    summary = summary_data_from_transaction_data(
        df,
        customer_id_col='customer_id',
        datetime_col='invoice_date',
        monetary_value_col='total_price',
        observation_period_end=snapshot_date,
        freq='D'
    )

    summary = summary[summary['frequency'] > 0]
    summary = summary[summary['monetary_value'] > 0]

    logger.info(f'RFM summary built for {len(summary):,} customers')
    logger.info(f'Avg frequency : {summary["frequency"].mean():.2f}')
    logger.info(f'Avg recency   : {summary["recency"].mean():.2f} days')
    logger.info(f'Avg T         : {summary["T"].mean():.2f} days')
    return summary

def train_bgnbd(summary):
    logger.info('Training BG/NBD model (purchase frequency)...')
    bgf = BetaGeoFitter(penalizer_coef=0.01)
    bgf.fit(
        summary['frequency'],
        summary['recency'],
        summary['T']
    )
    logger.info('BG/NBD model trained successfully')
    logger.info(f'  Model params: {bgf.params_}')
    return bgf

def train_gamma_gamma(summary):
    logger.info('Training Gamma-Gamma model (monetary value)...')
    ggf = GammaGammaFitter(penalizer_coef=0.01)
    ggf.fit(
        summary['frequency'],
        summary['monetary_value']
    )
    logger.info('Gamma-Gamma model trained successfully')
    logger.info(f'  Model params: {ggf.params_}')
    return ggf

def compute_clv(bgf, ggf, summary):
    logger.info('Computing 12-month CLV predictions...')

    summary['predicted_purchases_12m'] = bgf.conditional_expected_number_of_purchases_up_to_time(
        365,
        summary['frequency'],
        summary['recency'],
        summary['T']
    ).round(2)

    summary['expected_avg_value'] = ggf.conditional_expected_average_profit(
        summary['frequency'],
        summary['monetary_value']
    ).round(2)

    clv_12m = ggf.customer_lifetime_value(
        bgf,
        summary['frequency'],
        summary['recency'],
        summary['T'],
        summary['monetary_value'],
        time=12,
        freq='D',
        discount_rate=0.01
    ).round(2)

    summary['clv_12m'] = clv_12m

    logger.info(f'CLV computed for {len(summary):,} customers')
    logger.info(f'Avg 12m CLV   : GBP {summary["clv_12m"].mean():.2f}')
    logger.info(f'Median 12m CLV: GBP {summary["clv_12m"].median():.2f}')
    logger.info(f'Max 12m CLV   : GBP {summary["clv_12m"].max():.2f}')

    top5 = summary.nlargest(5, 'clv_12m')[['clv_12m', 'frequency', 'monetary_value']]
    logger.info('Top 5 customers by predicted CLV:')
    for cid, row in top5.iterrows():
        logger.info(f'  Customer {cid} → CLV: GBP {row["clv_12m"]:,.2f} | freq: {row["frequency"]} | avg value: GBP {row["monetary_value"]:.2f}')

    return summary

def save_models(bgf, ggf):
    logger.info('Saving CLV models to disk...')
    with open(os.path.join(MODELS_DIR, 'bgnbd_model.pkl'), 'wb') as f:
        pickle.dump(bgf, f)
    with open(os.path.join(MODELS_DIR, 'gamma_gamma_model.pkl'), 'wb') as f:
        pickle.dump(ggf, f)
    logger.info('CLV models saved')

def update_clv_scores(summary):
    logger.info('Updating CLV scores in PostgreSQL...')
    updated = 0
    with engine.begin() as conn:
        for customer_id, row in summary.iterrows():
            conn.execute(text('''
                UPDATE customer_features
                SET clv_12m = :clv
                WHERE customer_id = :cid
            '''), {
                'clv': float(row['clv_12m']),
                'cid': str(customer_id)
            })
            updated += 1
    logger.info(f'Updated CLV for {updated:,} customers')

def run():
    logger.info('=== Starting CLV model training ===')
    df = load_transactions()
    summary = build_rfm_summary(df)
    bgf = train_bgnbd(summary)
    ggf = train_gamma_gamma(summary)
    summary = compute_clv(bgf, ggf, summary)
    save_models(bgf, ggf)
    update_clv_scores(summary)
    logger.info('=== CLV model complete ===')
    return bgf, ggf, summary

if __name__ == '__main__':
    bgf, ggf, summary = run()