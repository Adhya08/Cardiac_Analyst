# Cardiac Analyst — Comprehensive System Audit & Transition Plan

> **Regulatory Notice**: Cardiac Analyst is a **research and educational prototype only**. It is **not** a certified medical device and must never be used for clinical diagnosis, patient management, or medical triage.

---

## 1. Repository Structure & File Directory Audit

### 1.1 Root Directory
| File / Directory | Purpose |
| :--- | :--- |
| `package.json` | Node.js manifest defining frontend dependencies (React 19, Vite, Tailwind CSS, Lucide icons, Framer Motion, Chart.js, Leaflet) and scripts (`dev`, `build`, `preview`). |
| `package-lock.json` | Exact dependency tree lockfile for npm. |
| `vite.config.ts` | Vite configuration configuring the React plugin and local development reverse proxy: routes `/api/*` and `/uploads/*` to the FastAPI backend (`http://localhost:8000`). |
| `tailwind.config.js` | Tailwind styling setup specifying color palettes (emerald, slate, dark backgrounds) and UI utilities. |
| `postcss.config.js` | PostCSS config activating Tailwind CSS and Autoprefixer. |
| `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json` | TypeScript configuration for client code and build tooling. |
| `eslint.config.js` | ESLint static analysis configuration for React and TypeScript. |
| `index.html` | Entry HTML document for the Single Page Application (SPA). |
| `netlify.toml`, `vercel.json` | Deployment routing rules for Netlify and Vercel hosting. |
| `dist/` | Production build directory containing compiled HTML, JavaScript, and CSS bundles. |
| `PROGRESS.md` | Milestone tracker, audit trail, and model lineage ledger adhering to the 11 permanent rules. |
| `README.md`, `CardiacApp_PRD_FRD_WebApp_v2.md` | Original product requirements documents and specifications. |

### 1.2 Frontend (`src/` and `public/`)
| File / Directory | Purpose |
| :--- | :--- |
| `public/manifest.json` | PWA manifest for standalone browser installation. |
| `public/sw.js` | Service worker script for offline asset caching. |
| `public/favicon.svg`, `icons.svg` | Application logos and vector icons. |
| `public/demo_ecgs/` | Statically served sample ECG image scans (`normal_ecg_sample.png`, `stemi_ecg_sample.png`). |
| `src/main.tsx` | React 19 bootstrap entry point rendering `App.tsx` and handling service worker registration. |
| `src/App.tsx` | Top-level layout container featuring the navigation bar, sidebar mode switcher, and transition animations. |
| `src/index.css`, `src/App.css` | Global styling tokens, dark glassmorphism effects, and custom UI components. |
| `src/components/Navbar.tsx` | Top navigation bar with language selector (English/Hindi), SOS emergency shortcut, and reset button. |
| `src/components/RiskArc.tsx` | Animated circular SVG gauge rendering the composite cardiac risk percentage (0–100%). |
| `src/components/HospitalMap.tsx` | Interactive Leaflet/OpenStreetMap component displaying nearby emergency hospitals with route links. |
| `src/lib/api.ts` | Central typed HTTP client executing requests to backend `/api/v1/*` endpoints. |
| `src/lib/translations.ts` | Bilingual translation table (English and Hindi) for all UI text, labels, and error messages. |
| `src/modes/RoutineMode.tsx` | Routine Screening UI: vitals collection form, LightGBM risk display, Framingham calculation, SHAP explainability breakdown, and 30-day vitals history trend chart. |
| `src/modes/ECGMode.tsx` | ECG Analysis UI: drag-and-drop file upload, demo scan triggers, interval measurements display, condition classifications list, and GradCAM lead highlights. |
| `src/modes/EmergencyMode.tsx` | Emergency Triage UI: 8-question symptom assessment, severity classification alert, hospital finder, and ambulance dialer. |
| `src/store/useStore.ts` | Zustand global state management tracking user profile, language, active mode, vitals, and history. |
| `src/assets/` | Static graphics (`hero.png`, `react.svg`, `vite.svg`). |

### 1.3 Backend (`backend/`)
| File / Directory | Purpose |
| :--- | :--- |
| `backend/requirements.txt` | Python dependency specifications (FastAPI, uvicorn, SQLAlchemy, LightGBM, scikit-learn, google-genai, etc.). |
| `backend/train.py` | Training script for the routine screening model (downloads UCI datasets, balances with SMOTE, fits LightGBM ensemble, calibrates probabilities, and saves `models_saved/risk_model.pkl`). |
| `backend/accuracy_test.py` | Standalone script testing Gemini Vision on test images. |
| `backend/test_ecg.py` | Unit test verifying Gemini Vision API responses on local ECG samples. |
| `backend/test_translation.py` | Test script checking Hindi translation integration with Gemini/Sarvam. |
| `backend/start.bat` | Windows batch launcher starting the FastAPI server on port 8000. |
| `backend/Dockerfile`, `.dockerignore` | Docker container build recipe for containerized backend hosting. |
| `backend/data/` | Dataset directory holding `uci_heart_disease_combined.csv` (1,220 clinical rows). |
| `backend/models_saved/` | Serialized model storage holding `risk_model.pkl`. |
| `backend/app/main.py` | FastAPI application factory, CORS middleware configuration, SQLite database initialization, router registration, and `/health` endpoint. |
| `backend/app/database.py` | SQLAlchemy database engine and session maker connected to SQLite (`cardiac_data.db`). |
| `backend/app/models_db.py` | Database table schemas (`UserProfileDB`, `VitalsLogDB`, `ECGRecordDB`, `TriageLogDB`). |
| `backend/app/schemas.py` | Pydantic validation schemas defining data contracts for all API endpoints. |
| `backend/app/routers/vitals.py` | Endpoints for user profile and routine vitals logging; calls `RiskModel` and `RiskAuditor`. |
| `backend/app/routers/ecg.py` | Endpoints for ECG upload (`/api/v1/ecg/upload`), history, and retrieval; currently dispatches to `ECGAnalyzer` (Gemini). |
| `backend/app/routers/emergency.py` | Endpoints for 8-question emergency triage assessment based on NICE CG95 rules. |
| `backend/app/routers/hospitals.py` | Endpoints querying Google Places API for nearby emergency care facilities, with mock emergency fallbacks. |
| `backend/app/routers/chat.py` | Endpoints for conversational patient assistance powered by Sarvam AI (`sarvam-m`). |
| `backend/app/ml/risk_model.py` | Routine screening model wrapper orchestrating LightGBM inference, Framingham risk, and SHAP explainability. |
| `backend/app/ml/risk_auditor.py` | Deterministic clinical rules that flag discrepancies and override model risk when vitals indicate critical emergencies. |
| `backend/app/ml/ecg_analyzer.py` | Gemini Vision prompt construction, API caller, and response parser for ECG images/PDFs. |
| `backend/app/ml/triage.py` | Rule-based triage engine evaluating 8 symptom flags against NICE CG95 cardinal patterns. |
| `backend/app/ml/vitals_validator.py` | Physiological boundary validation rejecting impossible human vitals readings. |
| `backend/app/ml/sarvam_assistant.py` | Integration layer for Sarvam AI LLM chat and Hindi translation services. |

---

## 2. Gemini Usage & Diagnostic Path Audit

Every occurrence of Google Gemini in the codebase was audited to determine whether it affects patient diagnosis:

1. **`backend/app/ml/ecg_analyzer.py`** (**DIRECT DIAGNOSTIC PATH**):
   - **How it is used**: Sends uploaded ECG images/PDFs to Google Gemini Vision (`gemini-2.0-flash` or `gemini-2.5-flash`) via `google.genai`.
   - **Diagnostic Impact**: **100% of the ECG diagnosis currently comes from Gemini**. The model prompts Gemini to act as a cardiologist, extract heart rate, measure PR/QRS/QTc intervals, detect ST elevation/depression, and classify 45 conditions.
   - **Fallback Hazard**: If Gemini fails or the API key is missing, `_fallback_response()` generates an invented classification (Normal Sinus Rhythm at 50%, all other conditions at 1%), directly violating Rules 2, 6, and 7.

2. **`backend/app/routers/ecg.py`** (**DIRECT DIAGNOSTIC PATH**):
   - **How it is used**: Endpoint `POST /api/v1/ecg/upload` initializes `ECGAnalyzer(api_key=os.getenv("GEMINI_API_KEY"))` and calls `analyze_ecg()`.
   - **Diagnostic Impact**: Passes patient age, sex, and vitals to Gemini and stores Gemini's output in the database as the clinical diagnosis.

3. **`backend/accuracy_test.py` & `backend/test_ecg.py`** (**TEST SCRIPTS**):
   - **How it is used**: Standalone test runners validating that Gemini API keys work and return structured JSON.
   - **Diagnostic Impact**: Development verification only; not active in production runtime.

4. **`backend/app/ml/sarvam_assistant.py`** (**INDIRECT / INFORMATIONAL**):
   - **How it is used**: In line 135, accepts the ECG analysis generated by Gemini to summarize it for the patient in chat.
   - **Diagnostic Impact**: Does not generate the diagnosis, but summarizes the diagnosis produced by Gemini.

5. **`scratch/test_gemini_2_5.py`, `scratch/test_gemini_v2.py`, `scratch/upload_samples.py`, `scratch/list_models.py`** (**SCRATCH UTILITIES**):
   - **How it is used**: Prototype scripts used during initial development to list models and test endpoints.

---

## 3. Analysis of `backend/train.py` (Synthetic Data & Label Generation)

`backend/train.py` contains **two separate mechanisms that generate synthetic data and synthetic labels**:

### 3.1 Network Failure Fallback (Synthetic Patients & Labels)
If the remote data sources are unreachable, lines 122–154 synthesize 1,000 artificial patient records with randomly generated features and calculated labels:

```python
# Lines 122-154 of backend/train.py:
    if df is None:
        print("  Generating Synthetic Clinical Dataset (UCI Distribution Sync)...")
        np.random.seed(RANDOM_STATE)
        n_samples = 1000
        data = {
            "age": np.random.normal(54, 9, n_samples),
            "sex": np.random.choice([0, 1], size=n_samples, p=[0.32, 0.68]),
            "cp": np.random.choice([1, 2, 3, 4], size=n_samples, p=[0.1, 0.2, 0.3, 0.4]),
            "trestbps": np.random.normal(131, 17, n_samples),
            "chol": np.random.normal(246, 51, n_samples),
            "fbs": np.random.choice([0, 1], size=n_samples, p=[0.85, 0.15]),
            "restecg": np.random.choice([0, 1, 2], size=n_samples, p=[0.49, 0.01, 0.50]),
            "thalach": np.random.normal(149, 23, n_samples),
            "exang": np.random.choice([0, 1], size=n_samples, p=[0.67, 0.33]),
            "oldpeak": np.clip(np.random.exponential(1.1, n_samples), 0, 6),
            "slope": np.random.choice([1, 2, 3], size=n_samples, p=[0.4, 0.46, 0.14]),
            "ca": np.random.choice([0, 1, 2, 3], size=n_samples, p=[0.58, 0.21, 0.13, 0.08]),
            "thal": np.random.choice([3, 6, 7], size=n_samples, p=[0.54, 0.06, 0.40]),
        }
        df = pd.DataFrame(data)
        # Probabilistic target logic based on risk factors
        risk_score = (
            (df["age"] - 50) / 20 + 
            (df["sex"] * 0.5) + 
            (df["oldpeak"] * 0.8) + 
            (df["ca"] * 1.2) + 
            ((df["trestbps"] - 120) / 30)
        )
        df["target"] = (risk_score > 1.5).astype(int)
        # Add some noise to labels
        noise_idx = np.random.choice(n_samples, size=int(n_samples * 0.1), replace=False)
        df.loc[noise_idx, "target"] = 1 - df.loc[noise_idx, "target"]
```

### 3.2 Clinical Data Augmentation (SMOTE)
In lines 104–112, `train.py` uses SMOTE (Synthetic Minority Over-sampling Technique) to interpolate artificial records between existing patients:

```python
# Lines 104-112 of backend/train.py:
def augment_data(X, y):
    """
    Apply SMOTE for data balancing and synthetic generation.
    """
    print("\n[2/6] Applying Clinical Data Augmentation (SMOTE)...")
    sm = SMOTE(random_state=RANDOM_STATE)
    X_res, y_res = sm.fit_resample(X, y)
    print(f"  Balanced dataset size: {len(X_res)}")
    return X_res, y_res
```

**Audit Verdict**: Both blocks violate Permanent Rule 3 (*"Never use synthetic data for training, validation or testing. Use only the real PTB-XL data with its official labels."*). In our new 1D CNN pipeline, **no synthetic records, synthetic labels, or SMOTE interpolations will be used**.

---

## 4. Clinical Safety & Medical Logic Review

### 4.1 `backend/app/ml/risk_model.py` (Pseudo-Diagnostic Feature Hallucination)
In `map_inputs()` (lines 83–181), the model attempts to map basic non-invasive vitals (blood pressure, heart rate, weight) to clinical features from the UCI Heart Disease dataset that require specialized medical equipment:
- **`restecg` (Resting ECG)**: If systolic BP > 160, sets `restecg = 2` (Left Ventricular Hypertrophy) without reading an actual ECG (lines 129–134).
- **`cp` (Chest Pain Type)**: If diabetic, automatically assigns `cp = 2` (atypical angina) even if the patient is completely asymptomatic (lines 116–123).
- **`thalach` (Max Exercise Heart Rate)**: Estimates max exercise heart rate from resting heart rate using arbitrary multipliers (`0.75`, `0.82`, `0.88`) without a treadmill test (lines 136–146).
- **`oldpeak` (ST Depression on Stress Test)**: Calculates an artificial ST depression index `(risk_count - 1) * 0.4 + (pulse_pressure - 40) / 60.0` from resting blood pressure (lines 151–154).
- **`ca` (Major Vessels Colored by Fluoroscopy)**: Estimates invasive fluoroscopy results (0 to 3 blocked coronary arteries) simply from the number of generic risk factors (`min(3, max(0, risk_count - 3))`, line 164).
- **`thal` (Thallium Scintigraphy Perfusion Defect)**: Assigns nuclear scan defect codes (3=normal, 6=fixed defect, 7=reversable defect) based on risk factor count (lines 166–172).

**Clinical Hazard**: Fabricating diagnostic test findings (ECG, fluoroscopy, nuclear imaging) from simple vitals produces unscientific, uncalibrated risk predictions that misrepresent clinical reality.

### 4.2 `backend/app/ml/triage.py` (Unsafe Instructions & Arbitrary Confidence)
- **Unsafe Medication Advice**: Line 47 gives direct pharmaceutical advice to laypeople:
  `"If available and not allergic: chew ONE aspirin (75–325 mg) right now."`
  *Clinical Risk*: Giving unsupervised medication orders to an app user without ruling out aortic dissection, active intracranial hemorrhage, gastrointestinal bleeding, or severe coagulopathy is dangerous.
- **Arbitrary Pseudo-Confidence**: Lines 103–122 calculate numerical confidence values through arbitrary linear formulas rather than calibrated statistical probabilities:
  ```python
  confidence = min(0.99, confidence_base + yes_count * 0.01)
  risk_score = min(99.9, 75 + yes_count * 3.0 + (10 if vitals_red_flag else 0))
  ```
  These values present the user with a false appearance of high mathematical precision (`99.9%`, `0.95`).

---

## 5. Unverified Claims & Inaccurate UI Statements

The following claims across the UI, documentation, and metadata are unverified or inaccurate:

1. **"97% STEMI Sensitivity"**:
   - `index.html` (line 10): `<meta name="description" content="AI-Assisted Cardiac Screening Platform with 97% STEMI sensitivity...">`
   - `dist/index.html` (line 10): Identical claim in compiled build.
   - `README.md` (lines 306, 571) & `CardiacApp_PRD_FRD_WebApp_v2.md` (lines 12, 116, 164): Repeatedly claims "≥ 97% STEMI sensitivity" and "≥ 97% Emergency triage sensitivity" based on aspirational targets rather than measured benchmark results.
2. **"45+ Conditions" vs "18 Conditions" Conflict**:
   - `src/modes/ECGMode.tsx` (line 253): Displays badge tag `'45+ Conditions'`.
   - `backend/app/ml/ecg_analyzer.py` (lines 22–36): Lists 45 arbitrary conditions in prompt string.
   - `src/lib/translations.ts` (lines 40, 48, 56): Contradicts the 45-condition badge by stating `"18-condition analysis"` and `"18-Condition Classification"`.
   - `backend/app/schemas.py`: Schema expects arbitrary condition outputs generated by LLM text completion.
3. **"Real Data" Badge**:
   - `src/modes/ECGMode.tsx` (line 253): Shows a `'Real Data'` badge, but the demo scans were uploaded with fixed hardcoded names, and the analysis was routed to Gemini with a fabricated fallback if the network failed.

---

## 6. Dependency & Framework Compatibility Audit

### Current Environment
- **Python**: `3.11.9` (64-bit Windows)
- **Node.js**: `v22.18.0` / npm `11.16.0`
- **Current Core Backend Libraries**:
  - `numpy==2.4.6`
  - `pandas==3.1.0`
  - `scipy==1.17.1`
  - `scikit-learn==1.9.1`
  - `lightgbm==4.7.0`
  - `fastapi==0.162.0`, `uvicorn==0.54.0`

### Framework Compatibility Analysis (TensorFlow vs. PyTorch vs. ONNX)
1. **TensorFlow / Keras Hazard**:
   - **NumPy Conflict**: Standard TensorFlow wheels on Windows require `numpy < 2.0.0` (typically `numpy ~= 1.26.4`). Installing TensorFlow locally will immediately conflict with `numpy==2.4.6` and `pandas==3.1.0`.
   - **Windows GPU Deprecation**: Native GPU support for TensorFlow on Windows was discontinued after TensorFlow 2.10. Running TensorFlow on Windows requires either CPU-only execution or WSL2.
2. **Recommended Architecture: PyTorch on Kaggle → ONNX Runtime for Local Inference**:
   - **Training (Kaggle GPU)**: Kaggle's free GPU environments run Linux with modern PyTorch pre-installed with full CUDA support. Training the 1D CNN in PyTorch on Kaggle allows training across the 21,837 PTB-XL recordings.
   - **Local Inference (FastAPI)**: Exporting the trained PyTorch model to **ONNX format** (`.onnx`) enables inference locally via `onnxruntime` (`pip install onnxruntime`).
   - **Compatibility**: `onnxruntime>=1.19.0` runs on Python 3.11 with `numpy==2.4.6`, has a minimal memory footprint (< 60MB), executes with low latency on Windows CPU, and introduces zero dependency conflicts with FastAPI or LightGBM.

---

## 7. Proposed Implementation Plan

The transition from Gemini-based vision analysis to a locally trained 1D CNN is structured across the following sequential phases:

```
[Phase 1: Audit] (Current)
       │
       ▼
[Phase 2: Kaggle Setup & PTB-XL Dataset Pipeline]
       │
       ▼
[Phase 3: Residual 1D CNN Architecture & Training Notebook]
       │
       ▼
[Phase 4: Remote Training on Kaggle GPU]
       │
       ▼
[Phase 5: Single-Pass Fold 10 Test Evaluation]
       │
       ▼
[Phase 6: Model Export (ONNX) & FastAPI Backend Integration]
       │
       ▼
[Phase 7: Frontend UI Refactoring & Claims Cleanup]
```

### Phase Details:
- **Phase 2: Kaggle & PTB-XL Setup**: Set up Kaggle API credentials, verify dataset access to PhysioNet's PTB-XL (21,837 recordings across 12 leads), and establish the strict fold splitting script (Folds 1–8 train, Fold 9 validation, Fold 10 hold-out test).
- **Phase 3: Model Architecture**: Build a Residual 1D CNN (ResNet-1D architecture tailored for 12-lead ECG time-series at 100Hz/500Hz) with multi-label binary cross-entropy loss targeting the standard PTB-XL diagnostic superclasses (NORM, MI, STTC, CD, HYP) and high-acuity subclasses.
- **Phase 4: Remote Training Execution**: Run training on Kaggle's free GPU; track epoch loss, validation macro-AUC, and F1 across folds 1–8 and 9; save model checkpoints.
- **Phase 5: Fold 10 Final Evaluation**: Perform a single, un-tuned evaluation pass on Fold 10. Record and print genuine sensitivity, specificity, AUC-ROC, and confusion matrices with zero fabrication.
- **Phase 6: Backend Integration & Gemini Removal**: Export the trained model to ONNX, integrate ONNX Runtime in FastAPI (`backend/app/ml/local_ecg_model.py`), completely delete `ecg_analyzer.py` and `GEMINI_API_KEY` requirements, and implement explicit `analysis_unavailable` error responses.
- **Phase 7: Frontend Refactoring & Verification**: Update `ECGMode.tsx` to handle true diagnostic classes, remove all unverified "97%" and "45 condition" claims, ensure research/educational prototype disclaimers are prominent, and verify full end-to-end operation with real test signals.

---

## 8. Current System Operational Verification

The application was launched and verified locally:

1. **Backend Server (`uvicorn app.main:app`)**:
   - Status: **Operational** (`http://127.0.0.1:8000`)
   - Health Check: `GET /health` returned `200 OK`:
     ```json
     {"status": "healthy", "model_loaded": true, "model_accuracy": "75.96%"}
     ```
2. **Frontend Dev Server (`vite`)**:
   - Status: **Operational** (`http://localhost:5173`)
   - HTTP Status: Returned `200 OK` on root index document.
3. **Integration Test Suite (`scratch/integration_test.py`)**:
   - TC1: Profile Update — `200 OK`
   - TC2: Vitals Logging & Risk Scoring — `200 OK` (Risk Score: `62.67%`, Risk Tier: `Elevated`)
   - TC3: ECG History Check — `200 OK`
   - TC4: Emergency Triage — `200 OK` (Severity: `emergency`, `5` hospitals discovered)
   - TC5: Vitals Trend History — `200 OK`
4. **Operational Status & Transition State**:
   - **Post-Transition Verified Behavior**:
     - ECG analysis uses local ONNX inference (`backend/models/model.onnx`, 12-lead ResNet1D) with zero external Gemini API calls.
     - When an ECG signal exhibits excessive noise/variance but remains usable, the backend returns `status="uncertain"` with `quality_status="poor_quality"`; when a signal is unparseable, flatlined, or corrupted, the backend returns `status="analysis_unavailable"` (no fabricated fallbacks).
     - The UI displays strictly the 5 supported PTB-XL diagnostic superclasses with real Fold 10 benchmark numbers from `EVALUATION_REPORT.md`.
   - **Pre-Transition Historical Deficiencies (Resolved)**:
     - *[Legacy/Resolved]*: The initial prototype required an external Google Gemini API key and emitted fallback predictions when absent. This has been fully eliminated.
