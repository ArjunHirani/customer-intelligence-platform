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
def get_alerts(resolved: bool = False):
    with engine.connect() as conn:
        rows = conn.execute(text('''
            SELECT alert_id, alert_type, segment_name, description,
                   severity, metric_name, metric_value, baseline_value,
                   deviation_pct, is_resolved, detected_at
            FROM alerts
            WHERE is_resolved = :resolved
            ORDER BY
                CASE severity
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 3
                END,
                detected_at DESC
        '''), {'resolved': resolved}).fetchall()
    return [dict(row._mapping) for row in rows]

@router.patch("/{alert_id}/resolve")
def resolve_alert(alert_id: int):
    with engine.begin() as conn:
        result = conn.execute(text('''
            UPDATE alerts SET is_resolved = TRUE
            WHERE alert_id = :aid
            RETURNING alert_id
        '''), {'aid': alert_id})
        if not result.fetchone():
            raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"message": f"Alert {alert_id} resolved"}