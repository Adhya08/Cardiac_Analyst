# Kaggle Remote Execution & GPU Training Workflow

> **Regulatory Notice**: Cardiac Analyst is a **research and educational prototype only**. It is **not** a certified medical device and must never be used for clinical diagnosis or direct patient treatment.

---

## 1. Overview
All machine learning model training for the Residual 1D CNN is executed remotely on **Kaggle's free GPU compute infrastructure** (Dual NVIDIA Tesla T4 GPUs with ~15GB VRAM each). 

The local development environment manages the entire training lifecycle programmatically via the **Kaggle CLI** (`kaggle` 2.2.5 installed in `backend/venv`), enabling autonomous:
1. Kernel preparation & configuration (`kernel-metadata.json`).
2. Remote pushing to Kaggle's GPU runners.
3. Asynchronous execution monitoring & polling.
4. Model artifact and evaluation report downloads.

---

## 2. Authentication & Secret Management

In compliance with **Permanent Rule 5** (*Never put secrets in code, chat, or Git*):
- The Kaggle API Token (`KGAT_...`) is stored locally on the host machine at `~/.kaggle/access_token` (`C:\Users\Vivan\.kaggle\access_token`) and in `backend/.env`.
- Both `kaggle.json`, `.kaggle/`, and `.env` are strictly excluded from version control via `.gitignore`.
- Authentication was verified and confirmed under Kaggle username: **`cyberfocus2410`**.

---

## 3. Verified Kaggle CLI Commands

All commands run through the virtual environment CLI wrapper (`backend\venv\Scripts\kaggle.exe`).

### 3.1 Check CLI Version
```powershell
backend\venv\Scripts\kaggle.exe --version
# Output: Kaggle CLI 2.2.5
```

### 3.2 Search Public Datasets
```powershell
backend\venv\Scripts\kaggle.exe datasets list -s "ptb-xl"
```

### 3.3 Inspect Dataset Contents
```powershell
backend\venv\Scripts\kaggle.exe datasets files garethwmch/ptb-xl-1-0-3
```

### 3.4 Initialize Kernel Configuration Template
```powershell
backend\venv\Scripts\kaggle.exe kernels init -p "<directory_path>"
```

### 3.5 Push Kernel to Kaggle for GPU Execution
```powershell
backend\venv\Scripts\kaggle.exe kernels push -p "<directory_path>"
# Returns: Kernel version <N> successfully pushed.
```

### 3.6 Monitor Kernel Execution Status
```powershell
backend\venv\Scripts\kaggle.exe kernels status <username>/<kernel-slug>
# Returns: KernelWorkerStatus.QUEUED -> KernelWorkerStatus.RUNNING -> KernelWorkerStatus.COMPLETE
```

### 3.7 Download Trained Artifacts & Execution Logs
```powershell
backend\venv\Scripts\kaggle.exe kernels output <username>/<kernel-slug> -p "<local_destination_folder>"
```

---

## 4. Hardware Verification & Provenance

Execution was verified by running the `cardiac-analyst-gpu-test` kernel on Kaggle:
- **Runner OS**: Linux (Ubuntu GCC 13.3.0)
- **Python**: `3.13.15`
- **PyTorch**: `2.11.0+cu128`
- **CUDA Device**: `2x Tesla T4`
- **Total VRAM**: `14.56 GB`
- **Compute Capability**: `(7, 5)`
- **Tensor Benchmark**: `2048 x 2048` matrix multiplication completed with synchronized CUDA execution.

---

## 5. PTB-XL Dataset Selection & Strategy

### Evaluated Kaggle Candidates:
1. `garethwmch/ptb-xl-1-0-3`:
   - Size: `1.84 GB`
   - Structure: Complete official PhysioNet release **v1.0.3** (`ptbxl_database.csv`, `records100/`, `records500/`, `SHA256SUMS.txt`).
   - Provenance: Clean mirror of PhysioNet v1.0.3 with official fold allocations (1–10).
2. `khyeh0719/ptb-xl-dataset`:
   - Size: `1.85 GB`
   - Structure: Older PhysioNet release **v1.0.1**.

### Recommended Ingestion Approach:
- Mount `garethwmch/ptb-xl-1-0-3` as a dataset input in the notebook metadata (`dataset_sources: ["garethwmch/ptb-xl-1-0-3"]`). This provides instantaneous availability at `/kaggle/input/ptb-xl-1-0-3/` with zero download overhead.
- Direct PhysioNet download script (`wget https://physionet.org/static/published-projects/ptb-xl/ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3.zip`) retained in the training script as an active fallback.
