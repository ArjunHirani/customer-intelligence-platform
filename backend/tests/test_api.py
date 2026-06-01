import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.api.main import app

client = TestClient(app)

def has_data():
    try:
        r = client.get('/analytics/overview')
        return r.json().get('total_customers', 0) > 0
    except Exception:
        return False

def test_health_endpoint():
    response = client.get('/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert 'version' in data

def test_root_endpoint():
    response = client.get('/')
    assert response.status_code == 200
    data = response.json()
    assert 'message' in data
    assert 'docs' in data

def test_get_overview_returns_kpis():
    response = client.get('/analytics/overview')
    assert response.status_code == 200
    required = [
        'total_customers', 'total_revenue', 'avg_clv',
        'champions_count', 'active_alerts', 'avg_churn_score'
    ]
    data = response.json()
    for field in required:
        assert field in data, f"Missing KPI: {field}"

def test_get_alerts_returns_list():
    response = client.get('/alerts/')
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_customer_not_found_returns_404():
    response = client.get('/customers/INVALID_ID_99999')
    assert response.status_code == 404

def test_get_customers_pagination():
    response = client.get('/customers/?limit=5&offset=0')
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 5

def test_what_if_invalid_segment():
    response = client.post('/simulate/what-if', json={
        'segment': 'NonExistentSegment',
        'discount_pct': 10.0,
        'n_customers': 10
    })
    assert response.status_code == 404

@pytest.mark.skipif(not has_data(), reason="No data in database — skipping data-dependent tests")
def test_get_segments_returns_list():
    response = client.get('/segments/')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

@pytest.mark.skipif(not has_data(), reason="No data in database — skipping data-dependent tests")
def test_segment_has_required_fields():
    response = client.get('/segments/')
    data = response.json()
    required = ['rfm_segment', 'customer_count', 'avg_monetary', 'avg_churn_score']
    for field in required:
        assert field in data[0], f"Missing field: {field}"

@pytest.mark.skipif(not has_data(), reason="No data in database — skipping data-dependent tests")
def test_get_customers_returns_list():
    response = client.get('/customers/')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

@pytest.mark.skipif(not has_data(), reason="No data in database — skipping data-dependent tests")
def test_overview_values_positive():
    response = client.get('/analytics/overview')
    data = response.json()
    assert data['total_customers'] > 0
    assert data['total_revenue'] > 0
    assert data['champions_count'] > 0

@pytest.mark.skipif(not has_data(), reason="No data in database — skipping data-dependent tests")
def test_revenue_trend_returns_data():
    response = client.get('/analytics/revenue-trend')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

@pytest.mark.skipif(not has_data(), reason="No data in database — skipping data-dependent tests")
def test_top_customers_returns_data():
    response = client.get('/analytics/top-customers?limit=5')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) <= 5

@pytest.mark.skipif(not has_data(), reason="No data in database — skipping data-dependent tests")
def test_what_if_simulation():
    response = client.post('/simulate/what-if', json={
        'segment': 'At Risk',
        'discount_pct': 15.0,
        'n_customers': 20
    })
    assert response.status_code == 200
    data = response.json()
    assert 'roi' in data
    assert 'recommendation' in data
    assert data['customers_targeted'] > 0