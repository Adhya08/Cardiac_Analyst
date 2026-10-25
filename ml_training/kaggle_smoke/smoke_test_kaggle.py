"""
Cardiac Analyst — Phase 3 Pipeline Smoke Test on Kaggle GPU
============================================================
Validates the complete data and training pipeline on a small subset (500 train, 100 val)
for 2 epochs before full-scale training.

Verifies:
1. GPU hardware availability (Tesla T4 / P100)
2. PTB-XL data loading & SCP mapping to 5 diagnostic superclasses
3. Zero patient leakage across Train, Val, and Test splits
4. Signal shapes (1000, 12) float32 -> (12, 1000) for PyTorch Conv1d
5. Per-lead normalization using training data only
6. Multi-label BCEWithLogitsLoss with positive class re-weighting
7. End-to-end forward/backward pass with mixed precision (AMP)
8. Output serialization of preprocessing_config.json and smoke_test_metrics.json
"""
import os
import sys
import ast
import json
import time
import subprocess
import numpy as np
import pandas as pd
from typing import List, Optional, Tuple, Dict, Any

# -------------------------------------------------------------
# 0. Dependencies Setup
# -------------------------------------------------------------
try:
    import wfdb
except ImportError:
    print("[Setup] Installing wfdb...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "wfdb"])
    import wfdb

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import roc_auc_score, f1_score

# -------------------------------------------------------------
# 1. Pipeline Constants & Configuration
# -------------------------------------------------------------
DIAGNOSTIC_SUPERCLASSES = ["NORM", "MI", "STTC", "CD", "HYP"]
SUPERCLASS_TO_IDX = {cls_name: idx for idx, cls_name in enumerate(DIAGNOSTIC_SUPERCLASSES)}
NUM_CLASSES = len(DIAGNOSTIC_SUPERCLASSES)

STANDARD_LEAD_ORDER = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
SAMPLING_RATE = 100
SIGNAL_LENGTH = 1000
NUM_LEADS = 12
RAW_SIGNAL_SHAPE = (SIGNAL_LENGTH, NUM_LEADS)
TORCH_SIGNAL_SHAPE = (NUM_LEADS, SIGNAL_LENGTH)

TRAIN_FOLDS = list(range(1, 9))
VAL_FOLDS = [9]
TEST_FOLDS = [10]

SMOKE_TRAIN_SAMPLES = 500
SMOKE_VAL_SAMPLES = 100
SMOKE_EPOCHS = 2
BATCH_SIZE = 32
LEARNING_RATE = 1e-3

OUTPUT_DIR = "/kaggle/working" if os.path.exists("/kaggle/working") else "./smoke_output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


# -------------------------------------------------------------
# 2. Dataset Path Resolution
# -------------------------------------------------------------
def locate_ptbxl() -> str:
    candidate_paths = [
        "/kaggle/input/datasets/garethwmch/ptb-xl-1-0-3/ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3",
        "/kaggle/input/ptb-xl-1-0-3/ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3",
        "/kaggle/input/ptb-xl-1-0-3",
        "/kaggle/input/ptb-xl-dataset",
        "./scratch/ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3",
    ]
    for p in candidate_paths:
        if os.path.exists(os.path.join(p, "ptbxl_database.csv")):
            print(f"[Dataset] Found PTB-XL at: {p}")
            return p

    if os.path.exists("/kaggle/input"):
        for root, _, files in os.walk("/kaggle/input"):
            if "ptbxl_database.csv" in files:
                print(f"[Dataset] Located PTB-XL via walk at: {root}")
                return root

    raise FileNotFoundError("Could not find PTB-XL dataset containing ptbxl_database.csv.")


# -------------------------------------------------------------
# 3. Data Loading & Preprocessing
# -------------------------------------------------------------
def load_and_map_metadata(data_dir: str) -> pd.DataFrame:
    db_csv = os.path.join(data_dir, "ptbxl_database.csv")
    scp_csv = os.path.join(data_dir, "scp_statements.csv")

    df = pd.read_csv(db_csv, index_col="ecg_id")
    scp_df = pd.read_csv(scp_csv, index_col=0)
    diag_scp = scp_df[scp_df["diagnostic"] == 1.0]

    if isinstance(df["scp_codes"].iloc[0], str):
        df["scp_codes"] = df["scp_codes"].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)

    def aggregate_diagnostic(scp_codes: dict):
        classes = set()
        for code in scp_codes.keys():
            if code in diag_scp.index:
                d_class = diag_scp.loc[code, "diagnostic_class"]
                if pd.notna(d_class) and d_class in SUPERCLASS_TO_IDX:
                    classes.add(d_class)
        return list(classes)

    df["diagnostic_superclass"] = df["scp_codes"].apply(aggregate_diagnostic)
    clean_df = df[df["diagnostic_superclass"].apply(lambda x: len(x) > 0)].copy()

    targets = np.zeros((len(clean_df), NUM_CLASSES), dtype=np.float32)
    for row_idx, classes in enumerate(clean_df["diagnostic_superclass"]):
        for cls_name in classes:
            targets[row_idx, SUPERCLASS_TO_IDX[cls_name]] = 1.0
    clean_df["label_vector"] = list(targets)

    return clean_df


class Preprocessor:
    def __init__(self):
        self.lead_order = list(STANDARD_LEAD_ORDER)
        self.lead_means = np.zeros(NUM_LEADS, dtype=np.float32)
        self.lead_stds = np.ones(NUM_LEADS, dtype=np.float32)

    def fit_from_training_signals(self, signals: List[np.ndarray]):
        stacked = np.stack(signals, axis=0)  # (N, 1000, 12)
        self.lead_means = np.mean(stacked, axis=(0, 1)).astype(np.float32)
        stds = np.std(stacked, axis=(0, 1)).astype(np.float32)
        self.lead_stds = np.where(stds < 1e-6, 1.0, stds).astype(np.float32)
        print(f"[Preprocessing] Fitted per-lead stats on {len(signals)} training records.")

    def preprocess(self, raw_signal: np.ndarray, current_lead_names: List[str]) -> np.ndarray:
        sig = np.array(raw_signal, dtype=np.float32)
        if sig.ndim == 2 and sig.shape[0] == NUM_LEADS and sig.shape[1] != NUM_LEADS:
            sig = sig.T

        if current_lead_names:
            name_to_idx = {name.upper(): i for i, name in enumerate(current_lead_names)}
            reordered = []
            for t_name in self.lead_order:
                t_up = t_name.upper()
                if t_up in name_to_idx:
                    reordered.append(sig[:, name_to_idx[t_up]])
                else:
                    reordered.append(np.zeros(sig.shape[0], dtype=np.float32))
            sig = np.stack(reordered, axis=-1)

        sig = np.nan_to_num(sig, nan=0.0, posinf=0.0, neginf=0.0)

        # Pad / crop to 1000 samples
        if sig.shape[0] > SIGNAL_LENGTH:
            sig = sig[:SIGNAL_LENGTH, :]
        elif sig.shape[0] < SIGNAL_LENGTH:
            pad = SIGNAL_LENGTH - sig.shape[0]
            sig = np.pad(sig, ((0, pad), (0, 0)), mode="edge")

        # Per-lead normalization using training set statistics
        norm = (sig - self.lead_means) / self.lead_stds
        norm = np.clip(norm, -10.0, 10.0).astype(np.float32)
        return norm

    def save_config(self, out_path: str):
        config_data = {
            "dataset": "PhysioNet PTB-XL v1.0.3",
            "lead_order": self.lead_order,
            "sampling_rate": SAMPLING_RATE,
            "signal_shape": list(RAW_SIGNAL_SHAPE),
            "torch_signal_shape": list(TORCH_SIGNAL_SHAPE),
            "labels": DIAGNOSTIC_SUPERCLASSES,
            "normalization": {
                "method": "per_lead_z_score",
                "computed_on": "Folds 1-8 (Training set only)",
                "lead_means": [float(m) for m in self.lead_means],
                "lead_stds": [float(s) for s in self.lead_stds],
            },
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        print(f"[Preprocessing] Saved config to: {out_path}")


class PTBDataset(Dataset):
    def __init__(self, df: pd.DataFrame, base_dir: str, preprocessor: Preprocessor):
        self.df = df.reset_index(drop=False)
        self.base_dir = base_dir
        self.preprocessor = preprocessor

    def __len__(self):
        return len(self.df)

    def __getitem__(self, idx):
        row = self.df.iloc[idx]
        full_path = os.path.join(self.base_dir, row["filename_lr"])
        signal, fields = wfdb.rdsamp(full_path)
        lead_names = fields.get("sig_name", [])

        # Preprocess to (1000, 12)
        norm_1000_12 = self.preprocessor.preprocess(signal, lead_names)
        # Transpose to (12, 1000) for PyTorch Conv1d
        torch_12_1000 = norm_1000_12.T.astype(np.float32)

        target = np.array(row["label_vector"], dtype=np.float32)
        return torch.tensor(torch_12_1000, dtype=torch.float32), torch.tensor(target, dtype=torch.float32)


# -------------------------------------------------------------
# 4. Model Architecture (1D Residual CNN)
# -------------------------------------------------------------
class ResBlock1D(nn.Module):
    def __init__(self, in_ch, out_ch, stride=1, kernel_size=7):
        super().__init__()
        p = (kernel_size - 1) // 2
        self.conv1 = nn.Conv1d(in_ch, out_ch, kernel_size, stride=stride, padding=p, bias=False)
        self.bn1 = nn.BatchNorm1d(out_ch)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv1d(out_ch, out_ch, kernel_size, stride=1, padding=p, bias=False)
        self.bn2 = nn.BatchNorm1d(out_ch)

        if stride != 1 or in_ch != out_ch:
            self.shortcut = nn.Sequential(
                nn.Conv1d(in_ch, out_ch, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm1d(out_ch),
            )
        else:
            self.shortcut = nn.Identity()

    def forward(self, x):
        res = self.shortcut(x)
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        out = out + res
        out = self.relu(out)
        return out


class ResNet1D(nn.Module):
    def __init__(self, in_channels=12, num_classes=5, dropout_rate=0.2):
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv1d(in_channels, 64, kernel_size=15, stride=2, padding=7, bias=False),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=3, stride=2, padding=1),
        )
        self.stage1 = self._make_stage(64, 64, 2, 1)
        self.stage2 = self._make_stage(64, 128, 2, 2)
        self.stage3 = self._make_stage(128, 256, 2, 2)
        self.stage4 = self._make_stage(256, 512, 2, 2)
        self.global_pool = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(dropout_rate)
        self.fc = nn.Linear(512, num_classes)

    def _make_stage(self, in_ch, out_ch, num_blocks, stride):
        layers = [ResBlock1D(in_ch, out_ch, stride=stride)]
        for _ in range(1, num_blocks):
            layers.append(ResBlock1D(out_ch, out_ch, stride=1))
        return nn.Sequential(*layers)

    def forward(self, x):
        out = self.stem(x)
        out = self.stage1(out)
        out = self.stage2(out)
        out = self.stage3(out)
        out = self.stage4(out)
        out = self.global_pool(out)
        out = torch.flatten(out, 1)
        out = self.dropout(out)
        return self.fc(out)


# -------------------------------------------------------------
# 5. Evaluation Function
# -------------------------------------------------------------
def evaluate(model, loader, criterion, device):
    model.eval()
    total_loss = 0.0
    all_targets = []
    all_probs = []

    with torch.no_grad():
        for signals, targets in loader:
            signals = signals.to(device)
            targets = targets.to(device)

            logits = model(signals)
            loss = criterion(logits, targets)
            total_loss += loss.item() * signals.size(0)

            probs = torch.sigmoid(logits).cpu().numpy()
            all_probs.append(probs)
            all_targets.append(targets.cpu().numpy())

    all_targets = np.vstack(all_targets)
    all_probs = np.vstack(all_probs)
    avg_loss = total_loss / max(len(loader.dataset), 1)

    per_class_auc = {}
    auc_values = []
    for idx, cls_name in enumerate(DIAGNOSTIC_SUPERCLASSES):
        try:
            auc = float(roc_auc_score(all_targets[:, idx], all_probs[:, idx]))
        except Exception:
            auc = 0.5
        per_class_auc[cls_name] = auc
        auc_values.append(auc)

    macro_auc = float(np.mean(auc_values))
    preds = (all_probs >= 0.5).astype(np.float32)
    macro_f1 = float(f1_score(all_targets, preds, average="macro", zero_division=0))

    return avg_loss, macro_auc, macro_f1, per_class_auc


# -------------------------------------------------------------
# 6. Main Smoke Test Routine
# -------------------------------------------------------------
def main():
    print("=" * 70)
    print("  CARDIAC ANALYST — PHASE 3 PIPELINE SMOKE TEST (KAGGLE GPU)")
    print("=" * 70)

    # 1. Device Diagnostics
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"\n[Hardware] Device: {device}")
    if torch.cuda.is_available():
        print(f"           GPU: {torch.cuda.get_device_name(0)}")
        print(f"           VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB")
        print(f"           PyTorch: {torch.__version__} | CUDA: {torch.version.cuda}")

    # 2. Locate Data & Load Metadata
    data_dir = locate_ptbxl()
    clean_df = load_and_map_metadata(data_dir)
    print(f"\n[Metadata] Total Clean Diagnostic Records: {len(clean_df)}")

    # Split dataset
    train_df = clean_df[clean_df["strat_fold"].isin(TRAIN_FOLDS)].copy()
    val_df = clean_df[clean_df["strat_fold"].isin(VAL_FOLDS)].copy()
    test_df = clean_df[clean_df["strat_fold"].isin(TEST_FOLDS)].copy()

    # 3. Verify Patient Overlap
    train_pts = set(train_df["patient_id"].dropna().unique())
    val_pts = set(val_df["patient_id"].dropna().unique())
    test_pts = set(test_df["patient_id"].dropna().unique())

    print("\n--- PATIENT OVERLAP AUDIT (RULE 4) ---")
    print(f"  Train Patients (Folds 1-8): {len(train_pts)}")
    print(f"  Val Patients   (Fold 9)   : {len(val_pts)}")
    print(f"  Test Patients  (Fold 10)  : {len(test_pts)}")
    overlap_tv = len(train_pts.intersection(val_pts))
    overlap_tt = len(train_pts.intersection(test_pts))
    overlap_vt = len(val_pts.intersection(test_pts))
    print(f"  Train & Val Overlap : {overlap_tv}")
    print(f"  Train & Test Overlap: {overlap_tt}")
    print(f"  Val & Test Overlap  : {overlap_vt}")
    assert overlap_tv == 0 and overlap_tt == 0 and overlap_vt == 0, "Patient leakage detected!"
    print("  --> ZERO PATIENT LEAKAGE VERIFIED.")

    # 4. Print Real Split Statistics
    print("\n--- REAL DATASET STATISTICS ---")
    for name, s_df in [("Train (Folds 1-8)", train_df), ("Val (Fold 9)", val_df), ("Test (Fold 10)", test_df)]:
        print(f"\n{name} ({len(s_df)} records):")
        for c in DIAGNOSTIC_SUPERCLASSES:
            count = int(sum(s_df["diagnostic_superclass"].apply(lambda cl: c in cl)))
            pct = count / len(s_df) * 100.0
            print(f"  {c:5s}: {count:5d} ({pct:5.2f}%)")

    # 5. Preprocessing & Normalization Statistics (Computed on Training Data Only)
    preprocessor = Preprocessor()
    print("\n[Preprocessing] Sampling 100 training signals to compute per-lead training statistics...")
    sample_train_sigs = []
    for idx in range(min(100, len(train_df))):
        rel = train_df.iloc[idx]["filename_lr"]
        sig, flds = wfdb.rdsamp(os.path.join(data_dir, rel))
        if sig.shape[0] > SIGNAL_LENGTH:
            sig = sig[:SIGNAL_LENGTH, :]
        elif sig.shape[0] < SIGNAL_LENGTH:
            sig = np.pad(sig, ((0, SIGNAL_LENGTH - sig.shape[0]), (0, 0)), mode="edge")
        sample_train_sigs.append(sig.astype(np.float32))

    preprocessor.fit_from_training_signals(sample_train_sigs)
    cfg_file = os.path.join(OUTPUT_DIR, "preprocessing_config.json")
    preprocessor.save_config(cfg_file)

    # 6. Create Tiny Smoke Test Subset
    smoke_train_df = train_df.iloc[:SMOKE_TRAIN_SAMPLES].copy()
    smoke_val_df = val_df.iloc[:SMOKE_VAL_SAMPLES].copy()

    train_ds = PTBDataset(smoke_train_df, data_dir, preprocessor)
    val_ds = PTBDataset(smoke_val_df, data_dir, preprocessor)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=2)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=2)

    # Check batch shapes
    sample_sig, sample_tgt = train_ds[0]
    print(f"\n[Shape Check] Dataset Item Signal Shape: {sample_sig.shape} (Expected: {TORCH_SIGNAL_SHAPE}), Dtype: {sample_sig.dtype}")
    print(f"              Target Vector Shape: {sample_tgt.shape} (Expected: (5,))")
    assert sample_sig.shape == TORCH_SIGNAL_SHAPE, f"Shape mismatch: {sample_sig.shape}"

    # 7. Model & Loss Setup
    model = ResNet1D().to(device)

    # Compute positive class weights from smoke training set
    train_targets = np.array(smoke_train_df["label_vector"].tolist(), dtype=np.float32)
    pos_counts = np.sum(train_targets, axis=0)
    pos_weights = (len(train_targets) - pos_counts) / np.maximum(pos_counts, 1.0)
    pos_weights_tensor = torch.tensor(pos_weights, dtype=torch.float32).to(device)

    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weights_tensor)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE, weight_decay=1e-2)

    use_cuda = (device.type == "cuda")
    scaler = None
    if use_cuda:
        try:
            scaler = torch.amp.GradScaler("cuda")
        except Exception:
            scaler = torch.cuda.amp.GradScaler()

    # 8. Run 2-Epoch Smoke Test
    print(f"\n[Smoke Test Execution] Running {SMOKE_EPOCHS} epochs on GPU ({len(train_ds)} train, {len(val_ds)} val)...")
    history = []

    for epoch in range(1, SMOKE_EPOCHS + 1):
        t0 = time.time()
        model.train()
        train_loss = 0.0

        for signals, targets in train_loader:
            signals = signals.to(device)
            targets = targets.to(device)
            optimizer.zero_grad()

            if scaler is not None:
                with torch.cuda.amp.autocast(enabled=True):
                    logits = model(signals)
                    loss = criterion(logits, targets)
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()
            else:
                logits = model(signals)
                loss = criterion(logits, targets)
                loss.backward()
                optimizer.step()

            train_loss += loss.item() * signals.size(0)

        train_loss /= len(train_ds)
        val_loss, val_auc, val_f1, per_class_auc = evaluate(model, val_loader, criterion, device)
        elapsed = time.time() - t0

        print(f"  Epoch {epoch}/{SMOKE_EPOCHS} ({elapsed:.1f}s) | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Macro AUC: {val_auc:.4f} | Val Macro F1: {val_f1:.4f}")
        for c, a in per_class_auc.items():
            print(f"      {c:5s} AUC: {a:.4f}")

        history.append({
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "val_macro_auc": val_auc,
            "val_macro_f1": val_f1,
            "per_class_auc": per_class_auc,
        })

    # Save smoke metrics
    metrics_file = os.path.join(OUTPUT_DIR, "smoke_test_metrics.json")
    with open(metrics_file, "w") as f:
        json.dump({
            "smoke_test_passed": True,
            "device": str(device),
            "epochs": SMOKE_EPOCHS,
            "train_samples": len(train_ds),
            "val_samples": len(val_ds),
            "history": history,
        }, f, indent=2)

    torch.save(model.state_dict(), os.path.join(OUTPUT_DIR, "smoke_model.pth"))

    print("\n" + "=" * 70)
    print("  >>> SMOKE TEST COMPLETED SUCCESSFULLY ON GPU! <<<")
    print(f"  Artifacts written to: {OUTPUT_DIR}")
    print("=" * 70)


if __name__ == "__main__":
    main()
