import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.utils.logger import get_logger

logger = get_logger('behavioral')

engine = create_engine(
    'postgresql://postgres:password@localhost:5433/customer_intelligence',
    pool_pre_ping=True
)

def load_data():
    logger.info('Loading transaction data...')
    query = '''
        SELECT customer_id, invoice_no, stock_code, description,
               quantity, unit_price, total_price, invoice_date, country
        FROM transactions
        WHERE total_price > 0
    '''
    df = pd.read_sql(query, engine)
    df['invoice_date'] = pd.to_datetime(df['invoice_date'], utc=True)
    logger.info(f'Loaded {len(df):,} rows for {df.customer_id.nunique():,} customers')
    return df

def compute_purchase_patterns(df):
    logger.info('Computing purchase patterns...')
    df['hour'] = df['invoice_date'].dt.hour
    df['day_of_week'] = df['invoice_date'].dt.dayofweek
    df['month'] = df['invoice_date'].dt.month

    patterns = df.groupby('customer_id').agg(
        preferred_hour=('hour', lambda x: int(x.mode()[0])),
        preferred_day=('day_of_week', lambda x: int(x.mode()[0])),
        weekend_purchase_rate=('day_of_week', lambda x: round(float((x >= 5).mean()), 4)),
        unique_months_active=('month', 'nunique'),
    ).reset_index()
    return patterns

def compute_basket_metrics(df):
    logger.info('Computing basket metrics...')
    basket = df.groupby(['customer_id', 'invoice_no']).agg(
        basket_value=('total_price', 'sum'),
        basket_size=('quantity', 'sum'),
        unique_items=('stock_code', 'nunique')
    ).reset_index()

    basket_agg = basket.groupby('customer_id').agg(
        avg_basket_value=('basket_value', 'mean'),
        max_basket_value=('basket_value', 'max'),
        avg_basket_size=('basket_size', 'mean'),
        avg_unique_items=('unique_items', 'mean')
    ).reset_index()

    basket_agg['avg_basket_value'] = basket_agg['avg_basket_value'].round(2)
    basket_agg['max_basket_value'] = basket_agg['max_basket_value'].round(2)
    basket_agg['avg_basket_size'] = basket_agg['avg_basket_size'].round(2)
    basket_agg['avg_unique_items'] = basket_agg['avg_unique_items'].round(2)
    return basket_agg

def compute_spend_trend(df):
    logger.info('Computing spend trends...')
    snapshot_date = df['invoice_date'].max()
    cutoff_90d = snapshot_date - pd.Timedelta(days=90)
    cutoff_180d = snapshot_date - pd.Timedelta(days=180)

    recent_90 = df[df['invoice_date'] >= cutoff_90d].groupby('customer_id')['total_price'].sum()
    prev_90 = df[
        (df['invoice_date'] >= cutoff_180d) & (df['invoice_date'] < cutoff_90d)
    ].groupby('customer_id')['total_price'].sum()

    trend = pd.DataFrame({'customer_id': recent_90.index, 'spend_last_90d': recent_90.values})
    trend = trend.merge(
        pd.DataFrame({'customer_id': prev_90.index, 'spend_prev_90d': prev_90.values}),
        on='customer_id', how='left'
    )
    trend['spend_prev_90d'] = trend['spend_prev_90d'].fillna(0)
    trend['spend_trend'] = trend.apply(
        lambda row: (
            'growing' if row['spend_last_90d'] > row['spend_prev_90d'] * 1.1
            else 'declining' if row['spend_last_90d'] < row['spend_prev_90d'] * 0.9
            else 'stable'
        ), axis=1
    )
    trend['spend_last_90d'] = trend['spend_last_90d'].round(2)
    trend['spend_prev_90d'] = trend['spend_prev_90d'].round(2)
    return trend

def compute_top_category(df):
    logger.info('Computing top product per customer...')
    top_cat = df.groupby(['customer_id', 'description'])['total_price'].sum().reset_index()
    top_cat = top_cat.loc[top_cat.groupby('customer_id')['total_price'].idxmax()]
    top_cat = top_cat.rename(columns={'description': 'top_product'})
    top_cat['top_product'] = top_cat['top_product'].str[:100]
    return top_cat[['customer_id', 'top_product']]

def run():
    logger.info('=== Starting behavioral feature engineering ===')
    df = load_data()
    patterns = compute_purchase_patterns(df)
    basket = compute_basket_metrics(df)
    trend = compute_spend_trend(df)
    top_cat = compute_top_category(df)

    merged = patterns.merge(basket, on='customer_id', how='left')
    merged = merged.merge(trend, on='customer_id', how='left')
    merged = merged.merge(top_cat, on='customer_id', how='left')
    merged['spend_last_90d'] = merged['spend_last_90d'].fillna(0)
    merged['spend_prev_90d'] = merged['spend_prev_90d'].fillna(0)
    merged['spend_trend'] = merged['spend_trend'].fillna('stable')

    logger.info(f'Behavioral features ready for {len(merged):,} customers')
    logger.info('Spend trend distribution:')
    for val, count in merged['spend_trend'].value_counts().items():
        logger.info(f'  {val:<12} {count:>6,} customers')

    logger.info('=== Behavioral feature engineering complete ===')
    return merged

if __name__ == '__main__':
    behavioral = run()
    print('\nSample output:')
    print(behavioral[[
        'customer_id', 'avg_basket_value',
        'spend_trend', 'unique_months_active', 'weekend_purchase_rate'
    ]].head(10).to_string(index=False))