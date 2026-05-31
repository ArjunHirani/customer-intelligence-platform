import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from fastapi import APIRouter
from sqlalchemy import create_engine, text

router = APIRouter()

engine = create_engine(
    'postgresql://postgres:password@localhost:5433/customer_intelligence',
    pool_pre_ping=True
)

@router.get("/overview")
def get_overview():
    with engine.connect() as conn:
        total_customers = conn.execute(text('SELECT COUNT(*) FROM customers')).scalar()
        total_revenue = conn.execute(text('SELECT ROUND(SUM(total_revenue)::numeric,2) FROM customers')).scalar()
        avg_clv = conn.execute(text('SELECT ROUND(AVG(clv_12m)::numeric,2) FROM customer_features WHERE clv_12m IS NOT NULL')).scalar()
        high_risk = conn.execute(text('SELECT COUNT(*) FROM customer_features WHERE churn_score >= 0.65')).scalar()
        champions = conn.execute(text("SELECT COUNT(*) FROM customer_features WHERE rfm_segment = 'Champions'")).scalar()
        cannot_lose = conn.execute(text("SELECT COUNT(*) FROM customer_features WHERE rfm_segment = 'Cannot Lose Them'")).scalar()
        active_alerts = conn.execute(text('SELECT COUNT(*) FROM alerts WHERE is_resolved = FALSE')).scalar()
        avg_churn = conn.execute(text('SELECT ROUND(AVG(churn_score)::numeric,4) FROM customer_features WHERE churn_score IS NOT NULL')).scalar()

    return {
        'total_customers': total_customers,
        'total_revenue': float(total_revenue or 0),
        'avg_clv': float(avg_clv or 0),
        'high_risk_customers': high_risk,
        'champions_count': champions,
        'cannot_lose_count': cannot_lose,
        'active_alerts': active_alerts,
        'avg_churn_score': float(avg_churn or 0)
    }

@router.get("/revenue-trend")
def get_revenue_trend():
    with engine.connect() as conn:
        rows = conn.execute(text('''
            SELECT
                DATE_TRUNC('month', invoice_date) as month,
                ROUND(SUM(total_price)::numeric, 2) as revenue,
                COUNT(DISTINCT customer_id) as unique_customers,
                COUNT(DISTINCT invoice_no) as total_orders
            FROM transactions
            GROUP BY DATE_TRUNC('month', invoice_date)
            ORDER BY month
        ''')).fetchall()
    return [dict(row._mapping) for row in rows]

@router.get("/cohort-retention")
def get_cohort_retention():
    with engine.connect() as conn:
        rows = conn.execute(text('''
            WITH first_purchase AS (
                SELECT customer_id,
                       DATE_TRUNC('month', MIN(invoice_date)) as cohort_month
                FROM transactions
                GROUP BY customer_id
            ),
            monthly_activity AS (
                SELECT
                    t.customer_id,
                    fp.cohort_month,
                    DATE_TRUNC('month', t.invoice_date) as activity_month
                FROM transactions t
                JOIN first_purchase fp ON t.customer_id = fp.customer_id
            ),
            cohort_data AS (
                SELECT
                    cohort_month,
                    activity_month,
                    COUNT(DISTINCT customer_id) as customers,
                    EXTRACT(MONTH FROM AGE(activity_month, cohort_month)) as month_number
                FROM monthly_activity
                GROUP BY cohort_month, activity_month
            )
            SELECT
                TO_CHAR(cohort_month, 'YYYY-MM') as cohort,
                month_number::int as month_number,
                customers
            FROM cohort_data
            WHERE month_number >= 0 AND month_number <= 11
            ORDER BY cohort_month, month_number
        ''')).fetchall()
    return [dict(row._mapping) for row in rows]

@router.get("/top-customers")
def get_top_customers(limit: int = 10):
    with engine.connect() as conn:
        rows = conn.execute(text('''
            SELECT c.customer_id, c.country, c.total_revenue,
                   cf.rfm_segment, cf.churn_score, cf.clv_12m,
                   cf.frequency, cf.monetary
            FROM customers c
            JOIN customer_features cf ON c.customer_id = cf.customer_id
            ORDER BY c.total_revenue DESC
            LIMIT :limit
        '''), {'limit': limit}).fetchall()
    return [dict(row._mapping) for row in rows]