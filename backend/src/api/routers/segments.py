import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from fastapi import APIRouter, HTTPException
from sqlalchemy import create_engine, text

router = APIRouter()

engine = create_engine(
    'postgresql://postgres:password@localhost:5433/customer_intelligence',
    pool_pre_ping=True
)

@router.get("/")
def get_all_segments():
    query = '''
        SELECT
            rfm_segment,
            COUNT(*) as customer_count,
            ROUND(AVG(monetary)::numeric, 2) as avg_monetary,
            ROUND(AVG(churn_score)::numeric, 4) as avg_churn_score,
            ROUND(AVG(clv_12m)::numeric, 2) as avg_clv,
            ROUND(SUM(monetary)::numeric, 2) as total_revenue,
            ROUND(AVG(recency_days)::numeric, 1) as avg_recency,
            ROUND(AVG(frequency)::numeric, 2) as avg_frequency
        FROM customer_features
        GROUP BY rfm_segment
        ORDER BY avg_monetary DESC
    '''
    with engine.connect() as conn:
        rows = conn.execute(text(query)).fetchall()
    return [dict(row._mapping) for row in rows]

@router.get("/{segment_name}/customers")
def get_segment_customers(segment_name: str, limit: int = 50):
    with engine.connect() as conn:
        rows = conn.execute(text('''
            SELECT cf.customer_id, cf.monetary, cf.frequency,
                   cf.recency_days, cf.churn_score, cf.clv_12m,
                   c.country, c.total_revenue
            FROM customer_features cf
            JOIN customers c ON cf.customer_id = c.customer_id
            WHERE cf.rfm_segment = :seg
            ORDER BY cf.monetary DESC
            LIMIT :limit
        '''), {'seg': segment_name, 'limit': limit}).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"Segment '{segment_name}' not found")
    return [dict(row._mapping) for row in rows]

@router.get("/{segment_name}/history")
def get_segment_history(segment_name: str):
    with engine.connect() as conn:
        rows = conn.execute(text('''
            SELECT snapshot_date, customer_count, total_revenue,
                   avg_clv, avg_churn_score
            FROM segment_history
            WHERE segment_name = :seg
            ORDER BY snapshot_date DESC
            LIMIT 90
        '''), {'seg': segment_name}).fetchall()
    return [dict(row._mapping) for row in rows]