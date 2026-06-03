import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.utils.logger import get_logger

logger = get_logger('rfm')

_db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5433/customer_intelligence')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
engine = create_engine(_db_url, pool_size=5, max_overflow=10, pool_pre_ping=True)
def load_transactions():
    logger.info('Loading transactions from PostgreSQL...')
    query = '''
        SELECT customer_id, invoice_no, total_price,
               invoice_date, stock_code, quantity, unit_price
        FROM transactions
        WHERE total_price > 0
    '''
    df = pd.read_sql(query, engine)
    df['invoice_date'] = pd.to_datetime(df['invoice_date'], utc=True)
    logger.info(f'Loaded {len(df):,} transactions for {df.customer_id.nunique():,} customers')
    return df

def compute_rfm(df):
    logger.info('Computing RFM features...')
    snapshot_date = df['invoice_date'].max() + pd.Timedelta(days=1)
    logger.info(f'Snapshot date: {snapshot_date.date()}')

    rfm = df.groupby('customer_id').agg(
        recency_days=('invoice_date', lambda x: (snapshot_date - x.max()).days),
        frequency=('invoice_no', 'nunique'),
        monetary=('total_price', 'sum'),
        product_diversity=('stock_code', 'nunique'),
        total_items=('quantity', 'sum')
    ).reset_index()

    rfm['monetary'] = rfm['monetary'].round(2)
    rfm['avg_order_value'] = (rfm['monetary'] / rfm['frequency']).round(2)
    logger.info(f'RFM computed for {len(rfm):,} customers')
    return rfm

def compute_return_rate(df):
    logger.info('Computing return rates...')
    query = '''
        SELECT customer_id, COUNT(*) as cancelled_count
        FROM transactions
        WHERE is_cancelled = TRUE
        GROUP BY customer_id
    '''
    cancelled = pd.read_sql(query, engine)
    purchase_counts = df.groupby('customer_id')['invoice_no'].nunique().reset_index()
    purchase_counts.columns = ['customer_id', 'purchase_count']
    merged = purchase_counts.merge(cancelled, on='customer_id', how='left')
    merged['cancelled_count'] = merged['cancelled_count'].fillna(0)
    merged['return_rate'] = (merged['cancelled_count'] / merged['purchase_count']).round(4)
    return merged[['customer_id', 'return_rate']]

def assign_rfm_segment(rfm):
    logger.info('Assigning RFM segments...')
    rfm['r_score'] = pd.qcut(rfm['recency_days'], q=4, labels=[4, 3, 2, 1]).astype(int)
    rfm['f_score'] = pd.qcut(rfm['frequency'].rank(method='first'), q=4, labels=[1, 2, 3, 4]).astype(int)
    rfm['m_score'] = pd.qcut(rfm['monetary'].rank(method='first'), q=4, labels=[1, 2, 3, 4]).astype(int)

    def get_segment(row):
        r, f, m = row['r_score'], row['f_score'], row['m_score']
        if r >= 4 and f >= 4 and m >= 4:
            return 'Champions'
        elif r >= 3 and f >= 3 and m >= 3:
            return 'Loyal Customers'
        elif r >= 4 and f <= 2:
            return 'Recent Customers'
        elif r >= 3 and f >= 2 and m >= 2:
            return 'Potential Loyalists'
        elif r >= 2 and f >= 3 and m >= 3:
            return 'At Risk'
        elif r <= 1 and f >= 4 and m >= 4:
            return 'Cannot Lose Them'
        elif r >= 2 and f <= 2 and m <= 2:
            return 'Promising'
        else:
            return 'Hibernating'

    rfm['rfm_segment'] = rfm.apply(get_segment, axis=1)

    segment_counts = rfm['rfm_segment'].value_counts()
    logger.info('Segment distribution:')
    for seg, count in segment_counts.items():
        logger.info(f'  {seg:<25} {count:>6,} customers')

    return rfm

def save_features(rfm):
    logger.info('Saving features to customer_features table...')
    with engine.begin() as conn:
        conn.execute(text('TRUNCATE TABLE customer_features'))

    insert_df = rfm[[
        'customer_id', 'recency_days', 'frequency', 'monetary',
        'avg_order_value', 'return_rate', 'product_diversity', 'rfm_segment'
    ]].copy()
    insert_df['churn_score'] = None
    insert_df['clv_12m'] = None

    insert_df.to_sql(
        'customer_features', engine,
        if_exists='append', index=False,
        method='multi', chunksize=1000
    )
    logger.info(f'Saved features for {len(insert_df):,} customers')

def run():
    logger.info('=== Starting feature engineering ===')
    df = load_transactions()
    rfm = compute_rfm(df)
    return_rates = compute_return_rate(df)
    rfm = rfm.merge(return_rates, on='customer_id', how='left')
    rfm['return_rate'] = rfm['return_rate'].fillna(0)
    rfm = assign_rfm_segment(rfm)
    save_features(rfm)
    logger.info('=== Feature engineering complete ===')
    return rfm

if __name__ == '__main__':
    rfm = run()
    print('\nSample output:')
    print(rfm[['customer_id', 'recency_days', 'frequency', 'monetary', 'rfm_segment']].head(10).to_string(index=False))