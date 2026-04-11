"""
FastAPI Main Application
-------------------------
Cardiac Risk Prediction Platform — Backend v2.0
"""
import os
from dotenv import load_dotenv

load_dotenv()  # Load backend/.env *before* any other imports

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .routers import vitals, ecg, emergency, hospitals

# ── Create FastAPI app
app = FastAPI(
    title="Cardiac AI — Backend API",
    description=(
        "Cardiac Risk Prediction Platform v2.0.\n"
        "Modes: Routine Screening (LightGBM + Framingham), "
        "ECG Diagnosis (Advanced Multi-Modal AI), "
        "Emergency Triage (NICE CG95 + Google Places)."
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS (allow React dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers
app.include_router(vitals.router)
app.include_router(ecg.router)
app.include_router(emergency.router)
app.include_router(hospitals.router)

# ── Static: serve uploaded ECG images
os.makedirs("uploads/ecg", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# ── Events
@app.on_event("startup")
async def startup():
    init_db()
    print("\n" + "=" * 50)
    print("  CARDIAC AI BACKEND v2.0 — LIVE")
    print("  Docs: http://localhost:8000/docs")
    print("=" * 50 + "\n")


# ── Health check
@app.get("/", tags=["health"])
async def root():
    return {
        "status": "healthy",
        "app": "Cardiac AI Backend",
        "version": "2.0.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health():
    from .routers.vitals import get_risk_model
    model = get_risk_model()
    return {
        "status": "healthy",
        "model_loaded": model.is_loaded,
        "model_accuracy": f"{model.test_accuracy * 100:.2f}%" if model.is_loaded else "Model not trained yet",
    }
