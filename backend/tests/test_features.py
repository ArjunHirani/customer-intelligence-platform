import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.features.rfm import compute_rfm, assign_rfm_segment

def make_sample_df():
    return pd.DataFrame({
        'customer_id': ['C1', 'C1', 'C2', 'C2', 'C3'],
        'invoice_no':  ['I1', 'I2', 'I3', 'I4', 'I5'],
        'total_price': [100.0, 200.0, 50.0, 75.0, 500.0],
        'invoice_date': pd.to_datetime([
            '2011-12-01', '2011-12-05',
            '2011-06-01', '2011-08-01',
            '2011-11-01'
        ], utc=True),
        'stock_code': ['S1', 'S2', 'S1', 'S3', 'S4'],
        'quantity':   [2, 3, 1, 2, 5],
        'unit_price': [50.0, 66.7, 50.0, 37.5, 100.0]
    })

def test_compute_rfm_returns_correct_columns():
    df = make_sample_df()
    rfm = compute_rfm(df)
    required_cols = ['customer_id', 'recency_days', 'frequency', 'monetary']
    for col in required_cols:
        assert col in rfm.columns, f"Missing column: {col}"

def test_compute_rfm_correct_customer_count():
    df = make_sample_df()
    rfm = compute_rfm(df)
    assert len(rfm) == 3

def test_compute_rfm_frequency_correct():
    df = make_sample_df()
    rfm = compute_rfm(df).set_index('customer_id')
    assert rfm.loc['C1', 'frequency'] == 2
    assert rfm.loc['C2', 'frequency'] == 2
    assert rfm.loc['C3', 'frequency'] == 1

def test_compute_rfm_monetary_correct():
    df = make_sample_df()
    rfm = compute_rfm(df).set_index('customer_id')
    assert rfm.loc['C1', 'monetary'] == 300.0
    assert rfm.loc['C2', 'monetary'] == 125.0

def test_compute_rfm_recency_positive():
    df = make_sample_df()
    rfm = compute_rfm(df)
    assert (rfm['recency_days'] >= 0).all()

def test_avg_order_value_calculated():
    df = make_sample_df()
    rfm = compute_rfm(df).set_index('customer_id')
    assert rfm.loc['C1', 'avg_order_value'] == 150.0

def test_assign_rfm_segment_returns_valid_segments():
    df = make_sample_df()
    rfm = compute_rfm(df)
    rfm['return_rate'] = 0.0
    rfm = assign_rfm_segment(rfm)
    valid_segments = {
        'Champions', 'Loyal Customers', 'Potential Loyalists',
        'Recent Customers', 'Promising', 'At Risk',
        'Cannot Lose Them', 'Hibernating'
    }
    assert rfm['rfm_segment'].isin(valid_segments).all()

def test_no_null_segments():
    df = make_sample_df()
    rfm = compute_rfm(df)
    rfm['return_rate'] = 0.0
    rfm = assign_rfm_segment(rfm)
    assert rfm['rfm_segment'].isnull().sum() == 0