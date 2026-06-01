import os
import sys
import json
import pickle
import numpy as np
import pandas as pd
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import create_engine, text
from src.api.schemas import CustomerFull, ChurnRisk
import redis
import shap

router = APIRouter()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5433/customer_intelligence')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'models_saved')

def load_churn_model():
    with open(os.path.join(MODELS_DIR, 'churn_model.pkl'), 'rb') as f:
        model = pickle.load(f)
    with open(os.path.join(MODELS_DIR, 'churn_model_meta.json'), 'r') as f:
        meta = json.load(f)
    return model, meta

def get_risk_level(score: float) -> str:
    if score >= 0.65:
        return 'high'
    elif score >= 0.45:
        return 'medium'
    else:
        return 'low'

@router.get("/")
def list_customers(
    limit: int = Query(50, le=500),
    offset: int = Query(0),
    segment: str = Query(None),
    risk: str = Query(None)
):
    query = '''
        SELECT c.customer_id, c.country, c.first_purchase, c.last_purchase,
               c.total_orders, c.total_revenue,
               cf.churn_score, cf.clv_12m, cf.rfm_segment, cf.monetary
        FROM customers c
        LEFT JOIN customer_features cf ON c.customer_id = cf.customer_id
        WHERE 1=1
    '''
    params = {}
    if segment:
        query += " AND cf.rfm_segment = :segment"
        params['segment'] = segment
    if risk == 'high':
        query += " AND cf.churn_score >= 0.65"
    elif risk == 'medium':
        query += " AND cf.churn_score >= 0.45 AND cf.churn_score < 0.65"
    elif risk == 'low':
        query += " AND cf.churn_score < 0.45"

    query += " ORDER BY cf.monetary DESC NULLS LAST LIMIT :limit OFFSET :offset"
    params['limit'] = limit
    params['offset'] = offset

    with engine.connect() as conn:
        rows = conn.execute(text(query), params).fetchall()

    return [dict(row._mapping) for row in rows]

@router.get("/{customer_id}", response_model=CustomerFull)
def get_customer(customer_id: str):
    cached = redis_client.get(f'customer:{customer_id}:features')
    if cached:
        data = json.loads(cached)
        data['churn_risk_level'] = get_risk_level(data.get('churn_score') or 0.5)
        return data

    with engine.connect() as conn:
        row = conn.execute(text('''
            SELECT c.*, cf.recency_days, cf.frequency, cf.monetary,
                   cf.avg_order_value, cf.return_rate, cf.product_diversity,
                   cf.churn_score, cf.clv_12m, cf.rfm_segment
            FROM customers c
            LEFT JOIN customer_features cf ON c.customer_id = cf.customer_id
            WHERE c.customer_id = :cid
        '''), {'cid': customer_id}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

    data = dict(row._mapping)
    data['first_purchase'] = str(data.get('first_purchase', ''))
    data['last_purchase'] = str(data.get('last_purchase', ''))
    data['churn_risk_level'] = get_risk_level(data.get('churn_score') or 0.5)
    return data

@router.get("/{customer_id}/risk", response_model=ChurnRisk)
def get_customer_risk(customer_id: str):
    cached = redis_client.get(f'customer:{customer_id}:features')
    if not cached:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")

    features = json.loads(cached)
    churn_score = features.get('churn_score') or 0.5

    model, meta = load_churn_model()
    feature_cols = meta['feature_cols']

    segment_map = {
        'Champions': 8, 'Loyal Customers': 7, 'Potential Loyalists': 6,
        'Recent Customers': 5, 'Promising': 4, 'At Risk': 3,
        'Cannot Lose Them': 2, 'Hibernating': 1
    }
    monetary = features.get('monetary') or 0
    frequency = features.get('frequency') or 1

    row = {
        'frequency': features.get('frequency') or 0,
        'monetary': monetary,
        'avg_order_value': features.get('avg_order_value') or 0,
        'return_rate': features.get('return_rate') or 0,
        'product_diversity': features.get('product_diversity') or 0,
        'total_orders': features.get('total_orders') or 0,
        'total_revenue': features.get('total_revenue') or 0,
        'segment_score': segment_map.get(features.get('rfm_segment', ''), 1),
        'revenue_per_order': round(monetary / max(frequency, 1), 2),
        'log_monetary': float(np.log1p(monetary)),
        'log_frequency': float(np.log1p(frequency)),
        'high_value_flag': 1 if monetary > 2000 else 0
    }

    X = pd.DataFrame([row])[feature_cols]
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)[0]

    top_factors = sorted(
        [{'feature': col, 'shap_value': round(float(val), 4)}
         for col, val in zip(feature_cols, shap_values)],
        key=lambda x: abs(x['shap_value']),
        reverse=True
    )[:5]

    return {
        'customer_id': customer_id,
        'churn_score': round(churn_score, 4),
        'churn_risk_level': get_risk_level(churn_score),
        'top_factors': top_factors,
        'rfm_segment': features.get('rfm_segment'),
        'monetary': monetary,
        'clv_12m': features.get('clv_12m')
    }

@router.get("/{customer_id}/events")
def get_customer_events(customer_id: str, limit: int = 20):
    with engine.connect() as conn:
        rows = conn.execute(text('''
            SELECT event_type, product_id, session_id,
                   event_timestamp, metadata
            FROM events
            WHERE customer_id = :cid
            ORDER BY event_timestamp DESC
            LIMIT :limit
        '''), {'cid': customer_id, 'limit': limit}).fetchall()
    return [dict(row._mapping) for row in rows]