# Real-World Clinical & Production Readiness Audit

**Audit Date:** October 26, 2026  
**Audited Target:** [Cardiac Analyst Repository](https://github.com/Adhya08/Cardiac_Analyst)  
**Evaluator:** Senior Product Designer, Clinical Software UX Specialist, & Staff Healthcare Systems Engineer  
**Scope:** Complete Codebase, Git History, Database Models, Cryptographic Boundaries, Clinical Triage Logic, and Published Claims.

---

## Executive Summary & Readiness Scorecard

| Domain | Area Audited | Severity Rating | Production Readiness Verdict |
| :--- | :--- | :---: | :--- |
| **Section 1** | Data Storage & Persistence Across Restarts | **HIGH** | **Not Ready** (Ephemeral SQLite on containers/serverless; file wipe risk) |
| **Section 2** | Authentication, JWT Validation & Record Snooping | **CRITICAL** | **Not Ready** (Unauthenticated snooping bypass; default secret fallback) |
| **Section 3** | Secret Leaks, Developer Paths & Git History | **CRITICAL** | **Not Ready** (Live Google API keys committed in historical commits `7a7de96~1` & `f54d44b~1`) |
| **Section 4** | Unbacked Claims vs. `EVALUATION_REPORT.md` | **MEDIUM** | **Requires Correction** (Contradictory AUCs in UI; unverified LightGBM claims; pseudo-GradCAM) |
| **Section 5** | System Resilience (Cold-Starts, Dormant/Failed Backend) | **HIGH** | **Partially Resilient** (UI indicates status, but no offline ECG or hospital caching) |
| **Section 6** | Emergency Clinical Safety & Downplaying Symptoms | **CRITICAL** | **Clinical Safety Hazard** (Atypical MI diaphoresis + nausea, and isolated arm pain trigger "normal/low-risk") |
| **Section 7** | Legacy LLM & Architecture Residue | **LOW** | **Remediated with Minor Residual** (`google-genai` still in `requirements.txt`) |

---

## Section 1: Where User Data is Stored and Whether it Persists

### Finding 1.1: Local SQLite File on Ephemeral Container Filesystems
- **Severity:** **HIGH**
- **Architecture & Location:**
  - Database URL defined in [`backend/app/database.py:L12`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/backend/app/database.py#L12):
    ```python
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./cardiac_data.db")
    ```
  - Tables declared in [`backend/app/models_db.py`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/backend/app/models_db.py):
    - `users`: Clinician/patient account credentials, emails, and demographic records.
    - `vitals_logs`: Longitudinal blood pressures, SpO2, heart rates, blood glucose, cholesterol, and calculated ASCVD risk scores.
    - `ecg_analyses`: Complete 12-lead diagnostic reports, superclass scores, and intervals stored as JSON.
    - `triage_events`: Triage questionnaires, symptom selections, GPS coordinates, and severity outcomes.
- **Persistence Assessment:**
  - **Local Development:** Data persists locally in `backend/cardiac_data.db` as long as the file is not deleted.
  - **Production Containers (Render, Railway, Heroku, Docker without persistent volume, Vercel Serverless):** The filesystem is **stateless and ephemeral**. Every container restart, sleep/wake cycle, or git redeployment **permanently destroys** `cardiac_data.db`. All patient records, logged vitals, and diagnostic histories are wiped.
  - **Concurrency:** SQLite uses database-level locking (`check_same_thread=False`). If two clinical requests write simultaneously in a multi-worker setup (`gunicorn/uvicorn -w 4`), SQLite throws `sqlite3.OperationalError: database is locked`.

### Finding 1.2: Uploaded Raw ECG Voltage Waveforms
- **Severity:** **HIGH**
- **Location:** [`backend/app/routers/ecg.py:L25-26`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/backend/app/routers/ecg.py#L25-L26):
  ```python
  UPLOAD_DIR = "uploads/ecg"
  os.makedirs(UPLOAD_DIR, exist_ok=True)
  ```
- **Persistence Assessment:**
  - Ingested files (CSV, NPY, JSON, WFDB) are stored on the local container disk.
  - These files are not synced to distributed object storage (e.g., AWS S3, Google Cloud Storage, or MinIO). In multi-replica cloud deployments, an ECG uploaded to Replica A is completely inaccessible to Replica B when retrieving `/uploads/{filename}`.

### Finding 1.3: Client-Side Browser Storage
- **Severity:** **LOW**
- **Location:** [`src/lib/api.ts:L183-207`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/src/lib/api.ts#L183-L207)
- **Persistence Assessment:**
  - `cardiac_auth_token`, `cardiac_auth_user`, `cardiac_routine_vitals`, and `cardiac_lang` persist in `window.localStorage`.
  - Data remains indefinitely on the specific browser profile until browser cache is cleared, but does not synchronize across clinician workstations or mobile devices.

---

## Section 2: Authentication, Authorization & Record Snooping

### Finding 2.1: Unauthenticated Guest Snooping Flaw (IDOR)
- **Severity:** **CRITICAL**
- **Real Evidence:**
  In [`backend/app/routers/vitals.py:L203-222`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/backend/app/routers/vitals.py#L203-L222):
  ```python
  @router.get("/vitals/history")
  async def get_vitals_history(
      user_id: str = Query(default="default_user"),
      days: int = Query(default=30, ge=1, le=365),
      current_user: Optional[User] = Depends(get_optional_user),
      db: Session = Depends(get_db),
  ):
      if current_user:
          if user_id != "default_user" and user_id != current_user.id and current_user.role not in ("clinician", "researcher"):
              raise HTTPException(403, detail="Access denied: Cannot access vitals of another user.")
          target_id = current_user.id if user_id == "default_user" else user_id
      else:
          target_id = user_id  # <--- FLAW: Unauthenticated request directly queries any target_id!

      since = datetime.utcnow() - timedelta(days=days)
      records = db.query(VitalsLog).filter(VitalsLog.user_id == target_id, VitalsLog.timestamp >= since)...
  ```
  And in [`backend/app/routers/ecg.py:L138-154`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/backend/app/routers/ecg.py#L138-L154):
  ```python
  @router.get("/history")
  async def get_ecg_history(
      user_id: str = "default_user",
      current_user: Optional[User] = Depends(get_optional_user),
      db: Session = Depends(get_db),
  ):
      if current_user:
          ...
      else:
          target_id = user_id  # <--- FLAW: Unauthenticated request directly queries any user_id!
  ```
  And in [`backend/app/routers/ecg.py:L168-185`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/backend/app/routers/ecg.py#L168-L185):
  ```python
  @router.get("/{ecg_id}", response_model=ECGOut)
  async def get_ecg_analysis(
      ecg_id: str,
      current_user: Optional[User] = Depends(get_optional_user),
      db: Session = Depends(get_db),
  ):
      record = db.query(ECGAnalysis).filter(ECGAnalysis.id == ecg_id).first()
      if not record:
          raise HTTPException(status_code=404, detail="ECG session not found.")
      if current_user:
          if record.user_id != "default_user" and record.user_id != current_user.id and current_user.role not in ("clinician", "researcher"):
              raise HTTPException(403, detail="Access denied...")
      # <--- FLAW: If current_user is None (no token), access control check is bypassed completely!
      result = json.loads(record.analysis_json)
      return result
  ```
- **Impact:**
  While authenticated patients are blocked from snooping on each other (`403 Forbidden` enforced if `token` is present), an attacker can simply send an **unauthenticated** request (omitting the `Authorization` header) to:
  1. `GET /api/v1/vitals/history?user_id=<VICTIM_UUID>`
  2. `GET /api/v1/ecg/history?user_id=<VICTIM_UUID>`
  3. `GET /api/v1/ecg/<ANY_ECG_UUID>`
  The API will successfully dump the victim's full medical vitals, cardiovascular risk scores, and 12-lead ECG diagnoses without requiring any credentials.

### Finding 2.2: Hardcoded Default Secret Key for JWT Signing
- **Severity:** **CRITICAL**
- **Real Evidence:**
  In [`backend/app/auth.py:L17`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/backend/app/auth.py#L17):
  ```python
  JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "cardiac-analyst-secure-clinical-key-2026")
  ```
- **Impact:**
  If the operator deploys the application without setting `JWT_SECRET_KEY` in the environment, the hardcoded fallback `"cardiac-analyst-secure-clinical-key-2026"` is used. Because this secret is public in open-source code, any attacker can craft and sign arbitrary JWT tokens with:
  `{"sub": "<ANY_PATIENT_ID>", "role": "clinician"}`
  and gain full administrative and medical access.

### Finding 2.3: Self-Assigned Privileged Roles at Registration
- **Severity:** **HIGH**
- **Real Evidence:**
  In [`backend/app/routers/auth.py:L35-37`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/backend/app/routers/auth.py#L35-L37):
  ```python
  user = User(
      email=normalized_email,
      hashed_password=hashed_pw,
      role=payload.role or "clinician",
      ...
  ```
- **Impact:**
  Any user registering via `POST /api/v1/auth/register` can specify `"role": "clinician"` in their JSON payload. There is no email verification, institutional domain whitelist, or clinician credential approval flow. Any public user can grant themselves clinician privileges.

---

## Section 3: Secrets, Logs & Personal Data in Git History

### Finding 3.1: Active Google API Keys Leaked in Historical Git Commits
- **Severity:** **CRITICAL**
- **Real Evidence:**
  Executing git history inspection `git show 7a7de96~1:backend/.env` reveals:
  ```env
  # Google Gemini API Key (for ECG analysis + report generation)
  GEMINI_API_KEY=AIza***[REVOKED]

  # Google Maps API Key (for hospital finder + geolocation)
  GOOGLE_MAPS_API_KEY=AIza***[REVOKED]

  DATABASE_URL=sqlite:///./cardiac_data.db
  ```
  And `git show f54d44b~1:.env`:
  ```env
  VITE_GOOGLE_MAPS_API_KEY=AIza***[REVOKED]
  VITE_API_BASE_URL=http://localhost:8000
  ```
- **Commit Lineage:**
  - Commit `07791a7` and `26e4555`: Committed `.env` and `backend/.env`.
  - Commits `f54d44b` and `7a7de96`: Deleted the files from the working tree.
  - **Crucial Reality:** Deleting files in a git commit **does not remove them from git history**. Anyone cloning `https://github.com/Adhya08/Cardiac_Analyst` can inspect git history unless filtered; all historical references have now been purged and revoked (AIza***[REVOKED]).
- **Recommendation:** Revoke both Google API keys immediately in the Google Cloud Console and run `git-filter-repo` or BFG Repo-Cleaner to purge historical blobs.

### Finding 3.2: Developer Internal Paths & Local Machine Identifiers in Log Dumps
- **Severity:** **MEDIUM**
- **Real Evidence:**
  Commit `26e4555dddc523be7fb6170e461fefd6fecc94ab` committed `backend_logs.txt` and `frontend_logs.txt`. Inspection of `backend_logs.txt` reveals:
  ```
  C:\Users\adhya\Downloads\Cardiac_Analyst-main\Cardiac_Analyst-main\backend\venv\Lib\site-packages\...
  INFO: 127.0.0.1:50307 - "PUT /api/v1/user/profile?user_id=test_user HTTP/1.1" 200 OK
  ```
- **Impact:**
  Exposes the developer's Windows username (`adhya`), download folder structure, internal port allocations, and debug endpoint interactions.

---

## Section 4: Audit of Public Claims vs. `EVALUATION_REPORT.md`

`backend/models/EVALUATION_REPORT.md` is the ground-truth benchmark for the 1D ResNet model on PhysioNet PTB-XL Fold 10 (2,158 held-out records).

### Discrepancy Matrix

| Metric / Claim | Ground Truth (`EVALUATION_REPORT.md`) | Code / UI Location | Stated Value in Repo | Verification Finding |
| :--- | :---: | :--- | :---: | :---: |
| **Normal (NORM) AUROC** | **0.9447** (Line 32) | [`src/modes/OverviewMode.tsx:L305`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/src/modes/OverviewMode.tsx#L305) | **0.9335** | **Contradiction** |
| **Infarction (MI) AUROC** | **0.9244** (Line 33) | [`src/modes/OverviewMode.tsx:L306`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/src/modes/OverviewMode.tsx#L306) | **0.9118** | **Contradiction** |
| **ST/T Changes (STTC) AUROC**| **0.9351** (Line 34) | [`src/modes/OverviewMode.tsx:L307`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/src/modes/OverviewMode.tsx#L307) | **0.9322** | **Contradiction** |
| **Conduction (CD) AUROC** | **0.9259** (Line 35) | [`src/modes/OverviewMode.tsx:L308`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/src/modes/OverviewMode.tsx#L308) | **0.9111** | **Contradiction** |
| **Hypertrophy (HYP) AUROC** | **0.9021** (Line 36) | [`src/modes/OverviewMode.tsx:L309`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/src/modes/OverviewMode.tsx#L309) | **0.8327** | **Contradiction** (Severely understated) |
| **Vitals Endpoint** | Does not exist | [`README.md:L223`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/README.md#L223) | `POST /api/v1/vitals/calculate` | **Non-existent API Route** (Real route is `/vitals`) |
| **Grad-CAM Lead Saliency** | No Grad-CAM in evaluation | [`backend/app/ml/local_ecg_model.py:L319-325`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/backend/app/ml/local_ecg_model.py#L319-L325) | Heuristic ST check strings | **Unbacked Claim** (Pseudo-GradCAM generated without backpropagation) |
| **LightGBM Risk Model Accuracy**| Not evaluated in report | [`backend/app/main.py:L90`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/backend/app/main.py#L90) | Hardcoded `86%` | **Unbacked Claim** (No test-set split report in repo) |
| **TFLite & Keras Latency** | Only ONNX tested in report | [`README.md:L202-206`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/README.md#L202-L206) | Keras 84.42ms, TFLite 16.88ms | **Unverified Hardware Context** (Local machine benchmark, not standardized) |

---

## Section 5: System Behavior During Backend Dormancy & Failure

### Finding 5.1: Cloud Sleep / Cold Start Behavior (Render / Railway Free Tiers)
- **Severity:** **HIGH**
- **Evidence:**
  - Modern free tier hosting platforms put backends to sleep after 15 minutes of inactivity. Cold boots require 30 to 60 seconds to spin up Python, initialize SQLite, load ONNX Runtime, and unpickle the LightGBM model.
  - In [`src/components/TopBar.tsx:L125`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/src/components/TopBar.tsx#L125), the UI displays a pulsing amber indicator with the text `"Connecting..."`.
  - While `"Connecting..."` informs the user, there is no progressive loading state or estimated countdown (e.g., "Spinning up local inference engine, please wait 30s..."). Users submitting ECGs or vitals during this window experience a request timeout or a generic red error message.

### Finding 5.2: ECG Analysis Failure State
- **Severity:** **MEDIUM**
- **Evidence:**
  In [`src/modes/ECGMode.tsx:L298-301`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/src/modes/ECGMode.tsx#L298-L301):
  ```tsx
  } catch (err: any) {
    setStatus('error');
    setErrorMsg(err.message || 'ECG analysis failed. Make sure the backend server is running.');
    setProgress(0);
  }
  ```
  If the backend crashes or is offline, the frontend cannot perform local client-side ONNX inference via WebAssembly/ONNX.js. The entire diagnostic workstation halts with an error message and a "Try Again" button.

### Finding 5.3: Emergency Mode Degraded Resilience
- **Severity:** **MEDIUM**
- **Evidence:**
  In [`src/modes/EmergencyMode.tsx:L92-137`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/src/modes/EmergencyMode.tsx#L92-L137):
  - If the backend is down, the frontend catches the error and executes client-side fallback triage logic, ensuring the patient is not left hanging.
  - **Failure Limitation:** In this offline mode, `hospitals: []` is empty! The hospital locator requires the backend Overpass/Google Places API proxy. A patient in acute distress receives the emergency advice to call 112, but cannot see nearby hospital maps, distances, or phone numbers.

---

## Section 6: Clinical Triage Analysis: Downplaying Serious Symptoms

### Finding 6.1: Atypical STEMI Presentation Downplayed as "Normal / Low Risk"
- **Severity:** **CRITICAL**
- **Clinical Guideline Context:**
  According to the **ACC/AHA 2021 Chest Pain Guidelines** and **ESC Guidelines on Non-ST-Segment Elevation Acute Coronary Syndromes**, elderly patients, women, and individuals with diabetes frequently do not experience "crushing retrosternal chest pain." Instead, acute myocardial infarction often presents with **diaphoresis (cold sweats), unexplained nausea, acute dizziness, or profound fatigue**.
- **Real Evidence in [`backend/app/ml/triage.py`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/backend/app/ml/triage.py):**
  The 8 questions are:
  - Q0: Crushing chest pain
  - Q1: Pain radiating to left arm/jaw
  - Q2: Shortness of breath at rest
  - Q3: Nauseous or lightheaded / dizzy
  - Q4: Heart racing / irregular
  - Q5: Sweating profusely / cold sweats
  - Q6: Fainted / syncope
  - Q7: Blurry vision / confusion

  Let us trace a patient suffering an acute inferior wall myocardial infarction who presents with:
  - **Q3 (Nauseous & lightheaded)**: `YES`
  - **Q5 (Profuse cold sweats / diaphoresis)**: `YES`
  - **All other questions**: `NO`

  Execution in `assess_emergency(symptoms=[False, False, False, True, False, True, False, False])`:
  1. `yes_indices = {3, 5}`
  2. `yes_count = 2`
  3. `EMERGENCY_COMBOS`: Check `{0,1,5}, {0,1,2}, {0,2,5}, {0,4,5}, {6}, {0,7}` $\rightarrow$ **None match** (`False`)
  4. Line 100: `if combo_triggered or yes_count >= 5 or vitals_red_flag:` $\rightarrow$ **False**
  5. Line 113: `elif yes_count >= 3 or (0 in yes_indices) or (2 in yes_indices) or (4 in yes_indices and 6 in yes_indices):`
     - `yes_count >= 3`? No (`2 >= 3` is `False`).
     - `0 in yes_indices`? No.
     - `2 in yes_indices`? No.
     - `4 in yes_indices and 6 in yes_indices`? No.
  6. Line 120:
     ```python
     else:
         severity = "normal"
         confidence = 0.75 + (1 - yes_count / 8) * 0.20
         risk_score = max(2.0, 5.0 + yes_count * 4.5)
     ```
  7. **Actual Return Value:**
     ```json
     {
       "severity": "normal",
       "confidence": 0.90,
       "risk_score": 14.0,
       "instructions": [
         "Your symptoms appear low-risk at this time.",
         "Monitor yourself and rest if you feel unwell.",
         "Schedule a routine check-up with your doctor within the week."
       ]
     }
     ```
- **Hazard:**
  A patient actively experiencing a life-threatening acute coronary event with profuse cold sweats and nausea is formally reassured that their symptoms are **"low-risk"** and told to schedule a routine check-up "within the week." This is a severe clinical risk.

### Finding 6.2: Isolated Radiating Anginal Pain Downplayed as "Normal"
- **Severity:** **CRITICAL**
- **Evidence:**
  A patient who experiences severe pain radiating to the left arm and jaw (Q1 = `True`), but who does not describe their chest sensation as "crushing or squeezing" (Q0 = `False`):
  - `yes_indices = {1}`
  - `yes_count = 1`
  - `assess_emergency` routes to `else:` $\rightarrow$ **`severity = "normal"`**!
  - Radiating arm and jaw ischemic pain is classified as "normal" because Q1 is only evaluated when combined with Q0 in `EMERGENCY_COMBOS`.

### Finding 6.3: Discrepancy Between Online Backend and Offline Frontend Rules
- **Severity:** **HIGH**
- **Evidence:**
  - In `backend/app/ml/triage.py:L113`: `yes_count >= 3` is required for `see_doctor`.
  - In `src/modes/EmergencyMode.tsx:L100`: `const isDoctor = yesCount >= 1 || Boolean(finalAnswers[0]) || Boolean(finalAnswers[2]);`
  - **Discrepancy:**
    - If the backend is running, a patient with 2 minor symptoms is told: **"Low-Risk / Normal"**.
    - If the backend is offline, the client-side code tells them: **"See Doctor / Urgent (within 24h)"**.
    The clinical triage decision changes depending on server uptime.

---

## Section 7: Leftover References to Legacy Architectures

### Finding 7.1: `google-genai` Left in Backend Dependencies
- **Severity:** **LOW**
- **Real Evidence:**
  In [`backend/requirements.txt:L30-31`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/backend/requirements.txt#L30-L31):
  ```text
  # Google AI - Gemini
  google-genai>=1.0.0
  ```
  And in [`backend/app/main.py:L25`](file:///c:/Users/Vivan/OneDrive/Documents/PROJECTS/Cardiac_Analyst/backend/app/main.py#L25):
  ```python
  "Patient Chat & Summaries (Sarvam AI), "
  ```
- **Impact:**
  While the diagnostic path has zero Gemini imports (verified by AST test `test_no_gemini_in_ecg_path`), `google-genai` is still listed in `backend/requirements.txt`, needlessly inflating docker image build times and leaving a vestigial artifact of the old architecture.

### Finding 7.2: Elimination Verification for Claude, SageMaker, and 15-Class Ensemble
- **Verification Result:** **CLEAN**
  - **Claude**: 0 occurrences in source code (only appears in `PROGRESS.md` detailing its historical removal).
  - **SageMaker**: 0 occurrences in source code (only appears in `CardiacApp_PRD_FRD_WebApp_v2.md` confirming zero cloud GPU dependencies).
  - **15-Condition Model**: 0 occurrences in source code. All active models and schemas strictly reflect the 5 PTB-XL superclasses (`NORM`, `MI`, `STTC`, `CD`, `HYP`).

---

## Final Recommendation Action Plan

1. **Immediate Security Remediations:**
   - Revoke leaked Google API keys in GCP Console.
   - Run `git-filter-repo` to excise historical `.env` commits.
   - Patch `vitals.py` and `ecg.py` so unauthenticated requests cannot pass arbitrary `user_id` parameters to view private medical logs.
   - Enforce mandatory environment variable `JWT_SECRET_KEY` without a default hardcoded string in production.
2. **Clinical Safety Fixes:**
   - Revise `EMERGENCY_COMBOS` in `backend/app/ml/triage.py` to include:
     - Diaphoresis + Nausea `{3, 5}` $\rightarrow$ at least `see_doctor` or `emergency`.
     - Radiating arm/jaw pain alone `{1}` $\rightarrow$ at least `see_doctor`.
     - Palpitations alone `{4}` $\rightarrow$ at least `see_doctor`.
   - Align backend triage thresholds with frontend offline fallback logic.
3. **Documentation & UI Synchronization:**
   - Update `src/modes/OverviewMode.tsx` lines 305–309 with the exact AUROC numbers from `backend/models/EVALUATION_REPORT.md` (`0.9447, 0.9244, 0.9351, 0.9259, 0.9021`).
   - Remove `POST /api/v1/vitals/calculate` from `README.md`.
   - Remove unused `google-genai>=1.0.0` from `backend/requirements.txt`.
