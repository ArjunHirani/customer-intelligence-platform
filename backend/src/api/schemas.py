
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import date

class CustomerSummary(BaseModel):
    customer_id: str
    country: Optional[str]
    first_purchase: Optional[str]
    last_purchase: Optional[str]
    total_orders: Optional[int]
    total_revenue: Optional[float]

class CustomerFeatures(BaseModel):
    customer_id: str
    recency_days: Optional[int]
    frequency: Optional[int]
    monetary: Optional[float]
    avg_order_value: Optional[float]
    return_rate: Optional[float]
    product_diversity: Optional[int]
    churn_score: Optional[float]
    clv_12m: Optional[float]
    rfm_segment: Optional[str]

class CustomerFull(BaseModel):
    customer_id: str
    country: Optional[str]
    first_purchase: Optional[str]
    last_purchase: Optional[str]
    total_orders: Optional[int]
    total_revenue: Optional[float]
    recency_days: Optional[int]
    frequency: Optional[int]
    monetary: Optional[float]
    avg_order_value: Optional[float]
    return_rate: Optional[float]
    product_diversity: Optional[int]
    churn_score: Optional[float]
    clv_12m: Optional[float]
    rfm_segment: Optional[str]
    churn_risk_level: Optional[str]

class ChurnRisk(BaseModel):
    customer_id: str
    churn_score: float
    churn_risk_level: str
    top_factors: List[dict]
    rfm_segment: Optional[str]
    monetary: Optional[float]
    clv_12m: Optional[float]

class SegmentSummary(BaseModel):
    rfm_segment: str
    customer_count: int
    avg_monetary: float
    avg_churn_score: float
    avg_clv: float
    total_revenue: float
    avg_recency: float

class AlertOut(BaseModel):
    alert_id: int
    alert_type: str
    segment_name: Optional[str]
    description: str
    severity: str
    metric_name: Optional[str]
    metric_value: Optional[float]
    baseline_value: Optional[float]
    deviation_pct: Optional[float]
    is_resolved: bool
    detected_at: Any

class WhatIfRequest(BaseModel):
    segment: str
    discount_pct: float
    n_customers: int

class WhatIfResponse(BaseModel):
    segment: str
    customers_targeted: int
    avg_clv_targeted: float
    discount_pct: float
    cost_of_intervention: float
    estimated_revenue_saved: float
    roi: float
    recommendation: str

class OverviewKPIs(BaseModel):
    total_customers: int
    total_revenue: float
    avg_clv: float
    high_risk_customers: int
    champions_count: int
    cannot_lose_count: int
    active_alerts: int
    avg_churn_score: float