"""
PTB-XL Dataset Loader & Preprocessing
-------------------------------------
Official PhysioNet PTB-XL (v1.0.3) 12-lead ECG Dataset.
Strict Data Splitting:
  - Folds 1–8: Training
  - Fold 9: Validation
  - Fold 10: Hold-out Test (STRICTLY untouched during training/tuning)

Diagnostic Superclasses (5 classes):
  - NORM: Normal ECG
  - MI: Myocardial Infarction
  - STTC: ST/T Changes
  - CD: Conduction Disturbance
  - HYP: Hypertrophy
"""

import os
import ast
import numpy as np
import pandas as pd
import wfdb

try:
    import torch
    from torch.utils.data import Dataset
except ImportError:
    torch = None
    Dataset = object

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
    # Only consider statements designated as diagnostic
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
    # Keep only records that have at least one diagnostic superclass
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
    # signal is (samples, 12). Transpose to channels-first: (12, samples)
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
