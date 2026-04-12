# ❤️ Cardiac Analyst

> **AI-powered cardiac risk prediction and emergency response system with real-time ECG analysis, triage, and plain-language reporting — accessible from any browser, no app store required.**

[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-6.0-3178C6?logo=typescript)](https://www.typescriptlang.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Python-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.x-FF6F00?logo=tensorflow)](https://www.tensorflow.org)
[![Claude API](https://img.shields.io/badge/Claude-Sonnet_4-D97757)](https://www.anthropic.com)
[![PWA](https://img.shields.io/badge/PWA-Installable-5A0FC8)](https://web.dev/progressive-web-apps)
[![License](https://img.shields.io/badge/License-Development_Only-red)]()

---

## 🫀 Introduction

Cardiovascular disease is the leading cause of death in India, claiming **4.77 million lives annually**. Most patients arrive at emergency rooms only when damage is already irreversible — because there are no accessible, intelligent tools for early self-screening at home.

**Cardiac Analyst** is a Progressive Web App (PWA) that acts as a **24/7 personal cardiac monitor**. It runs entirely in a browser — no app store download required — and provides three integrated capabilities:

1. **Routine screening** — log daily vitals, get an AI-computed 10-year cardiovascular risk score with explainable reasoning
2. **ECG-based diagnosis** — upload any ECG image or CSV, get multi-disease classification across 15 cardiac conditions with GradCAM heatmaps and plain-language AI reports
3. **Emergency triage** — activate a full emergency response stack including hospital finder, ambulance routing, and family guardian alerts

> ⚠️ This is an AI-assisted screening tool and is not a substitute for professional medical diagnosis or advice.

---

## 🎯 What It Does

```
User logs vitals daily
       ↓
LightGBM computes 10-year ASCVD risk score + SHAP explanation
       ↓
Risk ≥ 15%? → Prompt to get ECG at nearby clinic and upload it
       ↓
ECG uploaded → OpenCV preprocesses → SE-ResNet + Transformer ensemble classifies
       ↓
Claude API generates plain-language report (English + Hindi)
       ↓
STEMI detected? → Auto-redirect to Emergency Mode
       ↓
Hospital map + ambulance routing + family guardian alert
```

---

## ✨ Features

### Mode 1 — Routine Screening
| # | Feature | Description |
|---|---------|-------------|
| F01 | Daily Vitals Logger | BP, weight, SpO2, HR, glucose, cholesterol — validated form, auto-saved |
| F02 | Routine Risk Score | LightGBM computes 10-year ASCVD-aligned risk: Low / Borderline / Elevated |
| F03 | SHAP Explainability Dashboard | Interactive bar chart — *"Your BP contributed 34% to this score"* |
| F04 | ECG Escalation Trigger | Banner appears at risk >15% prompting ECG upload |
| F13 | Longitudinal Trend Alerts | Web Push notification if BP rises >10 mmHg 3 weeks in a row |

### Mode 2 — ECG-Enhanced Diagnosis
| # | Feature | Description |
|---|---------|-------------|
| F05 | ECG Upload & Parsing | Drag-and-drop zone; accepts JPG, PNG, PDF, CSV (KardiaMobile, Apple Watch) |
| F06 | AI ECG Diagnosis | 15-disease multi-label classification via SE-ResNet + Transformer ensemble |
| F07 | GradCAM Heatmap | Colored SVG overlay on ECG — shows exactly which leads triggered each diagnosis |
| F08 | Plain-Language Report | Claude API generates 3–5 sentence patient-friendly explanation; English + Hindi |
| F14 | ECG History Archive | Timeline of past ECG sessions with side-by-side comparison |
| F19 | PDF Report Export | One-click branded PDF with ECG image, GradCAM, SHAP chart, AI text |
| F20 | Bulk Clinic Upload | Up to 50 ECGs; results as downloadable CSV + per-patient reports |

### Mode 3 — Emergency Triage
| # | Feature | Description |
|---|---------|-------------|
| F09 | Symptom Triage | 8 Yes/No questions → Rule engine + ML classifies severity |
| F10 | One-Tap SOS | Persistent red button on every page; triggers tel:112, shares GPS, opens hospital map |
| F12 | Ambulance Routing | Lists 112, 108, and private services with tel: links and GPS ETA |
| F16 | Offline Emergency Cache | Service Worker caches hospital list + SOS page — works without internet |

### Cross-Cutting
- 🌐 PWA installable on Android and iOS Safari (Add to Home Screen)
- 🔐 OTP login + JWT in httpOnly cookies (never localStorage)
- 🇮🇳 English ↔ Hindi toggle (i18next)
- ♿ WCAG 2.1 AA accessibility compliance
- 🏥 ABHA / NDHM health ID integration
- 🖥️ Embeddable iframe widget for hospital portals

---

## 🛠 Tech Stack

### Frontend
| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | React 19 + TypeScript + Vite | Type-safe, fast HMR, PWA-ready |
| State | Zustand + React Query | Global state + server-state caching |
| UI | shadcn/ui + Tailwind CSS | Accessible, responsive components |
| Charts | Chart.js + D3.js + SVG overlays | Vitals trends, SHAP bars, GradCAM heatmap |
| Forms | React Hook Form + Zod | Schema-validated, accessible error handling |
| Maps | Google Maps JS API + Geolocation API | Hospital finder with live filtering |
| Animation | Framer Motion | Page transitions and micro-interactions |
| i18n | i18next + react-i18next | English/Hindi lazy-loaded language packs |
| Offline | Service Worker (Workbox) + IndexedDB | Emergency page cache + background sync |
| Uploads | React Dropzone | ECG file drag-and-drop |

### Backend
| Service | Stack | Responsibility |
|---------|-------|---------------|
| Auth Service | FastAPI + PostgreSQL + AWS Cognito | OTP, JWT, ABHA |
| Vitals Service | FastAPI + PostgreSQL + SageMaker | CRUD vitals, ASCVD scoring, SHAP |
| ECG Service | FastAPI + OpenCV + TF Serving + Gemini API | Upload, preprocess, infer, GradCAM, PDF |
| Risk Engine | FastAPI + LightGBM + Redis | Fusion scoring, triage, alert thresholds |
| Emergency Service | FastAPI + Google Maps | Hospitals, ambulance, SOS |
| Report Service | FastAPI + WeasyPrint + Jinja2 | Branded PDF generation |

### ML & AI
| Component | Technology |
|-----------|-----------|
| Tabular risk model | LightGBM + SHAP + Indian cohort calibration (INTERHEART SA) |
| ECG classification | 1D-SE-ResNet + Transformer (soft-vote ensemble) |
| ECG preprocessing | OpenCV + SciPy + NeuroKit2 |
| Explainability | GradCAM (tf-explain) + SHAP |
| Model serving | AWS SageMaker Real-Time Endpoints (GPU auto-scale) |
| NLP reports | Gemini API — gemini flash 2.5 |
| PDF reports | WeasyPrint + Jinja2 |

### Infrastructure
| Layer | Technology |
|-------|-----------|
| Database | PostgreSQL Aurora Serverless v2 + PostGIS |
| Cache | Redis (ElastiCache) — 6h TTL for hospital data |
| Object storage | AWS S3 (AES-256 SSE) |
| Container orchestration | AWS EKS (Kubernetes) |
| IaC | Terraform |
| CI/CD | GitHub Actions + AWS CodePipeline |
| Monitoring | CloudWatch + Grafana + Sentry + Datadog RUM |

---

## ⚙️ How It Works

### Routine Screening Flow

```
1. User authenticates via Phone OTP → JWT issued in httpOnly cookie
2. Daily Check-In form (React Hook Form + Zod validation)
   Fields: Weight, Systolic BP, Diastolic BP, HR, SpO2, [Glucose, Cholesterol]
3. POST /api/v1/vitals →
   LightGBM runs: vitals + profile + 30-day rolling avg + Indian cohort coefficients
   Returns: risk_score, risk_tier, shap_top5[], trend_delta, ecg_prompt flag
4. SHAP dashboard renders top-5 contributors as interactive D3 bar chart
5. If risk ≥ Elevated → ECG escalation banner appears
6. Else → Chart.js 30-day trend charts, lifestyle tip card, Web Push reminder
```

### ECG Analysis Flow

```
1. User drags & drops ECG file (JPG/PNG/PDF/CSV)
2. Client: file validation, status steps → 'Uploading... Extracting... Analysing...'
3. Server-side preprocessing (OpenCV + NeuroKit2):
   deskew → grid removal → 12-lead region detection → signal extraction
   → resample to 500 Hz, 10s per lead → normalize to [-1, 1]
4. Ensemble inference (TF Serving on GPU):
   1D-SE-ResNet (PTB-XL trained) + Transformer (CPSC+Georgia trained)
   → soft-vote ensemble → probability vector for 15 conditions
5. Decision thresholds: >0.85 = DETECTED (red), 0.50–0.85 = POSSIBLE (amber)
6. Fusion: Final_Risk = 0.3 × Tabular_Score + 0.7 × ECG_Score
   STEMI override: if ECG_STEMI_prob > 0.85 → force Emergency Mode
7. GradCAM saliency computed → colored SVG overlay on ECG image
8. Claude API called → 3–5 sentence patient-friendly explanation per condition
9. Output: annotated ECG + probability bars + SHAP chart + AI report + PDF export
```

### Emergency Triage Flow

```
1. SOS button (visible on every page) OR 'I Feel Unwell' CTA
2. 12 Yes/No triage questions (large touch targets, WCAG compliant)
3. Client-side JS rule engine runs in parallel with server-side Random Forest
4. Severity classification:
   NORMAL → reassurance + tips
   SEE DOCTOR TODAY → GP finder map
   EMERGENCY → full emergency stack
5. Emergency screen:
   - 'CALL 112 NOW' (tel:112 link)
   - GPS location shared via Web Share API
   - Google Maps embed → 3 nearest hospitals filtered by ICU/cath-lab
   - Ambulance panel → tel: links + ETA
   - Calm first-aid instructions (Claude-generated)
   - Twilio SMS + FCM push → family guardian contacts
6. Offline: Service Worker serves cached page even without internet
```

---

## 🤖 How the Model Is Trained

### Model 1 — LightGBM Tabular Risk Model

**Dataset:** ASCVD / Framingham Heart Study + INTERHEART South Asia subgroup (~7,000 Indian patients) for demographic re-calibration.

**Feature Engineering:**
```
Input: age, sex, BMI (computed), systolic BP, diastolic BP, pulse pressure,
       heart rate, SpO2, fasting glucose, total cholesterol, smoking_flag,
       diabetes_flag, family_hx_flag, 30-day rolling average of each vital

Feature transforms:
  - BMI = weight(kg) / height(m)²
  - Pulse pressure = systolic - diastolic
  - 7-day & 30-day EWM (exponentially weighted mean) per vital
  - Binary flags for clinical thresholds (BP > 140, glucose > 126, etc.)
```

**Training Process:**
```
1. LightGBM Classifier trained with cross-entropy loss
2. Platt scaling for probability calibration (outputs calibrated 0–1 probabilities)
3. SHAP TreeExplainer computes feature contribution per prediction
4. Indian cohort calibration: re-fit intercept on INTERHEART SA subgroup
```

**Target:** 10-year ASCVD C-statistic ≥ 0.84

---

### Model 2 — ECG Ensemble (SE-ResNet + Transformer)

**Datasets:**
- PTB-XL (PhysioNet) — 21,837 annotated 12-lead ECG records → trains SE-ResNet
- CPSC 2018 + Georgia ECG Challenge (PhysioNet) → trains Transformer

**ECG Preprocessing Pipeline:**
```
Raw ECG image (JPG/PNG/PDF/CSV)
  ↓ OpenCV: deskew, remove grid lines, detect 12-lead regions
  ↓ NeuroKit2: extract waveform per lead, R-peak detection
  ↓ Resample to 500 Hz, window to 10s per lead
  ↓ Normalize each lead to [-1, 1]
  ↓ Shape: (12 leads × 5000 samples)
```

**SE-ResNet Architecture:**
```
Input: (12, 5000) → 1D Convolutional layers
→ Squeeze-and-Excitation blocks (channel attention across 12 leads)
→ Residual connections for deep training
→ Global Average Pooling
→ Dense → Sigmoid (multi-label, 15 classes)
```

**Transformer Architecture:**
```
Input: (12, 5000) → Patch embedding (patch size=50, 100 patches per lead)
→ Positional encoding
→ 6 Transformer encoder layers (8 attention heads)
→ [CLS] token → Dense → Sigmoid (15 classes)
```

**Ensemble & Loss:**
```
Soft-vote: P_final = α × P_SE-ResNet + (1−α) × P_Transformer
  where α is learned per condition class

Loss function:
  L = Focal_Loss(γ=2) + λ × ||Corr(ŷ) − Corr(y)||_F
  (Focal Loss for rare classes + label-correlation penalty)

Oversampling: SMOTE-ENN for WPW, Takotsubo, Hyperkalemia (<1% prevalence)

Test-Time Augmentation (inference):
  3 augmented versions (time-shift ±5ms, amplitude ±5%, Gaussian noise σ=0.01)
  → average probability vectors
```

**QTc Precision:**
```
NeuroKit2 detects every P-QRS-T complex per lead
QTc computed per beat using Bazett, Fredericia, and Fridericia formulas
Final QTc = median across all beats across all leads
Target precision: ±8ms MAE
```

**15 Conditions Detected:**
| Condition | ECG Signature | Severity |
|-----------|--------------|---------|
| STEMI | ST-elevation ≥1mm in ≥2 contiguous leads | 🔴 Emergency |
| NSTEMI / Unstable Angina | ST depression, T-wave inversion | 🔴 Urgent |
| Atrial Fibrillation | Absent P-waves, irregular R-R | 🟠 See doctor today |
| Atrial Flutter | Sawtooth flutter waves | 🟠 See doctor today |
| Ventricular Tachycardia | Wide-complex tachycardia >100 bpm | 🔴 Emergency |
| Heart Failure (LVH) | Sokolow-Lyon criteria, LBBB | 🟡 Review |
| Long QT Syndrome | QTc >450ms (M), >470ms (F) | 🟠 Review |
| WPW Syndrome | Delta wave, short PR interval | 🟠 Specialist |
| Pericarditis | Diffuse saddle ST elevation | 🟠 Review |
| LBBB / RBBB | Broad QRS ≥120ms | 🟡 Review |
| Bradycardia / AV Block | HR <50, prolonged PR, dropped QRS | 🟠 Evaluation |
| Takotsubo Cardiomyopathy | Diffuse T-wave inversions, QTc prolongation | 🟠 Urgent |
| Hyperkalemia | Peaked T-waves, wide QRS | 🔴 Urgent |
| Myocarditis | Diffuse ST elevation, sinus tachycardia | 🟠 Urgent |
| Normal Sinus Rhythm | — | 🟢 Normal |

**Accuracy Targets (v2.0):**
| Metric | Target |
|--------|--------|
| STEMI detection sensitivity | ≥ 97% |
| AFib AUROC | ≥ 0.995 |
| Multi-label ECG Macro-F1 | ≥ 0.88 |
| 10-year ASCVD C-statistic | ≥ 0.84 |
| Emergency triage sensitivity | ≥ 97% |
| QTc measurement precision | ±8ms MAE |

---

## 🏗 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              FRONTEND — React 19 + TypeScript PWA           │
│   Vite · Zustand · React Query · Chart.js · D3.js           │
│   Tailwind CSS · shadcn/ui · i18next · React Hook Form      │
│   Service Worker + IndexedDB (offline) · Google Maps        │
└────────────────────────┬────────────────────────────────────┘
                         │ REST API / HTTPS / JWT (httpOnly cookie)
┌────────────────────────▼────────────────────────────────────┐
│              API GATEWAY (AWS EKS / Kubernetes)             │
└──┬──────────┬──────────┬──────────┬──────────┬─────────────┘
   │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼
 Auth      Vitals      ECG       Risk      Emergency
Service   Service    Service    Engine     Service
FastAPI   FastAPI    FastAPI    FastAPI    FastAPI
+Cognito  +SageMaker +TF Serv  +LightGBM  +Maps+Twilio
                    +Claude    +Redis     +FCM
   │          │          │          │          │
   └──────────┴──────────┴──────────┴──────────┘
                         │
              ┌──────────▼──────────┐
              │   ML Pipeline       │
              │  (AWS SageMaker)    │
              │                     │
              │  LightGBM + SHAP    │
              │  SE-ResNet          │
              │  Transformer        │
              │  GradCAM            │
              │  NeuroKit2+OpenCV   │
              │  Claude API         │
              └──────────┬──────────┘
                         │
   ┌─────────────────────┼─────────────────────┐
   │                     │                     │
   ▼                     ▼                     ▼
PostgreSQL            Redis              AWS S3
Aurora v2         ElastiCache          (AES-256)
+PostGIS          (6h TTL cache)    ECG images
                                    GradCAM PNGs
users                               PDF reports
daily_vitals      hospital_cache    Model artifacts
ecg_uploads       session_tokens
diagnoses
symptom_events
hospital_cache
audit_log
```

---

## 🗄 Database Schema

```sql
-- Master user profiles
users (user_id PK, abha_id, phone UNIQUE, dob, sex, height, preferred_language)

-- Static clinical background
medical_history (user_id FK, conditions[], medications[], allergies[], family_hx[])

-- Core daily log — indexed on (user_id, date)
daily_vitals (user_id FK, date, bp_sys, bp_dia, hr, weight, spo2,
              glucose, cholesterol, risk_score, risk_tier, shap_json)

-- Emergency triage entries
symptom_events (user_id FK, ts, symptom_vector[12], bp_sys, hr,
                triage_result, confidence)

-- ECG uploads — links to S3 raw file + processed outputs
ecg_uploads (ecg_id PK, user_id FK, ts, s3_key, signal_json,
             model_output_json, ensemble_weights,
             gradcam_s3_key, pdf_report_s3_key)

-- Final ML output per session
diagnoses (diag_id PK, ecg_id FK, user_id FK,
           conditions[], probabilities[], confidence_intervals[],
           explanation_text EN, explanation_hindi HI, source)

-- Hospital data — PostGIS geospatial index, refreshed every 6h
hospital_cache (facility_id PK, name, lat, lon, icu_beds,
                ventilators, cath_lab, cardiac_surgeons, last_sync)

-- Ambulance directory
ambulance_directory (amb_id PK, city, service_name, contact,
                     gps_lat, gps_lon, type ENUM(govt, private))

-- Family guardian contacts
guardian_contacts (user_id FK, contact_name, phone, email,
                   notify_sms, notify_email)

-- Immutable PHI access log — 7-year retention
audit_log (log_id PK, user_id FK, action, ip_address,
           user_agent, ts, resource_id)
```

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/vitals` | Submit daily vitals → get risk score + SHAP + trend |
| `POST` | `/api/v1/ecg/upload` | Upload ECG file → get diagnosis + GradCAM + AI report |
| `POST` | `/api/v1/emergency/triage` | Submit symptoms → get severity + hospitals + ambulances |
| `GET` | `/api/v1/hospitals/nearby` | `?lat=&lon=&radius_km=10&requires=cath_lab` |
| `GET` | `/api/v1/ambulance/nearby` | `?lat=&lon=` → nearest ambulance services + ETA |
| `GET` | `/api/v1/vitals/history` | `?days=30` → trend records + risk history |
| `GET` | `/api/v1/ecg/history` | All past ECG sessions with thumbnails |
| `POST` | `/api/v1/sos` | Trigger SOS → nearest hospital + ambulance + guardian alert |
| `POST` | `/api/v1/ecg/report/pdf` | `{ ecg_id, language }` → pre-signed S3 PDF URL (1h TTL) |

**Sample vitals response:**
```json
{
  "risk_score": 18.4,
  "risk_tier": "elevated",
  "confidence_interval": [14.1, 22.8],
  "shap_top5": [
    { "feature": "Systolic BP", "contribution": 0.34 },
    { "feature": "Age", "contribution": 0.22 },
    { "feature": "Smoking", "contribution": 0.18 },
    { "feature": "Cholesterol", "contribution": 0.14 },
    { "feature": "BMI", "contribution": 0.09 }
  ],
  "ecg_prompt": true,
  "trend_delta": +2.1
}
```

---

## 🤖 ML Pipeline Architecture

```
                    ┌─────────────┐
                    │  ECG Image  │
                    │ (any format)│
                    └──────┬──────┘
                           │
              ┌────────────▼────────────┐
              │   OpenCV Preprocessing  │
              │ deskew → grid removal   │
              │ → 12-lead detection     │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │      NeuroKit2          │
              │ Signal extraction per   │
              │ lead → 500Hz resample   │
              │ → normalize [-1, 1]     │
              └──────┬─────────┬────────┘
                     │         │
         ┌───────────▼──┐  ┌───▼──────────────┐
         │ 1D-SE-ResNet │  │  Transformer      │
         │ (PTB-XL)     │  │  (CPSC+Georgia)   │
         │              │  │  8 heads, 6 layers│
         │ Squeeze &    │  │  Patch size=50    │
         │ Excitation   │  │  Self-attention   │
         │ blocks       │  │  on 1D patches    │
         └──────┬───────┘  └──────┬────────────┘
                │                 │
         ┌──────▼─────────────────▼──┐
         │    Soft-Vote Ensemble      │
         │  P = α·SE + (1-α)·Trans   │
         │  α learned per condition  │
         └──────────────┬────────────┘
                        │
              ┌──────────▼──────────┐
              │  15-class output    │
              │  + GradCAM saliency │
              └──────────┬──────────┘
                         │
         ┌───────────────┴───────────────┐
         │                               │
         ▼                               ▼
  LightGBM Tabular              Claude API
  ASCVD Risk Score              Report Generation
  + SHAP values                 (plain-language,
                                 English + Hindi)
         │                               │
         └───────────────┬───────────────┘
                         ▼
              ┌──────────────────────┐
              │  Risk Fusion Layer   │
              │ Final = 0.3×Tabular  │
              │       + 0.7×ECG      │
              │ STEMI override >0.85 │
              └──────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites
- Node.js ≥ 18, npm ≥ 9
- Python ≥ 3.11
- Docker + Kubernetes (for backend microservices)
- Gemini API key
- Google Maps API key

### Frontend Setup

```bash
# Clone the repo
git clone https://github.com/Adhya08/Cardiac_Analyst.git
cd Cardiac_Analyst

# Install dependencies
npm install

# Set environment variables
cp .env.example .env.local
# Fill in: VITE_API_BASE_URL, VITE_GOOGLE_MAPS_KEY

# Start development server
npm run dev

# Build for production
npm run build
```

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL=postgresql://...
export REDIS_URL=redis://...
export AWS_REGION=ap-south-1
export ANTHROPIC_API_KEY=sk-ant-...
export GOOGLE_MAPS_KEY=...

# Run a single service (example: vitals)
uvicorn vitals_service.main:app --reload --port 8001

# Or with Docker Compose
docker-compose up
```

---

## 🏆 Advantages

### Clinical
- **15 cardiac conditions** detected in a single ECG upload — more than any comparable consumer tool
- **≥97% STEMI sensitivity** target via SE-ResNet + Transformer ensemble with clinical override rules
- **Explainable AI** — SHAP charts and GradCAM heatmaps so users and clinicians understand *why* a risk score was generated
- **Indian cohort calibration** — re-fitted on INTERHEART South Asia data for accuracy on Indian demographics

### Technical
- **Zero install barrier** — Progressive Web App accessible via any browser URL; no App Store review cycles
- **Offline emergency resilience** — Service Worker caches the hospital list and SOS page; emergency mode works without internet
- **Multi-format ECG support** — accepts images, PDFs, and CSV exports from consumer wearables (KardiaMobile, Apple Watch)
- **GPU inference in under 8 seconds** P95 latency via AWS SageMaker endpoints
- **Horizontally scalable** — each microservice scales independently on Kubernetes

### User Experience
- **Plain-language AI reports** in English and Hindi, generated by Claude — patients can understand findings without a medical degree
- **One-tap SOS** visible on every single page — no hunting for emergency features in a crisis
- **Family Guardian alerts** — designated contacts receive GPS + status automatically in an emergency
- **Clinic embed widget** — hospitals can embed the tool directly in their own web portals

---

---

## 📚 Key Datasets & References

- [PTB-XL ECG Dataset](https://physionet.org/content/ptb-xl/) — PhysioNet
- [CPSC 2018 ECG Challenge](http://2018.icbeb.org/Challenge.html)
- [Georgia 12-lead ECG Challenge](https://physionet.org/content/georgia-ecg-databasev/)
- [INTERHEART South Asia Study](https://doi.org/10.1016/S0140-6736(04)17018-9)
- [NeuroKit2](https://github.com/neuropsychology/NeuroKit) — ECG signal processing
- [SHAP](https://github.com/slundberg/shap) — Model explainability

---

## 👤 Author

**Adhya08 (Adhya Kulshreshtha) & CyberFocus2410 (Vivan Mittal)**  
Built with AI assistance — React, FastAPI, TensorFlow, and Google Gemini.

---

> ⚠️ **Medical Disclaimer:** Cardiac Analyst is an AI-assisted screening tool intended to support — not replace — professional medical diagnosis. Always consult a qualified cardiologist for medical decisions. In a cardiac emergency, call 112 immediately.
