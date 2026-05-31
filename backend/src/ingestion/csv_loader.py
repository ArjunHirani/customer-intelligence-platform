import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.utils.logger import get_logger

logger = get_logger('csv_loader')

engine = create_engine(
    'postgresql://postgres:password@localhost:5433/customer_intelligence',
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True
)

DATA_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', 'data', 'raw', 'online_retail_II.csv'
)

def load_csv():
    logger.info('Reading CSV file...')
    df = pd.read_csv(
        DATA_PATH,
        encoding='utf-8',
        on_bad_lines='skip',
        low_memory=False
    )
    logger.info(f'Raw rows loaded: {len(df):,}')
    logger.info(f'Columns found: {list(df.columns)}')
    return df

def clean_data(df):
    logger.info('Cleaning data...')

    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

    rename_map = {
        'invoice': 'invoice_no',
        'stockcode': 'stock_code',
        'invoicedate': 'invoice_date',
        'unitprice': 'unit_price',
        'price': 'unit_price',
        'customerid': 'customer_id',
        'customer_id': 'customer_id'
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    df = df.dropna(subset=['customer_id'])
    df['customer_id'] = df['customer_id'].astype(float).astype(int).astype(str)

    df = df[pd.to_numeric(df['unit_price'], errors='coerce') > 0]
    df = df[pd.to_numeric(df['quantity'], errors='coerce') > 0]
    df['quantity'] = df['quantity'].astype(int)
    df['unit_price'] = df['unit_price'].astype(float)

    df['invoice_no'] = df['invoice_no'].astype(str)
    df['is_cancelled'] = df['invoice_no'].str.startswith('C')
    df = df[~df['is_cancelled']]

    df['total_price'] = df['quantity'] * df['unit_price']
    df['invoice_date'] = pd.to_datetime(df['invoice_date'], utc=True)
    df['description'] = df['description'].fillna('').astype(str).str[:200]
    df['stock_code'] = df['stock_code'].astype(str).str[:20]
    df['country'] = df['country'].fillna('Unknown').astype(str).str[:60]

    df = df.drop_duplicates()

    logger.info(f'Clean rows remaining: {len(df):,}')
    return df

def build_customers(df):
    logger.info('Building customers table...')
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
    logger.info(f'Unique customers: {len(customers):,}')
    return customers

def insert_customers(customers):
    logger.info('Inserting customers into PostgreSQL...')
    with engine.begin() as conn:
        conn.execute(text('''
            TRUNCATE TABLE customer_features, alerts, 
            segment_history, transactions, customers 
            RESTART IDENTITY CASCADE
        '''))
    customers.to_sql(
        'customers', engine,
        if_exists='append', index=False,
        method='multi', chunksize=1000
    )
    logger.info(f'Inserted {len(customers):,} customers')

def insert_transactions(df):
    logger.info('Inserting transactions (this takes 1-2 minutes)...')
    cols = ['customer_id', 'invoice_no', 'stock_code', 'description',
            'quantity', 'unit_price', 'total_price', 'invoice_date', 'country']
    df[cols].to_sql(
        'transactions', engine,
        if_exists='append', index=False,
        method='multi', chunksize=2000
    )
    logger.info(f'Inserted {len(df):,} transactions')

def verify_load():
    logger.info('Verifying load...')
    with engine.connect() as conn:
        tx_count  = conn.execute(text('SELECT COUNT(*) FROM transactions')).scalar()
        cx_count  = conn.execute(text('SELECT COUNT(*) FROM customers')).scalar()
        rev       = conn.execute(text('SELECT ROUND(SUM(total_price)::numeric, 2) FROM transactions')).scalar()
        top_cx    = conn.execute(text('''
            SELECT customer_id, ROUND(total_revenue::numeric, 2)
            FROM customers
            ORDER BY total_revenue DESC
            LIMIT 3
        ''')).fetchall()
    logger.info(f'Transactions : {tx_count:,}')
    logger.info(f'Customers    : {cx_count:,}')
    logger.info(f'Total revenue: GBP {rev:,}')
    logger.info('Top 3 customers by revenue:')
    for row in top_cx:
        logger.info(f'  Customer {row[0]} → GBP {row[1]:,}')

def run():
    logger.info('=== Starting data load ===')
    df = load_csv()
    df = clean_data(df)
    customers = build_customers(df)
    insert_customers(customers)
    insert_transactions(df)
    verify_load()
    logger.info('=== Data load complete ===')

if __name__ == '__main__':
    run()