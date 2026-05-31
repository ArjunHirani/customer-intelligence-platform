import os
import sys
import json
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.utils.logger import get_logger

import redis

logger = get_logger('feature_store')

engine = create_engine(
    'postgresql://postgres:password@localhost:5433/customer_intelligence',
    pool_pre_ping=True
)

redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

FEATURE_TTL_SECONDS = 86400  # 24 hours

def load_all_features():
    logger.info('Loading RFM features from PostgreSQL...')
    rfm_query = '''
        SELECT customer_id, recency_days, frequency, monetary,
               avg_order_value, return_rate, product_diversity,
               churn_score, clv_12m, rfm_segment, computed_at
        FROM customer_features
    '''
    rfm_df = pd.read_sql(rfm_query, engine)
    logger.info(f'Loaded RFM features for {len(rfm_df):,} customers')
    return rfm_df

def load_customer_metadata():
    logger.info('Loading customer metadata...')
    query = '''
        SELECT customer_id, country, first_purchase,
               last_purchase, total_orders, total_revenue
        FROM customers
    '''
    df = pd.read_sql(query, engine)
    df['first_purchase'] = df['first_purchase'].astype(str)
    df['last_purchase'] = df['last_purchase'].astype(str)
    return df

def write_to_redis(rfm_df, meta_df):
    logger.info('Writing features to Redis...')

    merged = rfm_df.merge(meta_df, on='customer_id', how='left')

    success_count = 0
    error_count = 0

    pipe = redis_client.pipeline()

    for _, row in merged.iterrows():
        customer_id = row['customer_id']
        key = f'customer:{customer_id}:features'

        feature_dict = {}
        for col, val in row.items():
            if pd.isna(val):
                feature_dict[col] = None
            elif hasattr(val, 'item'):
                feature_dict[col] = val.item()
            else:
                feature_dict[col] = val

        try:
            pipe.setex(key, FEATURE_TTL_SECONDS, json.dumps(feature_dict, default=str))
            success_count += 1
        except Exception as e:
            error_count += 1
            logger.warning(f'Failed to queue customer {customer_id}: {e}')

        if success_count % 1000 == 0 and success_count > 0:
            pipe.execute()
            pipe = redis_client.pipeline()
            logger.info(f'  Written {success_count:,} customers to Redis...')

    pipe.execute()

    logger.info(f'Redis write complete — success: {success_count:,}, errors: {error_count}')

def verify_redis(sample_ids):
    logger.info('Verifying Redis entries...')
    for customer_id in sample_ids:
        key = f'customer:{customer_id}:features'
        data = redis_client.get(key)
        if data:
            parsed = json.loads(data)
            logger.info(
                f'  Customer {customer_id} → segment: {parsed.get("rfm_segment")} | '
                f'monetary: {parsed.get("monetary")} | '
                f'recency: {parsed.get("recency_days")}d'
            )
        else:
            logger.warning(f'  Customer {customer_id} → NOT FOUND in Redis')

def get_customer_features(customer_id: str):
    key = f'customer:{customer_id}:features'
    data = redis_client.get(key)
    if data:
        return json.loads(data)
    return None

def run():
    logger.info('=== Starting feature store population ===')

    redis_client.ping()
    logger.info('Redis connection verified')

    rfm_df = load_all_features()
    meta_df = load_customer_metadata()
    write_to_redis(rfm_df, meta_df)

    total_keys = redis_client.dbsize()
    logger.info(f'Total keys in Redis: {total_keys:,}')

    sample_ids = ['12347', '18102', '14646']
    verify_redis(sample_ids)

    logger.info('=== Feature store population complete ===')

if __name__ == '__main__':
    run()