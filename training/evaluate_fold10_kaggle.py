"""
Phase 5: Single-Pass Fold 10 Test Evaluation on Kaggle GPU
==========================================================
Strictly evaluates the trained ResNet-1D model on the 2,158 held-out records
of Fold 10 from PhysioNet's PTB-XL (v1.0.3) dataset.

Zero Fabrication Rule: All numbers printed and saved are computed on real PTB-XL records.
Single Pass Rule: Fold 10 was strictly held out and is evaluated once.
"""

import os
import sys
import json
import ast
import time
import traceback
from pathlib import Path

# Enable unbuffered stdout so all prints are immediately visible in Kaggle logs
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, f1_score, confusion_matrix, precision_score, recall_score
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# Check GPU
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print(f"[Device] Using: {device}")
if torch.cuda.is_available():
    print(f"[GPU Name] {torch.cuda.get_device_name(0)}")

# -------------------------------------------------------------
# 1. Dataset & Preprocessing Constants
# -------------------------------------------------------------
DIAGNOSTIC_SUPERCLASSES = ["NORM", "MI", "STTC", "CD", "HYP"]
SUPERCLASS_TO_IDX = {cls_name: idx for idx, cls_name in enumerate(DIAGNOSTIC_SUPERCLASSES)}
NUM_CLASSES = len(DIAGNOSTIC_SUPERCLASSES)
LEAD_NAMES = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]


def locate_ptbxl_dataset() -> str:
    """Find PTB-XL dataset directory in Kaggle or local environments."""
    candidate_paths = [
        "/kaggle/input/ptb-xl-1-0-3/ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3",
        "/kaggle/input/ptb-xl-1-0-3",
        "/kaggle/input/ptb-xl-dataset",
        "./ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3",
        "../ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3",
    ]
    for p in candidate_paths:
        if os.path.exists(os.path.join(p, "ptbxl_database.csv")):
            print(f"[Dataset] Located PTB-XL at: {p}")
            return p

    # Recursive search in /kaggle/input
    if os.path.exists("/kaggle/input"):
        for root, dirs, files in os.walk("/kaggle/input"):
            if "ptbxl_database.csv" in files:
                print(f"[Dataset] Found PTB-XL via walk at: {root}")
                return root

    raise FileNotFoundError("Could not find PTB-XL dataset containing ptbxl_database.csv.")


def locate_model_checkpoint() -> str:
    """Find best_model.pth checkpoint in Kaggle input or local environments."""
    candidate_paths = [
        "/kaggle/input/datasets/cyberfocus2410/cardiac-analyst-model/best_model.pth",
        "/kaggle/input/cardiac-analyst-model/best_model.pth",
        "/kaggle/input/cardiac-analyst-ptb-xl-training/best_model.pth",
        "best_model.pth",
        "scratch/model_dataset/best_model.pth",
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            print(f"[Model Checkpoint] Located model at: {p}")
            return p

    if os.path.exists("/kaggle/input"):
        for root, dirs, files in os.walk("/kaggle/input"):
            if "best_model.pth" in files:
                path = os.path.join(root, "best_model.pth")
                print(f"[Model Checkpoint] Found model via walk at: {path}")
                return path

    raise FileNotFoundError("Could not find best_model.pth in /kaggle/input.")


def parse_and_aggregate_labels(df: pd.DataFrame, scp_statements_path: str) -> pd.DataFrame:
    """
    Map SCP codes in ptbxl_database.csv to the 5 official diagnostic superclasses.
    Filters records to ensure each has at least one valid diagnostic superclass.
    """
    if not os.path.exists(scp_statements_path):
        raise FileNotFoundError(f"scp_statements.csv not found at: {scp_statements_path}")

    scp_df = pd.read_csv(scp_statements_path, index_col=0)
    diag_scp = scp_df[scp_df["diagnostic"] == 1.0]

    code_to_superclass = {}
    for code, row in diag_scp.iterrows():
        diag_class = row["diagnostic_class"]
        if pd.notna(diag_class) and str(diag_class) in DIAGNOSTIC_SUPERCLASSES:
            code_to_superclass[code] = str(diag_class)

    def extract_superclasses(scp_str):
        if isinstance(scp_str, str):
            try:
                scp_dict = ast.literal_eval(scp_str)
            except Exception:
                return []
        elif isinstance(scp_str, dict):
            scp_dict = scp_str
        else:
            return []

        classes = set()
        for code in scp_dict.keys():
            if code in code_to_superclass:
                classes.add(code_to_superclass[code])
        return sorted(list(classes))

    df["diagnostic_superclass"] = df["scp_codes"].apply(extract_superclasses)
    clean_df = df[df["diagnostic_superclass"].apply(lambda x: len(x) > 0)].copy()

    targets = np.zeros((len(clean_df), NUM_CLASSES), dtype=np.float32)
    for row_idx, classes in enumerate(clean_df["diagnostic_superclass"]):
        for cls_name in classes:
            col_idx = SUPERCLASS_TO_IDX[cls_name]
            targets[row_idx, col_idx] = 1.0

    clean_df["label_vector"] = list(targets)
    return clean_df


def load_raw_waveform(file_path_no_ext: str) -> np.ndarray:
    """Read WFDB 12-lead record."""
    import wfdb
    signal, fields = wfdb.rdsamp(file_path_no_ext)
    signal = signal.T.astype(np.float32)
    signal = np.nan_to_num(signal, nan=0.0, posinf=0.0, neginf=0.0)

    # Lead-wise standardization
    mean = np.mean(signal, axis=-1, keepdims=True)
    std = np.std(signal, axis=-1, keepdims=True)
    std = np.where(std < 1e-6, 1.0, std)
    signal = (signal - mean) / std
    signal = np.clip(signal, -10.0, 10.0)
    return signal


class PTBXLDataset(Dataset):
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

        if signal.shape[1] > self.target_length:
            signal = signal[:, :self.target_length]
        elif signal.shape[1] < self.target_length:
            pad_len = self.target_length - signal.shape[1]
            signal = np.pad(signal, ((0, 0), (0, pad_len)), mode="constant")

        target = np.array(row["label_vector"], dtype=np.float32)
        ecg_id = int(row["ecg_id"])
        return torch.tensor(signal, dtype=torch.float32), torch.tensor(target, dtype=torch.float32), ecg_id


# -------------------------------------------------------------
# 2. Residual 1D CNN Architecture
# -------------------------------------------------------------
class ConvBlock1D(nn.Module):
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
    def __init__(self, in_channels: int = 12, num_classes: int = 5, base_filters: int = 64):
        super().__init__()
        self.in_channels = in_channels
        self.num_classes = num_classes

        self.stem = nn.Sequential(
            nn.Conv1d(in_channels, base_filters, kernel_size=15, stride=2, padding=7, bias=False),
            nn.BatchNorm1d(base_filters),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=3, stride=2, padding=1)
        )

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

        self.global_pool = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(p=0.3)
        self.fc = nn.Linear(base_filters * 8, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.stem(x)
        out = self.stage1(out)
        out = self.stage2(out)
        out = self.stage3(out)
        out = self.stage4(out)
        out = self.global_pool(out)
        out = torch.flatten(out, 1)
        out = self.dropout(out)
        logits = self.fc(out)
        return logits


# -------------------------------------------------------------
# 3. Evaluation Main Execution
# -------------------------------------------------------------
def main():
    start_time = time.time()
    out_dir = "/kaggle/working" if os.path.exists("/kaggle") else "./outputs"
    os.makedirs(out_dir, exist_ok=True)

    print("=================================================================")
    print("  CARDIAC ANALYST — PHASE 5 FOLD 10 SINGLE-PASS EVALUATION")
    print("=================================================================")

    # Install wfdb if missing
    try:
        import wfdb
    except ImportError:
        print("[Setup] Installing wfdb...")
        os.system("pip install --quiet wfdb")
        import wfdb

    data_dir = locate_ptbxl_dataset()
    db_csv = os.path.join(data_dir, "ptbxl_database.csv")
    scp_csv = os.path.join(data_dir, "scp_statements.csv")

    model_path = locate_model_checkpoint()

    raw_df = pd.read_csv(db_csv)
    print(f"[Dataset] Total raw database records: {len(raw_df)}")

    clean_df = parse_and_aggregate_labels(raw_df, scp_csv)
    print(f"[Dataset] Clean diagnostic records: {len(clean_df)}")

    test_df = clean_df[clean_df["strat_fold"] == 10].reset_index(drop=True)
    print(f"[Dataset Split - Rule 4] Strictly Held-Out Fold 10 records: {len(test_df)}")
    assert len(test_df) == 2158, f"Expected 2158 Fold 10 records, got {len(test_df)}"

    test_dataset = PTBXLDataset(test_df, data_dir, sampling_rate=100)
    test_loader = DataLoader(
        test_dataset,
        batch_size=64,
        shuffle=False,
        num_workers=2 if torch.cuda.is_available() else 0,
        pin_memory=torch.cuda.is_available()
    )

    # Load Model
    model = ResNet1D(in_channels=12, num_classes=NUM_CLASSES, base_filters=64).to(device)
    state_dict = torch.load(model_path, map_location=device, weights_only=True)
    model.load_state_dict(state_dict)
    model.eval()
    print(f"[Model Ready] ResNet1D loaded onto {device}")

    all_probs = []
    all_targets = []
    all_ecg_ids = []

    print(f"[Inference] Running forward pass on {len(test_df)} Fold 10 test records...")
    with torch.no_grad():
        for signals, targets, ecg_ids in test_loader:
            signals = signals.to(device)
            logits = model(signals)
            probs = torch.sigmoid(logits).cpu().numpy()

            all_probs.append(probs)
            all_targets.append(targets.numpy())
            all_ecg_ids.extend(ecg_ids.numpy().tolist())

    y_probs = np.vstack(all_probs)
    y_true = np.vstack(all_targets)

    print(f"[Inference Complete] Evaluated {len(y_probs)} records across {NUM_CLASSES} classes.")

    # -------------------------------------------------------------
    # Metrics Computation
    # -------------------------------------------------------------
    macro_auc = roc_auc_score(y_true, y_probs, average="macro")
    micro_auc = roc_auc_score(y_true, y_probs, average="micro")

    per_class_auc = {}
    for i, cls_name in enumerate(DIAGNOSTIC_SUPERCLASSES):
        per_class_auc[cls_name] = float(roc_auc_score(y_true[:, i], y_probs[:, i]))

    y_pred_bin = (y_probs >= 0.5).astype(int)
    macro_f1 = float(f1_score(y_true, y_pred_bin, average="macro", zero_division=0))
    micro_f1 = float(f1_score(y_true, y_pred_bin, average="micro", zero_division=0))

    per_class_metrics = {}
    for i, cls_name in enumerate(DIAGNOSTIC_SUPERCLASSES):
        y_t = y_true[:, i].astype(int)
        y_p = y_pred_bin[:, i]
        tn, fp, fn, tp = confusion_matrix(y_t, y_p, labels=[0, 1]).ravel()

        sensitivity = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0
        precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        f1 = float(f1_score(y_t, y_p, zero_division=0))

        per_class_metrics[cls_name] = {
            "auc": per_class_auc[cls_name],
            "sensitivity_recall": sensitivity,
            "specificity": specificity,
            "precision": precision,
            "f1": f1,
            "true_positives": int(tp),
            "false_positives": int(fp),
            "true_negatives": int(tn),
            "false_negatives": int(fn),
            "total_positive_cases": int(tp + fn),
            "total_negative_cases": int(tn + fp),
        }

    elapsed = time.time() - start_time

    # -------------------------------------------------------------
    # Printed Report (Direct printed output for audit and logs)
    # -------------------------------------------------------------
    report_lines = [
        "=" * 75,
        "             CARDIAC ANALYST — FOLD 10 TEST METRICS REPORT",
        "=" * 75,
        f"Total Held-Out Test Records: {len(test_df)}",
        f"Evaluation Runtime         : {elapsed:.2f} seconds",
        f"Overall Macro AUC-ROC      : {macro_auc:.4f}",
        f"Overall Micro AUC-ROC      : {micro_auc:.4f}",
        f"Overall Macro F1 (th=0.5)  : {macro_f1:.4f}",
        f"Overall Micro F1 (th=0.5)  : {micro_f1:.4f}",
        "-" * 75,
        f"{'Class':<8} | {'AUC-ROC':<8} | {'Sensitivity':<11} | {'Specificity':<11} | {'F1':<6} | {'TP':<4} | {'FP':<4} | {'TN':<5} | {'FN':<4}",
        "-" * 75,
    ]
    for cls_name in DIAGNOSTIC_SUPERCLASSES:
        m = per_class_metrics[cls_name]
        report_lines.append(
            f"{cls_name:<8} | {m['auc']:<8.4f} | {m['sensitivity_recall']:<11.4f} | {m['specificity']:<11.4f} | {m['f1']:<6.4f} | {m['true_positives']:<4} | {m['false_positives']:<4} | {m['true_negatives']:<5} | {m['false_negatives']:<4}"
        )
    report_lines.append("=" * 75)

    full_report = "\n".join(report_lines)
    print("\n" + full_report)

    with open(os.path.join(out_dir, "fold10_test_report.txt"), "w") as f:
        f.write(full_report)

    # -------------------------------------------------------------
    # 4. Extract 5 Real Test Sample Waveforms (one per class)
    # -------------------------------------------------------------
    print("\n[Sample Extraction] Extracting 5 real PTB-XL sample test ECGs for local frontend/backend testing...")
    samples = {}

    for i, cls_name in enumerate(DIAGNOSTIC_SUPERCLASSES):
        pos_indices = np.where(y_true[:, i] == 1.0)[0]
        best_idx = pos_indices[np.argmax(y_probs[pos_indices, i])]

        row = test_df.iloc[best_idx]
        ecg_id = int(row["ecg_id"])
        patient_id = float(row["patient_id"])

        sig, meta = wfdb.rdsamp(os.path.join(data_dir, row["filename_lr"]))

        csv_filename = os.path.join(out_dir, f"sample_ecg_{cls_name}.csv")
        df_sig = pd.DataFrame(sig, columns=LEAD_NAMES)
        df_sig.to_csv(csv_filename, index=False)
        print(f"   - Saved {os.path.basename(csv_filename)} (ECG ID {ecg_id}, True: {cls_name}, Pred Prob: {y_probs[best_idx, i]:.4f})")

        samples[cls_name] = {
            "ecg_id": ecg_id,
            "patient_id": patient_id,
            "filename_lr": row["filename_lr"],
            "target_class": cls_name,
            "true_classes": [DIAGNOSTIC_SUPERCLASSES[k] for k, v in enumerate(y_true[best_idx]) if v == 1.0],
            "predicted_probs": {DIAGNOSTIC_SUPERCLASSES[k]: float(y_probs[best_idx, k]) for k in range(5)},
            "sampling_rate_hz": 100,
            "sequence_length": len(sig),
            "lead_names": LEAD_NAMES,
            "signal_12x1000": sig.T.tolist(),
        }

    with open(os.path.join(out_dir, "sample_test_records.json"), "w") as f:
        json.dump(samples, f, indent=2)
    print("   - Saved sample_test_records.json with all 5 verified sample waveforms.")

    strat_fold_is_10_all = bool((test_df["strat_fold"] == 10).all())
    ecg_id_unique = bool(test_df["ecg_id"].is_unique) if "ecg_id" in test_df.columns else bool(pd.Series(all_ecg_ids).is_unique)

    # -------------------------------------------------------------
    # 5. Save Final Results JSON
    # -------------------------------------------------------------
    final_results = {
        "dataset": "PTB-XL v1.0.3",
        "held_out_fold": 10,
        "num_test_records": len(test_df),
        "macro_auc": float(macro_auc),
        "micro_auc": float(micro_auc),
        "macro_f1": float(macro_f1),
        "micro_f1": float(micro_f1),
        "per_class_metrics": per_class_metrics,
        "classes": DIAGNOSTIC_SUPERCLASSES,
        "runtime_seconds": float(elapsed),
        "checkpoint_path": model_path,
        "verification_facts": {
            "all_rows_strat_fold_10": strat_fold_is_10_all,
            "ecg_ids_unique": ecg_id_unique,
            "evaluated_record_count": len(test_df),
        }
    }

    with open(os.path.join(out_dir, "fold10_test_results.json"), "w") as f:
        json.dump(final_results, f, indent=2)
    print("\n[Done] All results and sample records saved successfully to working directory.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        traceback.print_exc()
        out_dir = "/kaggle/working" if os.path.exists("/kaggle") else "./outputs"
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "error.txt"), "w") as f:
            traceback.print_exc(file=f)
        sys.exit(1)
