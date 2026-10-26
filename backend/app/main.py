"""
FastAPI Main Application
-------------------------
Cardiac Risk Prediction Platform — Backend v2.0
"""
import os
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)
load_dotenv()  # Fallback to current working directory .env

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .routers import auth, vitals, ecg, emergency, hospitals, chat

# ── Create FastAPI app
app = FastAPI(
    title="Cardiac AI — Backend API",
    description=(
        "Cardiac Risk Prediction Platform v2.0.\n"
        "Modes: Routine Screening (LightGBM + Framingham), "
        "ECG Diagnosis (PTB-XL Residual 1D CNN), "
        "Patient Chat & Summaries (Sarvam AI), "
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
        # Production — Vercel frontend
        "https://cardiac-analyst.vercel.app",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers
app.include_router(auth.router)
app.include_router(vitals.router)
app.include_router(ecg.router)
app.include_router(emergency.router)
app.include_router(hospitals.router)
app.include_router(chat.router)

# ── Internal ECG storage directory (not mounted publicly; served only via authenticated endpoints)
os.makedirs("uploads/ecg", exist_ok=True)


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
