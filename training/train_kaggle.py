"""
Cardiac Analyst — PTB-XL Residual 1D CNN Training Pipeline
===========================================================
Trains a 1D Residual CNN on PhysioNet's PTB-XL (v1.0.3) dataset.
Follows all project engineering rules:
  - Folds 1–8: Training
  - Fold 9: Validation
  - Fold 10: Hold-out Test (STRICTLY untouched during training/tuning)
  - Exports trained weights to ONNX format for local FastAPI CPU inference.
"""

import os
import sys
import ast
import json
import time
import subprocess
import numpy as np
import pandas as pd

# -------------------------------------------------------------
# 0. Runtime Dependency Setup
# -------------------------------------------------------------
try:
    import wfdb
except ImportError:
    print("[Setup] Installing wfdb...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "wfdb"])
    import wfdb

try:
    import onnx
    import onnxruntime
except ImportError:
    print("[Setup] Installing onnx and onnxruntime...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "onnx", "onnxruntime"])
    import onnx
    import onnxruntime

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from sklearn.metrics import roc_auc_score, f1_score


# -------------------------------------------------------------
# 1. Dataset & Preprocessing Constants
# -------------------------------------------------------------
DIAGNOSTIC_SUPERCLASSES = ["NORM", "MI", "STTC", "CD", "HYP"]
SUPERCLASS_TO_IDX = {cls_name: idx for idx, cls_name in enumerate(DIAGNOSTIC_SUPERCLASSES)}
NUM_CLASSES = len(DIAGNOSTIC_SUPERCLASSES)


def parse_and_aggregate_labels(df: pd.DataFrame, scp_statements_path: str) -> pd.DataFrame:
    """
    Map SCP codes in ptbxl_database.csv to the 5 official diagnostic superclasses.
    Filters records to ensure each has at least one valid diagnostic superclass.
    """
    if not os.path.exists(scp_statements_path):
        raise FileNotFoundError(f"scp_statements.csv not found at: {scp_statements_path}")

    agg_df = pd.read_csv(scp_statements_path, index_col=0)
    agg_df = agg_df[agg_df["diagnostic"] == 1.0]

    # Convert string representation of dict to real dict
    if isinstance(df["scp_codes"].iloc[0], str):
        df["scp_codes"] = df["scp_codes"].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)

    def aggregate_diagnostic(scp_codes: dict) -> list:
        classes = set()
        for code in scp_codes.keys():
            if code in agg_df.index:
                d_class = agg_df.loc[code, "diagnostic_class"]
                if pd.notna(d_class) and d_class in SUPERCLASS_TO_IDX:
                    classes.add(d_class)
        return list(classes)

    df["diagnostic_superclass"] = df["scp_codes"].apply(aggregate_diagnostic)
    # Filter for records with at least one diagnostic superclass
    clean_df = df[df["diagnostic_superclass"].apply(lambda x: len(x) > 0)].copy()

    # Create multi-label binary target array: [NORM, MI, STTC, CD, HYP]
    targets = np.zeros((len(clean_df), NUM_CLASSES), dtype=np.float32)
    for row_idx, classes in enumerate(clean_df["diagnostic_superclass"]):
        for cls_name in classes:
            col_idx = SUPERCLASS_TO_IDX[cls_name]
            targets[row_idx, col_idx] = 1.0

    clean_df["label_vector"] = list(targets)
    return clean_df


def load_raw_waveform(file_path_no_ext: str) -> np.ndarray:
    """
    Read WFDB 12-lead record.
    Returns array of shape (12, length) in float32.
    """
    signal, fields = wfdb.rdsamp(file_path_no_ext)
    # Transpose from (samples, 12) to channels-first: (12, samples)
    signal = signal.T.astype(np.float32)

    # Clean NaNs and Infs
    signal = np.nan_to_num(signal, nan=0.0, posinf=0.0, neginf=0.0)

    # Lead-wise standardization (zero mean, unit variance)
    mean = np.mean(signal, axis=-1, keepdims=True)
    std = np.std(signal, axis=-1, keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    signal = (signal - mean) / std

    # Clip extreme artifacts
    signal = np.clip(signal, -10.0, 10.0)
    return signal


class PTBXLDataset(Dataset):
    """
    PyTorch Dataset for PTB-XL 12-lead ECGs.
    """
    def __init__(self, df: pd.DataFrame, base_data_dir: str, sampling_rate: int = 100):
        self.df = df.reset_index(drop=True)
        self.base_data_dir = base_data_dir
        self.sampling_rate = sampling_rate
        self.filename_col = "filename_lr" if sampling_rate == 100 else "filename_hr"
        self.target_length = 1000 if sampling_rate == 100 else 5000

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        rel_path = row[self.filename_col]
        full_path = os.path.join(self.base_data_dir, rel_path)

        signal = load_raw_waveform(full_path)

        # Ensure exact length
        if signal.shape[1] > self.target_length:
            signal = signal[:, :self.target_length]
        elif signal.shape[1] < self.target_length:
            pad_len = self.target_length - signal.shape[1]
            signal = np.pad(signal, ((0, 0), (0, pad_len)), mode="constant")

        target = np.array(row["label_vector"], dtype=np.float32)

        return (
            torch.tensor(signal, dtype=torch.float32),
            torch.tensor(target, dtype=torch.float32)
        )


# -------------------------------------------------------------
# 2. Residual 1D CNN Architecture
# -------------------------------------------------------------
class ConvBlock1D(nn.Module):
    """
    Basic Residual Block for 1D Signals.
    Conv1D -> BatchNorm1D -> ReLU -> Conv1D -> BatchNorm1D + Shortcut -> ReLU
    """
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 7, stride: int = 1):
        super().__init__()
        padding = kernel_size // 2
        self.conv1 = nn.Conv1d(
            in_channels, out_channels,
            kernel_size=kernel_size, stride=stride, padding=padding, bias=False
        )
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv1d(
            out_channels, out_channels,
            kernel_size=kernel_size, stride=1, padding=padding, bias=False
        )
        self.bn2 = nn.BatchNorm1d(out_channels)

        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv1d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm1d(out_channels)
            )
        else:
            self.shortcut = nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.shortcut(x)
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        out = out + residual
        out = self.relu(out)
        return out


class ResNet1D(nn.Module):
    """
    1D Residual CNN for 12-lead ECG signal classification.
    Input: (B, 12, 1000) -> Output: (B, num_classes)
    """
    def __init__(self, in_channels: int = 12, num_classes: int = 5, base_filters: int = 64):
        super().__init__()
        self.in_channels = in_channels
        self.num_classes = num_classes

        # Stem: Initial convolution with wide kernel (15) to capture broad ECG morphologies
        self.stem = nn.Sequential(
            nn.Conv1d(in_channels, base_filters, kernel_size=15, stride=2, padding=7, bias=False),
            nn.BatchNorm1d(base_filters),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=3, stride=2, padding=1)
        )

        # 4 Residual Stages: [2, 2, 2, 2] blocks (ResNet-18 1D style)
        self.stage1 = nn.Sequential(
            ConvBlock1D(base_filters, base_filters, kernel_size=7, stride=1),
            ConvBlock1D(base_filters, base_filters, kernel_size=7, stride=1),
        )
        self.stage2 = nn.Sequential(
            ConvBlock1D(base_filters, base_filters * 2, kernel_size=7, stride=2),
            ConvBlock1D(base_filters * 2, base_filters * 2, kernel_size=7, stride=1),
        )
        self.stage3 = nn.Sequential(
            ConvBlock1D(base_filters * 2, base_filters * 4, kernel_size=7, stride=2),
            ConvBlock1D(base_filters * 4, base_filters * 4, kernel_size=7, stride=1),
        )
        self.stage4 = nn.Sequential(
            ConvBlock1D(base_filters * 4, base_filters * 8, kernel_size=7, stride=2),
            ConvBlock1D(base_filters * 8, base_filters * 8, kernel_size=7, stride=1),
        )

        # Classifier head
        self.global_pool = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(p=0.3)
        self.fc = nn.Linear(base_filters * 8, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.stem(x)
        out = self.stage1(out)
        out = self.stage2(out)
        out = self.stage3(out)
        out = self.stage4(out)
        out = self.global_pool(out)      # Shape: (B, 512, 1)
        out = torch.flatten(out, 1)      # Shape: (B, 512)
        out = self.dropout(out)
        logits = self.fc(out)            # Shape: (B, num_classes)
        return logits


# -------------------------------------------------------------
# 3. Helpers & Evaluation Routine
# -------------------------------------------------------------
def locate_ptbxl_dataset() -> str:
    """Find PTB-XL dataset directory in Kaggle or local environments."""
    candidate_paths = [
        "/kaggle/input/ptb-xl-1-0-3/ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3",
        "/kaggle/input/ptb-xl-1-0-3",
        "/kaggle/input/ptb-xl-dataset",
        "./ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3",
        "../ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3",
        "../scratch/ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3",
    ]
    for p in candidate_paths:
        if os.path.exists(os.path.join(p, "ptbxl_database.csv")):
            print(f"[Dataset] Located PTB-XL at: {p}")
            return p

    # Recursive search in /kaggle/input if running on Kaggle
    if os.path.exists("/kaggle/input"):
        for root, dirs, files in os.walk("/kaggle/input"):
            if "ptbxl_database.csv" in files:
                print(f"[Dataset] Found PTB-XL via walk at: {root}")
                return root

    raise FileNotFoundError("Could not find PTB-XL dataset containing ptbxl_database.csv.")


def compute_positive_weights(targets: np.ndarray) -> torch.Tensor:
    """Compute positive class weights for BCEWithLogitsLoss to counter imbalance."""
    pos_counts = np.sum(targets, axis=0)
    total_samples = len(targets)
    pos_weights = (total_samples - pos_counts) / np.maximum(pos_counts, 1.0)
    print("\n--- Positive Class Weights ---")
    for cls_name, count, weight in zip(DIAGNOSTIC_SUPERCLASSES, pos_counts, pos_weights):
        print(f"  {cls_name:6s} | Positives: {int(count):5d}/{total_samples} ({count/total_samples*100:.1f}%) | pos_weight: {weight:.2f}")
    return torch.tensor(pos_weights, dtype=torch.float32)


def evaluate(model: nn.Module, loader: DataLoader, criterion: nn.Module, device: torch.device):
    """Evaluate model on validation loader (Fold 9)."""
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
    avg_loss = total_loss / len(loader.dataset)

    # Compute per-class AUC-ROC
    per_class_auc = {}
    auc_values = []
    for idx, cls_name in enumerate(DIAGNOSTIC_SUPERCLASSES):
        try:
            auc = roc_auc_score(all_targets[:, idx], all_probs[:, idx])
            per_class_auc[cls_name] = float(auc)
            auc_values.append(auc)
        except Exception:
            per_class_auc[cls_name] = 0.5
            auc_values.append(0.5)

    macro_auc = float(np.mean(auc_values))

    # Compute Macro F1 at standard 0.5 threshold
    binary_preds = (all_probs >= 0.5).astype(np.float32)
    macro_f1 = float(f1_score(all_targets, binary_preds, average="macro", zero_division=0))

    return avg_loss, macro_auc, macro_f1, per_class_auc


# -------------------------------------------------------------
# 4. Main Execution
# -------------------------------------------------------------
def main():
    start_time = time.time()
    print("=" * 60)
    print("CARDIAC ANALYST — PTB-XL RESIDUAL 1D CNN TRAINING")
    print("=" * 60)

    # Hardware check
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print(f"[Device] Using: {device}")
    if torch.cuda.is_available():
        print(f"[GPU] Name: {torch.cuda.get_device_name(0)}")
        print(f"[GPU] VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB")

    # Dataset loading
    data_dir = locate_ptbxl_dataset()
    db_csv = os.path.join(data_dir, "ptbxl_database.csv")
    scp_csv = os.path.join(data_dir, "scp_statements.csv")

    raw_df = pd.read_csv(db_csv)
    print(f"[Dataset] Total raw records: {len(raw_df)}")

    df = parse_and_aggregate_labels(raw_df, scp_csv)
    print(f"[Dataset] Clean diagnostic records: {len(df)}")

    # Strict fold splits (Rule 4)
    train_df = df[df["strat_fold"] <= 8].copy()
    val_df = df[df["strat_fold"] == 9].copy()
    test_df = df[df["strat_fold"] == 10].copy()

    print(f"\n[Folds Split - Rule 4 Compliance]")
    print(f"  Train (Folds 1-8): {len(train_df)} records")
    print(f"  Val   (Fold 9):    {len(val_df)} records")
    print(f"  Test  (Fold 10):   {len(test_df)} records (STRICTLY HELD OUT)")

    # Save output artifacts in working directory
    output_dir = "/kaggle/working" if os.path.exists("/kaggle") else "./outputs"
    os.makedirs(output_dir, exist_ok=True)

    # Save Fold 10 manifest for Phase 5 single-pass evaluation
    test_df[["ecg_id", "patient_id", "strat_fold", "filename_lr", "diagnostic_superclass"]].to_csv(
        os.path.join(output_dir, "fold10_test_metadata.csv"), index=False
    )
    print(f"[Artifact] Saved Fold 10 test manifest to {os.path.join(output_dir, 'fold10_test_metadata.csv')}")

    # Data Loaders
    batch_size = 64
    num_workers = 2 if torch.cuda.is_available() else 0

    train_dataset = PTBXLDataset(train_df, data_dir, sampling_rate=100)
    val_dataset = PTBXLDataset(val_df, data_dir, sampling_rate=100)

    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True,
        num_workers=num_workers, pin_memory=torch.cuda.is_available()
    )
    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False,
        num_workers=num_workers, pin_memory=torch.cuda.is_available()
    )

    # Loss & Model Setup
    train_targets = np.vstack(train_df["label_vector"].values)
    pos_weights = compute_positive_weights(train_targets).to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weights)

    model = ResNet1D(in_channels=12, num_classes=NUM_CLASSES, base_filters=64).to(device)
    num_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"\n[Model] ResNet1D initialized with {num_params:,} trainable parameters.")

    # Optimizer & LR Scheduler
    epochs = 20
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-2)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
    scaler = torch.cuda.amp.GradScaler(enabled=torch.cuda.is_available())

    # Training Loop
    best_val_auc = 0.0
    best_epoch = 0
    best_weights_path = os.path.join(output_dir, "best_model.pth")
    history = []

    print("\n" + "=" * 60)
    print(f"{'Epoch':5s} | {'Train Loss':10s} | {'Val Loss':9s} | {'Val AUC':8s} | {'Val F1':7s} | {'Time':6s}")
    print("=" * 60)

    for epoch in range(1, epochs + 1):
        epoch_start = time.time()
        model.train()
        train_loss = 0.0

        for signals, targets in train_loader:
            signals = signals.to(device)
            targets = targets.to(device)

            optimizer.zero_grad()
            with torch.cuda.amp.autocast(enabled=torch.cuda.is_available()):
                logits = model(signals)
                loss = criterion(logits, targets)

            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()

            train_loss += loss.item() * signals.size(0)

        scheduler.step()
        train_loss = train_loss / len(train_dataset)

        # Validation on Fold 9
        val_loss, val_auc, val_f1, per_class_auc = evaluate(model, val_loader, criterion, device)
        epoch_time = time.time() - epoch_start

        print(f"{epoch:5d} | {train_loss:10.4f} | {val_loss:9.4f} | {val_auc:8.4f} | {val_f1:7.4f} | {epoch_time:5.1f}s")

        history.append({
            "epoch": epoch,
            "train_loss": train_loss,
            "val_loss": val_loss,
            "val_auc": val_auc,
            "val_f1": val_f1,
            **{f"auc_{k}": v for k, v in per_class_auc.items()},
            "lr": optimizer.param_groups[0]["lr"],
        })

        if val_auc > best_val_auc:
            best_val_auc = val_auc
            best_epoch = epoch
            torch.save(model.state_dict(), best_weights_path)
            print(f"  -> Checkpoint saved! Best Fold 9 Val AUC: {best_val_auc:.4f}")

    # Final Report on Validation Set (Fold 9)
    print("\n" + "=" * 60)
    print("TRAINING COMPLETE")
    print(f"Best Validation Epoch: {best_epoch} with Macro AUC: {best_val_auc:.4f}")
    print("=" * 60)

    # Reload best checkpoint for export
    model.load_state_dict(torch.load(best_weights_path, map_location=device))
    val_loss, best_auc, best_f1, best_per_class_auc = evaluate(model, val_loader, criterion, device)

    print("\n--- Final Validation Metrics (Fold 9) ---")
    print(f"  Macro AUC-ROC: {best_auc:.4f}")
    print(f"  Macro F1:      {best_f1:.4f}")
    print(f"  Loss:          {val_loss:.4f}")
    print("  Per-Class AUC-ROC:")
    for cls_name, auc in best_per_class_auc.items():
        print(f"    {cls_name:6s}: {auc:.4f}")

    # Save history and metrics artifacts
    history_df = pd.DataFrame(history)
    history_df.to_csv(os.path.join(output_dir, "training_history.csv"), index=False)

    # Perform actual split integrity check
    train_ecgs = set(train_df["ecg_id"])
    val_ecgs = set(val_df["ecg_id"])
    test_ecgs = set(test_df["ecg_id"])
    train_pats = set(train_df["patient_id"].dropna())
    val_pats = set(val_df["patient_id"].dropna())
    test_pats = set(test_df["patient_id"].dropna())

    ecg_disjoint = (
        len(train_ecgs.intersection(val_ecgs)) == 0 and
        len(train_ecgs.intersection(test_ecgs)) == 0 and
        len(val_ecgs.intersection(test_ecgs)) == 0
    )
    patient_disjoint = (
        len(train_pats.intersection(val_pats)) == 0 and
        len(train_pats.intersection(test_pats)) == 0 and
        len(val_pats.intersection(test_pats)) == 0
    )
    test_fold_is_10 = bool((test_df["strat_fold"] == 10).all())
    rule4_verified = bool(ecg_disjoint and patient_disjoint and test_fold_is_10)

    metrics_payload = {
        "best_epoch": int(best_epoch),
        "val_macro_auc": float(best_auc),
        "val_macro_f1": float(best_f1),
        "val_loss": float(val_loss),
        "per_class_auc": best_per_class_auc,
        "classes": DIAGNOSTIC_SUPERCLASSES,
        "num_train_records": len(train_df),
        "num_val_records": len(val_df),
        "num_test_records_held_out": len(test_df),
        "total_training_time_seconds": round(time.time() - start_time, 2),
        "rule4_verified": rule4_verified,
    }
    with open(os.path.join(output_dir, "metrics.json"), "w") as f:
        json.dump(metrics_payload, f, indent=2)

    with open(os.path.join(output_dir, "classes.json"), "w") as f:
        json.dump({
            "classes": DIAGNOSTIC_SUPERCLASSES,
            "mapping": SUPERCLASS_TO_IDX
        }, f, indent=2)

    # Export to ONNX (Rule 8)
    onnx_path = os.path.join(output_dir, "ptbxl_resnet1d.onnx")
    print(f"\n[ONNX] Exporting best model to {onnx_path}...")
    model.eval()
    dummy_input = torch.randn(1, 12, 1000, dtype=torch.float32).to(device)

    torch.onnx.export(
        model,
        dummy_input,
        onnx_path,
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=["input_ecg"],
        output_names=["logits"],
        dynamic_axes={
            "input_ecg": {0: "batch_size"},
            "logits": {0: "batch_size"}
        }
    )

    # Verify ONNX model integrity
    onnx_model = onnx.load(onnx_path)
    onnx.checker.check_model(onnx_model)
    print("[ONNX] Model checked successfully! Graph is valid.")

    # Test ONNX Runtime session inference
    ort_session = onnxruntime.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    ort_inputs = {ort_session.get_inputs()[0].name: np.random.randn(1, 12, 1000).astype(np.float32)}
    ort_outs = ort_session.run(None, ort_inputs)
    print(f"[ONNX Runtime] Test inference succeeded! Output logits shape: {ort_outs[0].shape}")

    total_time = time.time() - start_time
    print(f"\n[Pipeline] Entire run completed in {total_time/60:.2f} minutes.")
    print("=" * 60)


if __name__ == "__main__":
    main()
