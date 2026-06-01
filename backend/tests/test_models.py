import pytest
import pickle
import json
import os
import numpy as np
import pandas as pd

MODELS_DIR = os.path.join(os.path.dirname(__file__), '..', 'models_saved')

def test_churn_model_file_exists():
    assert os.path.exists(os.path.join(MODELS_DIR, 'churn_model.pkl'))

def test_churn_model_meta_exists():
    assert os.path.exists(os.path.join(MODELS_DIR, 'churn_model_meta.json'))

def test_churn_model_loads():
    with open(os.path.join(MODELS_DIR, 'churn_model.pkl'), 'rb') as f:
        model = pickle.load(f)
    assert model is not None

def test_churn_model_meta_has_required_fields():
    with open(os.path.join(MODELS_DIR, 'churn_model_meta.json'), 'r') as f:
        meta = json.load(f)
    assert 'feature_cols' in meta
    assert 'auc' in meta
    assert meta['auc'] > 0.7

def test_churn_model_predicts_probability():
    with open(os.path.join(MODELS_DIR, 'churn_model.pkl'), 'rb') as f:
        model = pickle.load(f)
    with open(os.path.join(MODELS_DIR, 'churn_model_meta.json'), 'r') as f:
        meta = json.load(f)

    feature_cols = meta['feature_cols']
    sample = pd.DataFrame([{col: 1.0 for col in feature_cols}])
    proba = model.predict_proba(sample)
    assert proba.shape == (1, 2)
    assert 0.0 <= proba[0][1] <= 1.0

def test_churn_model_auc_above_threshold():
    with open(os.path.join(MODELS_DIR, 'churn_model_meta.json'), 'r') as f:
        meta = json.load(f)
    assert meta['auc'] >= 0.75, f"AUC too low: {meta['auc']}"

def test_clv_bgnbd_model_exists():
    assert os.path.exists(os.path.join(MODELS_DIR, 'bgnbd_model.pkl'))

def test_clv_gamma_gamma_model_exists():
    assert os.path.exists(os.path.join(MODELS_DIR, 'gamma_gamma_model.pkl'))

def test_anomaly_model_exists():
    assert os.path.exists(os.path.join(MODELS_DIR, 'anomaly_model.pkl'))

def test_anomaly_model_loads():
    with open(os.path.join(MODELS_DIR, 'anomaly_model.pkl'), 'rb') as f:
        bundle = pickle.load(f)
    assert 'model' in bundle
    assert 'scaler' in bundle

def test_anomaly_model_predicts():
    with open(os.path.join(MODELS_DIR, 'anomaly_model.pkl'), 'rb') as f:
        bundle = pickle.load(f)
    model = bundle['model']
    scaler = bundle['scaler']
    sample = np.array([[30, 5, 1000, 200, 0.1, 10, 0.5, 5]])
    scaled = scaler.transform(sample)
    prediction = model.predict(scaled)
    assert prediction[0] in [-1, 1]