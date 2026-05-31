import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routers import customers, segments, alerts, simulate, analytics

app = FastAPI(
    title="Customer Intelligence Platform",
    description="AI-powered customer analytics — churn prediction, CLV, anomaly detection",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customers.router, prefix="/customers", tags=["Customers"])
app.include_router(segments.router, prefix="/segments", tags=["Segments"])
app.include_router(alerts.router, prefix="/alerts", tags=["Alerts"])
app.include_router(simulate.router, prefix="/simulate", tags=["Simulation"])
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}

@app.get("/")
def root():
    return {
        "message": "Customer Intelligence Platform API",
        "docs": "/docs",
        "health": "/health"
    }