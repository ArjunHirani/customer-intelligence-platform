import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from fastapi import APIRouter, HTTPException
from sqlalchemy import create_engine, text
from src.api.schemas import WhatIfRequest, WhatIfResponse

router = APIRouter()

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5433/customer_intelligence')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

@router.post("/what-if", response_model=WhatIfResponse)
def what_if_simulation(request: WhatIfRequest):
    with engine.connect() as conn:
        rows = conn.execute(text('''
            SELECT customer_id, monetary, churn_score, clv_12m
            FROM customer_features
            WHERE rfm_segment = :seg
            ORDER BY churn_score DESC
            LIMIT :n
        '''), {'seg': request.segment, 'n': request.n_customers}).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"Segment '{request.segment}' not found")

    customers = [dict(r._mapping) for r in rows]
    n = len(customers)

    avg_clv = sum(float(c['clv_12m'] or 0) for c in customers) / n if n > 0 else 0
    avg_monetary = sum(float(c['monetary'] or 0) for c in customers) / n if n > 0 else 0

    discount = float(request.discount_pct)
    retention_lift = min(discount * 0.8, 40) / 100
    estimated_revenue_saved = avg_clv * retention_lift * n
    cost_of_intervention = avg_monetary * (discount / 100) * n
    roi = round(
        (estimated_revenue_saved - cost_of_intervention) / max(cost_of_intervention, 1) * 100, 2
    ) if cost_of_intervention > 0 else 0

    if roi > 50:
        recommendation = f"Strong ROI of {roi:.1f}% with {discount:.0f}% discount. Recommend proceeding."
    elif roi > 0:
        recommendation = f"Positive ROI of {roi:.1f}% with {discount:.0f}% discount. Campaign is viable."
    else:
        recommendation = f"Negative ROI of {roi:.1f}% with {discount:.0f}% discount. Consider reducing the discount."

    return WhatIfResponse(
        segment=request.segment,
        customers_targeted=n,
        avg_clv_targeted=round(avg_clv, 2),
        discount_pct=discount,
        cost_of_intervention=round(cost_of_intervention, 2),
        estimated_revenue_saved=round(estimated_revenue_saved, 2),
        roi=roi,
        recommendation=recommendation
    )