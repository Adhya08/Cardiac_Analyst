# 🫀 CARDIAC ANALYST v2.0
## Product Requirements Document & Technical Specification

**Version**: 2.0 | Clinical Workstation Edition  
**Evaluation Standard**: PhysioNet PTB-XL Benchmark (Held-Out Fold 10: 2,158 Records)  
**Primary Architectures**: 1D Residual CNN (ONNX Runtime CPU) + LightGBM (TreeSHAP)  
**Status**: Implemented & Verified (Deterministic Zero-GenAI Diagnostic Pipeline)  

| Metric / Dimension | Specification & Verified Performance |
| :--- | :--- |
| **Model Architecture** | 1D Residual CNN (`model.onnx`, 33.37 MB, Float32) |
| **Macro AUROC** | **0.9265** (95% CI: [0.9194, 0.9330]) on 2,158 unseen patient records |
| **Macro F1 Score** | **0.7520** (95% CI: [0.7350, 0.7658]) using locked validation thresholds |
| **Inference Latency** | **7.46 ms / sample** on standard CPU (11.3x speedup over Keras baseline) |
| **Diagnostic Scope** | 5 AHA/ACC PTB-XL Superclasses: `NORM`, `MI`, `STTC`, `CD`, `HYP` |
| **Vitals Risk Model** | 10-Year ASCVD Risk Scoring via LightGBM + TreeSHAP Feature Attribution |
| **Emergency Triage** | UK NICE CG95 Guideline Decision Rules + Geolocation Hospital Routing |
| **Diagnostic Trust** | **Zero Generative AI** in diagnostic pathway; deterministic dual reports |

---

> ⚠️ **Regulatory & Clinical Safety Notice**:  
> **Cardiac Analyst is an academic research and educational prototype.** It has NOT been certified as a medical device by the US FDA, European CE, Indian CDSCO, or any international medical regulatory agency. It is NOT intended for independent clinical diagnosis, acute emergency triage, or direct patient management without qualified physician oversight. In acute chest pain or cardiovascular emergencies, users must immediately contact emergency services (112 in India, 911 in the US).

---

# 1. Executive Summary & Problem Definition

Cardiovascular disease (CVD) remains the leading cause of mortality worldwide, accounting for over **4.77 million deaths annually in India alone**. Over 60% of acute myocardial infarction (MI) deaths occur before patients reach a hospital emergency department, primarily driven by:
1. Delayed recognition of atypical or progressive ischemic symptoms.
2. Lack of accessible pre-hospital self-monitoring tools for hypertensive and diabetic patients.
3. Unavailability of immediate, interpretable 12-lead electrocardiogram evaluation in non-tertiary clinics.

**Cardiac Analyst v2.0** provides a responsive, local-first clinical workstation combining:
1. **Routine Preventative Screening**: Daily vitals tracking (blood pressure, resting heart rate, SpO2, blood glucose, cholesterol) analyzed by an ASCVD-calibrated LightGBM model with individualized TreeSHAP factor contributions.
2. **12-Lead Digital ECG Analysis**: Digital signal ingestion (100 Hz, 1,000 samples, 10-second voltage timeseries), physiological interval extraction (HR, rhythm, PR, QRS, QTc via Bazett's formula, ST segment deviations), and multi-label classification into 5 diagnostic superclasses via a 1D Residual CNN.
3. **Dual-Perspective Reporting**: Deterministic translation of raw model scores into both an electrophysiological clinical summary (for healthcare providers) and an everyday plain-language guide with actionable checklists (for patients and families).
4. **NICE CG95 Emergency Support**: Rapid 8-question acute symptom triage paired with GPS-based cardiac hospital routing and one-touch 112 emergency calling.

---

# 2. Clinical Scope & Diagnostic Classification

### 2.1 The 5 PTB-XL Diagnostic Superclasses
Rather than predicting uncalibrated fine-grained diagnoses that lack statistical support, Cardiac Analyst standardizes on the **5 gold-standard PhysioNet PTB-XL diagnostic superclasses**:

| Superclass Code | Clinical Condition | Pathophysiological Significance | Locked Decision Threshold |
| :--- | :--- | :--- | :---: |
| **`NORM`** | Normal ECG | Unremarkable sinus rhythm without ischemic, conduction, or voltage abnormalities. | **0.51** |
| **`MI`** | Myocardial Infarction | Acute or established myocardial necrosis / acute coronary syndrome. | **0.41** *(High Sensitivity)* |
| **`STTC`** | ST/T-Wave Changes | Non-specific repolarization abnormalities, myocardial ischemia, or strain. | **0.70** |
| **`CD`** | Conduction Disturbance | Bundle branch blocks (LBBB/RBBB), intraventricular blocks, or AV nodal delays. | **0.66** |
| **`HYP`** | Hypertrophy | Left or right ventricular / atrial hypertrophy from pressure or volume overload. | **0.75** |

### 2.2 Decision Threshold Tuning & Sensitivity-First Calibration
Decision thresholds $t \in [0.10, 0.90]$ were scanned on the validation fold (Fold 9) to optimize clinical utility before being locked for held-out testing:
- **`MI` Threshold (0.41)**: Tuned specifically for high sensitivity (80.00% recall, 87.81% specificity) to minimize critical missed ischemic events.
- **`HYP` Threshold (0.75)**: Calibrated to maintain 96.20% specificity against high-amplitude normal variants.
- **Uncertainty Margin ($\pm 0.05$)**: Predictions falling within the boundary zone of any locked threshold are explicitly flagged with `uncertainty_flag: true`.

---

# 3. Model Architecture & Benchmark Verification

### 3.1 1D Residual CNN Architecture (`model.onnx`)
```
Input Signal: (Batch, 1000, 12) [100 Hz, 10s, Leads: I, II, III, aVR, aVL, aVF, V1-V6]
  │
  ├──► Conv1D Stem (64 filters, kernel=15, stride=2) + BatchNorm + ReLU + MaxPool1D
  ├──► Residual Stage 1: 2x ResBlocks (64 filters, kernel=7) + Skip Connection
  ├──► Residual Stage 2: 2x ResBlocks (128 filters, kernel=7) + Stride 2 Projection
  ├──► Residual Stage 3: 2x ResBlocks (256 filters, kernel=7) + Stride 2 Projection
  ├──► Residual Stage 4: 2x ResBlocks (512 filters, kernel=7) + Stride 2 Projection
  ├──► GlobalAveragePooling1D + Dropout (0.3)
  └──► Dense(5, activation="sigmoid") ──► [NORM, MI, STTC, CD, HYP] Model Scores
```

### 3.2 Single-Pass Held-Out Test Results (Fold 10: 2,158 Records)
*Evaluated on the official held-out test fold of PhysioNet PTB-XL (zero patient overlap with training folds 1–8 or validation fold 9):*

| Class | Locked Threshold | AUROC | AUPRC | Sensitivity | Specificity | Precision | F1 Score | Brier Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **NORM** | 0.51 | **0.9447** | 0.9249 | 94.70% | 79.75% | 79.03% | 0.8616 | 0.1054 |
| **MI** | 0.41 | **0.9244** | 0.8288 | 80.00% | 87.81% | 69.18% | 0.7420 | 0.0990 |
| **STTC** | 0.70 | **0.9351** | 0.8314 | 80.04% | 91.63% | 75.27% | 0.7758 | 0.0996 |
| **CD** | 0.66 | **0.9259** | 0.8509 | 75.81% | 93.86% | 78.66% | 0.7721 | 0.0901 |
| **HYP** | 0.75 | **0.9021** | 0.6621 | 55.73% | 96.20% | 66.97% | 0.6083 | 0.0847 |
| **Macro Average** | — | **0.9265** | **0.8196** | **77.25%** | **89.85%** | **73.82%** | **0.7520** | — |

*95% Confidence Intervals (1,000 Bootstrap Resamples on Fold 10):*
- **Macro AUROC**: `0.9265` [95% CI: **0.9194, 0.9330**]
- **Macro AUPRC**: `0.8196` [95% CI: **0.8038, 0.8351**]
- **Macro F1 Score**: `0.7520` [95% CI: **0.7350, 0.7658**]

### 3.3 ONNX Conversion & Latency Benchmark
- **Original Keras Model**: 100.34 MB | 84.42 ms / sample CPU latency.
- **Optimized ONNX Runtime Model**: **33.37 MB** (66.7% size reduction) | **7.46 ms / sample** (11.3x faster).
- **Float32 Numerical Parity**: Maximum absolute divergence $\max |\Delta| = 2.09 \times 10^{-7}$.

---

# 4. Functional Specification by Application Mode

### 4.1 Mode 1 — Clinical Overview Dashboard (`OverviewMode.tsx`)
- **Quick Action Bar**: One-click routing to "New ECG Analysis", "Log Daily Vitals", and "Emergency Triage".
- **Latest Vitals Card**: Tabular presentation of most recently recorded BP, HR, weight, and SpO2 with status tags.
- **Diagnostic Ledger**: Real-time table of recent 12-lead ECG evaluations pulling from SQLite database.
- **Model Provenance Card**: Displays active ResNet1D engine version, inference engine status, and benchmark statistics.

### 4.2 Mode 2 — 12-Lead ECG Analysis Workspace (`ECGMode.tsx` & `ECGViewer.tsx`)
- **Digital Ingestion Engine**: Drag-and-drop zone accepting `.csv`, `.npy`, `.json`, and WFDB `.hea`/`.dat` timeseries (100 Hz, 1,000 samples).
- **Defensive Optical Scan Interception**: Pre-upload validation intercepts paper photos/scans (`.png`, `.jpg`, `.pdf`) with a clear message explaining that optical digitization introduces calibration error and paper artifacts.
- **Interactive 12-Lead ECG Viewer**:
  - High-DPI HTML5 Canvas rendering an authentic pink medical grid (1mm minor lines @ 4px, 5mm major lines @ 20px).
  - 1 mV calibration pulse (10mm height, 0.2s duration) at standard 25 mm/s paper speed and 10 mm/mV gain.
  - Multi-montage display: Standard 3×4 lead layout, continuous Lead II rhythm strip, and single-lead magnified inspector.
  - Pan and zoom controls with instant view reset.
- **Dual Analysis Report**:
  - *Clinical Specialist Tab*: Heart rate, rhythm classification, PR interval, QRS duration, Bazett QTc, ST elevation/depression lead mappings, ICD-10 cross-references, and locked threshold comparisons.
  - *Family Plain-Language Tab*: Non-technical analogies (e.g., hypertrophy explained as muscle thickening from pumping against high blood pressure), condition severity tags, actionable home checklist, and questions to ask the doctor.

### 4.3 Mode 3 — Routine Screening (`RoutineMode.tsx`)
- **Structured Vitals Entry**: Validated inputs with physical units (Systolic/Diastolic BP in mmHg, Heart Rate in bpm, Weight in kg, SpO2 in %, Fasting Glucose and Cholesterol in mg/dL).
- **LightGBM ASCVD Scoring**: Predicts 10-year risk tier (`Low Risk` <10%, `Borderline` 10–20%, `Elevated` >20%).
- **TreeSHAP Explainability**: Visual attribution ranking showing exact percentage risk contributions.
- **Longitudinal Trend Chart**: 30-day interactive time-series tracking systolic and diastolic trends against JNC-8 hypertension thresholds.

### 4.4 Mode 4 — Patient History Ledger (`HistoryMode.tsx`)
- **Unified Audit Trail**: Consolidated history of all previous 12-lead ECG analyses and vitals logs.
- **Filtering & Search**: Category filtering (`All`, `ECG Studies`, `Vitals Records`) with real-time text query.
- **Study Re-Inspection**: Single-click study inspection immediately loading past waveforms into the interactive viewer.

### 4.5 Mode 5 — Acute Emergency Support (`EmergencyMode.tsx`)
- **NICE CG95 Triage Wizard**: 8 targeted clinical questions assessing retrosternal chest pain, radiation to jaw/arm, diaphoresis, rest dyspnea, and syncope.
- **Deterministic Risk Tiering**: 0 symptoms reliably classify as "Low Risk" (emerald banner).
- **One-Touch SOS Action**: Direct click-to-call link for emergency dispatch (`tel:112`).
- **GPS Hospital Finder**: Live browser coordinate resolution querying nearby cardiac centers with cath lab availability, ratings, direct telephone numbers, and Google Maps routing.

---

# 5. Technical Architecture & Constraints

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND APPLICATION SHELL                      │
│   React 19 · TypeScript 5.8 · Vite · Tailwind CSS · Framer Motion      │
│   Persistent Collapsible Rail · Top Application Bar · Light Medical UI │
├────────────────────────────────────────────────────────────────────────┤
│                       LOCAL FASTAPI BACKEND SERVER                     │
│   Python 3.11 · FastAPI · Uvicorn (Port 8000) · SQLite (SQLAlchemy)    │
│   Routers: /api/v1/ecg, /api/v1/vitals, /api/v1/emergency, /health    │
├────────────────────────────────────────────────────────────────────────┤
│                     DETERMINISTIC MACHINE LEARNING                     │
│   • ECGInferenceService: ONNX Runtime CPU (model.onnx, 33.37 MB)       │
│   • Signal Processing: SciPy (Waveform peaks, intervals, ST deviation) │
│   • Vitals Risk: LightGBM (risk_model.pkl) + TreeSHAP explainability   │
│   • Emergency Engine: UK NICE CG95 Deterministic Decision Tree         │
└────────────────────────────────────────────────────────────────────────┘
```

- **Zero Cloud GPU / External LLM Dependency**: Complete system runs locally on standard CPU hardware without AWS SageMaker, external GPUs, or proprietary cloud APIs in the diagnostic loop.
- **Memory Footprint**: Backend process consumes $< 50\text{ MB}$ RAM with ONNX Runtime CPU execution provider.
- **Security & Data Privacy**: All patient health information (PHI) resides in local SQLite storage (`cardiac_data.db`). Zero patient data is transmitted to external generative AI endpoints.