import os
import sys
import math
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
            SELECT customer_id, monetary, churn_score, clv_12m, frequency
            FROM customer_features
            WHERE rfm_segment = :seg
            ORDER BY churn_score DESC
            LIMIT :n
        '''), {'seg': request.segment, 'n': request.n_customers}).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"Segment '{request.segment}' not found")

    customers = [dict(r._mapping) for r in rows]
    n = len(customers)
    discount = float(request.discount_pct)

    # Average metrics across targeted customers
    avg_clv        = sum(float(c['clv_12m'] or 0)    for c in customers) / n
    avg_monetary   = sum(float(c['monetary'] or 0)   for c in customers) / n
    avg_churn      = sum(float(c['churn_score'] or 0.5) for c in customers) / n
    avg_frequency  = sum(float(c['frequency'] or 1)  for c in customers) / n

    # Average order value = total spend / number of orders
    avg_order_value = avg_monetary / max(avg_frequency, 1)

    # --- COST MODEL ---
    # We give a discount on ONE purchase to each targeted customer
    # Cost = number of customers × avg order value × discount rate
    cost_of_intervention = n * avg_order_value * (discount / 100)

    # --- RETENTION MODEL ---
    # Of the targeted customers, avg_churn% are actually at risk of leaving
    # Discount effectiveness follows diminishing returns:
    #   retention_rate = discount% × 0.8 (capped at 35%)
    # Example: 10% discount → 8% of at-risk customers retained
    #          20% discount → 16% retained
    #          30% discount → 24% retained
    #          50% discount → 35% retained (cap)
    base_retention_rate = min(0.05 + (discount - 5) * 0.008, 0.30)

    # Customers likely to churn among our targeted group
    churners_in_group = n * avg_churn

    # Customers we actually retain
    customers_retained = churners_in_group * base_retention_rate

    # --- REVENUE SAVED MODEL ---
    # Each retained customer gives us their remaining CLV
    # We use 30% of CLV as a conservative estimate of near-term value recovered
    estimated_revenue_saved = customers_retained * avg_clv * 0.30

    # --- ROI ---
    roi = round(
        (estimated_revenue_saved - cost_of_intervention) / max(cost_of_intervention, 1) * 100, 2
    )

    # --- RECOMMENDATION ---
    if roi > 80:
        recommendation = (
            f"Excellent ROI of {roi:.1f}%. A {discount:.0f}% discount on this segment "
            f"is highly cost-effective — the CLV of retained customers far outweighs the discount cost. "
            f"Strongly recommend running this campaign."
        )
    elif roi > 30:
        recommendation = (
            f"Strong ROI of {roi:.1f}%. A {discount:.0f}% discount delivers good returns "
            f"for this segment. Recommend proceeding with the campaign."
        )
    elif roi > 0:
        recommendation = (
            f"Positive but thin ROI of {roi:.1f}%. The {discount:.0f}% discount is viable "
            f"but margins are slim. Consider targeting fewer, higher-value customers."
        )
    elif roi > -30:
        recommendation = (
            f"Slightly negative ROI of {roi:.1f}%. The {discount:.0f}% discount costs more "
            f"than the revenue it recovers. Try reducing the discount to 10-15%."
        )
    else:
        recommendation = (
            f"Negative ROI of {roi:.1f}%. A {discount:.0f}% discount is too expensive "
            f"for this segment's CLV. Reduce discount significantly or choose a higher-value segment."
        )

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