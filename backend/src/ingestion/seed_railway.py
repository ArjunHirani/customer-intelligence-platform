import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.utils.logger import get_logger

logger = get_logger('seed_railway')

DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(
    DATABASE_URL,
    pool_size=1,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={'connect_timeout': 60}
)

DATA_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'data', 'raw', 'online_retail_II.csv'
)

def load_csv():
    logger.info('Reading CSV...')
    df = pd.read_csv(DATA_PATH, encoding='utf-8', on_bad_lines='skip', low_memory=False)
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]
    rename_map = {
        'invoice': 'invoice_no', 'stockcode': 'stock_code',
        'invoicedate': 'invoice_date', 'price': 'unit_price',
        'customerid': 'customer_id', 'customer_id': 'customer_id'
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    df = df.dropna(subset=['customer_id'])
    df['customer_id'] = df['customer_id'].astype(float).astype(int).astype(str)
    df = df[pd.to_numeric(df['unit_price'], errors='coerce') > 0]
    df = df[pd.to_numeric(df['quantity'], errors='coerce') > 0]
    df['quantity'] = df['quantity'].astype(int)
    df['unit_price'] = df['unit_price'].astype(float)
    df['invoice_no'] = df['invoice_no'].astype(str)
    df = df[~df['invoice_no'].str.startswith('C')]
    df['total_price'] = df['quantity'] * df['unit_price']
    df['invoice_date'] = pd.to_datetime(df['invoice_date'], utc=True)
    df['description'] = df['description'].fillna('').astype(str).str[:200]
    df['stock_code'] = df['stock_code'].astype(str).str[:20]
    df['country'] = df['country'].fillna('Unknown').astype(str).str[:60]
    df = df.drop_duplicates()
    logger.info(f'Clean rows: {len(df):,}')
    return df

def truncate_tables():
    logger.info('Truncating tables...')
    with engine.begin() as conn:
        conn.execute(text('TRUNCATE TABLE customer_features, alerts, segment_history, transactions, customers RESTART IDENTITY CASCADE'))
    logger.info('Tables truncated')

def insert_customers(df):
    logger.info('Inserting customers...')
    customers = df.groupby('customer_id').agg(
        country=('country', 'first'),
        first_purchase=('invoice_date', 'min'),
        last_purchase=('invoice_date', 'max'),
        total_orders=('invoice_no', 'nunique'),
        total_revenue=('total_price', 'sum')
    ).reset_index()
    customers['first_purchase'] = customers['first_purchase'].dt.date
    customers['last_purchase'] = customers['last_purchase'].dt.date
    customers['total_revenue'] = customers['total_revenue'].round(2)
    customers.to_sql('customers', engine, if_exists='append', index=False, method='multi', chunksize=500)
    logger.info(f'Inserted {len(customers):,} customers')

def insert_transactions(df):
    logger.info('Inserting transactions in small chunks...')
    cols = ['customer_id', 'invoice_no', 'stock_code', 'description',
            'quantity', 'unit_price', 'total_price', 'invoice_date', 'country']
    chunk_size = 5000
    total = len(df)
    inserted = 0
    for i in range(0, total, chunk_size):
        chunk = df[cols].iloc[i:i+chunk_size]
        chunk.to_sql('transactions', engine, if_exists='append', index=False, method='multi', chunksize=500)
        inserted += len(chunk)
        logger.info(f'  Progress: {inserted:,} / {total:,} ({inserted/total*100:.1f}%)')
    logger.info(f'All {inserted:,} transactions inserted')

def verify():
    with engine.connect() as conn:
        tx = conn.execute(text('SELECT COUNT(*) FROM transactions')).scalar()
        cx = conn.execute(text('SELECT COUNT(*) FROM customers')).scalar()
        logger.info(f'Transactions: {tx:,}')
        logger.info(f'Customers: {cx:,}')

if __name__ == '__main__':
    logger.info('=== Railway seeding started ===')
    df = load_csv()
    truncate_tables()
    insert_customers(df)
    insert_transactions(df)
    verify()
    logger.info('=== Railway seeding complete ===')