"""
PTB-XL Data Loading Module
==========================
Loads PTB-XL metadata (ptbxl_database.csv, scp_statements.csv) and 100 Hz signals (records100)
using the wfdb library.

Maps SCP codes to the 5 official diagnostic superclasses:
  - NORM: Normal ECG
  - MI: Myocardial Infarction
  - STTC: ST/T Changes
  - CD: Conduction Disturbance
  - HYP: Hypertrophy

Enforces strict fold splitting based on the official 'strat_fold' column:
  - Folds 1–8: Training (17,084 clean diagnostic records)
  - Fold 9: Validation (2,146 clean diagnostic records)
  - Fold 10: Hold-out Test (2,158 clean diagnostic records)
"""
import os
import ast
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
import wfdb

try:
    import torch
    from torch.utils.data import Dataset, DataLoader
except ImportError:
    torch = None
    Dataset = object
    DataLoader = None

from .config import (
    DIAGNOSTIC_SUPERCLASSES,
    SUPERCLASS_TO_IDX,
    NUM_CLASSES,
    TRAIN_FOLDS,
    VAL_FOLDS,
    TEST_FOLDS,
    DEFAULT_LOCAL_DATA_DIR,
    KAGGLE_DATA_DIR_CANDIDATES,
    BATCH_SIZE,
)
from .preprocess import ECGPreprocessor


def locate_dataset(custom_path: Optional[str] = None) -> str:
    """
    Locate the PTB-XL root directory containing ptbxl_database.csv and scp_statements.csv.
    """
    if custom_path and os.path.exists(os.path.join(custom_path, "ptbxl_database.csv")):
        return custom_path

    # Check local default path
    if os.path.exists(os.path.join(DEFAULT_LOCAL_DATA_DIR, "ptbxl_database.csv")):
        return DEFAULT_LOCAL_DATA_DIR

    # Check Kaggle candidate paths
    for p in KAGGLE_DATA_DIR_CANDIDATES:
        if os.path.exists(os.path.join(p, "ptbxl_database.csv")):
            return p

    # Recursive check in /kaggle/input
    if os.path.exists("/kaggle/input"):
        for root, _, files in os.walk("/kaggle/input"):
            if "ptbxl_database.csv" in files and "scp_statements.csv" in files:
                return root

    # Relative paths
    rel_paths = [
        "scratch/ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3",
        "../scratch/ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3",
        "data/ptb-xl",
        "../data/ptb-xl",
    ]
    for p in rel_paths:
        if os.path.exists(os.path.join(p, "ptbxl_database.csv")):
            return os.path.abspath(p)

    raise FileNotFoundError(
        "Could not find PTB-XL dataset directory containing ptbxl_database.csv and scp_statements.csv."
    )


def load_metadata_and_map_labels(data_dir: str) -> pd.DataFrame:
    """
    Load ptbxl_database.csv and scp_statements.csv, then map raw SCP statements
    to the 5 official diagnostic superclasses using the standard PTB-XL benchmark approach.
    """
    db_csv = os.path.join(data_dir, "ptbxl_database.csv")
    scp_csv = os.path.join(data_dir, "scp_statements.csv")

    if not os.path.exists(db_csv):
        raise FileNotFoundError(f"ptbxl_database.csv not found at: {db_csv}")
    if not os.path.exists(scp_csv):
        raise FileNotFoundError(f"scp_statements.csv not found at: {scp_csv}")

    df = pd.read_csv(db_csv, index_col="ecg_id")
    scp_df = pd.read_csv(scp_csv, index_col=0)

    # Filter for diagnostic SCP statements only
    diag_scp = scp_df[scp_df["diagnostic"] == 1.0]

    # Convert string dict to python dict
    if isinstance(df["scp_codes"].iloc[0], str):
        df["scp_codes"] = df["scp_codes"].apply(lambda x: ast.literal_eval(x) if isinstance(x, str) else x)

    def aggregate_diagnostic(scp_codes: dict) -> List[str]:
        classes = set()
        for code in scp_codes.keys():
            if code in diag_scp.index:
                d_class = diag_scp.loc[code, "diagnostic_class"]
                if pd.notna(d_class) and d_class in SUPERCLASS_TO_IDX:
                    classes.add(d_class)
        return list(classes)

    df["diagnostic_superclass"] = df["scp_codes"].apply(aggregate_diagnostic)

    # Keep records that have at least one diagnostic superclass
    clean_df = df[df["diagnostic_superclass"].apply(lambda x: len(x) > 0)].copy()

    # Construct multi-label one-hot target vectors
    targets = np.zeros((len(clean_df), NUM_CLASSES), dtype=np.float32)
    for row_idx, classes in enumerate(clean_df["diagnostic_superclass"]):
        for cls_name in classes:
            targets[row_idx, SUPERCLASS_TO_IDX[cls_name]] = 1.0

    clean_df["label_vector"] = list(targets)
    return clean_df


def split_dataset(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Strict split on the official 'strat_fold' column:
    - Folds 1–8: Train
    - Fold 9: Validation
    - Fold 10: Test (Strictly held-out)
    """
    train_df = df[df["strat_fold"].isin(TRAIN_FOLDS)].copy()
    val_df = df[df["strat_fold"].isin(VAL_FOLDS)].copy()
    test_df = df[df["strat_fold"].isin(TEST_FOLDS)].copy()
    return train_df, val_df, test_df


def load_raw_wfdb_signal(file_path_no_ext: str) -> Tuple[np.ndarray, List[str]]:
    """
    Read WFDB 12-lead record. Returns:
      signal: ndarray of shape (samples, leads) in float32.
      lead_names: list of lead strings from the WFDB header.
    """
    signal, fields = wfdb.rdsamp(file_path_no_ext)
    signal = signal.astype(np.float32)
    lead_names = fields.get("sig_name", [])
    return signal, lead_names


class PTBXLDataset(Dataset):
    """
    PyTorch Dataset for PTB-XL 12-Lead ECG records.
    Preprocesses signals into shape (12, 1000) for 1D CNN training.
    """

    def __init__(
        self,
        df: pd.DataFrame,
        base_data_dir: str,
        preprocessor: ECGPreprocessor,
        sampling_rate: int = 100,
        max_samples: Optional[int] = None,
    ):
        self.df = df.reset_index(drop=False)
        if max_samples is not None and max_samples < len(self.df):
            self.df = self.df.iloc[:max_samples].copy()

        self.base_data_dir = base_data_dir
        self.preprocessor = preprocessor
        self.sampling_rate = sampling_rate
        self.filename_col = "filename_lr" if sampling_rate == 100 else "filename_hr"

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int):
        row = self.df.iloc[idx]
        rel_path = row[self.filename_col]
        full_path_no_ext = os.path.join(self.base_data_dir, rel_path)

        # 1. Load WFDB raw signal
        raw_signal, lead_names = load_raw_wfdb_signal(full_path_no_ext)

        # 2. Preprocess: fixed lead order, exact (1000, 12) shape, per-lead z-score normalization
        norm_signal_1000_12 = self.preprocessor.preprocess_signal(raw_signal, current_lead_names=lead_names)

        # 3. Transpose to PyTorch Conv1d format: (12, 1000)
        torch_signal_12_1000 = self.preprocessor.to_torch_channels_first(norm_signal_1000_12)

        target = np.array(row["label_vector"], dtype=np.float32)

        return (
            torch.tensor(torch_signal_12_1000, dtype=torch.float32),
            torch.tensor(target, dtype=torch.float32),
        )


def get_dataloaders(
    data_dir: str,
    preprocessor: ECGPreprocessor,
    batch_size: int = BATCH_SIZE,
    num_workers: int = 0,
    smoke_test_subset: Optional[Tuple[int, int]] = None,
) -> Tuple[DataLoader, DataLoader, DataLoader, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Construct DataLoaders for Train, Validation, and Test splits.
    If smoke_test_subset is provided as (max_train, max_val), loads a tiny subset for quick verification.
    """
    df = load_metadata_and_map_labels(data_dir)
    train_df, val_df, test_df = split_dataset(df)

    max_train = smoke_test_subset[0] if smoke_test_subset else None
    max_val = smoke_test_subset[1] if smoke_test_subset else None

    train_ds = PTBXLDataset(train_df, data_dir, preprocessor, max_samples=max_train)
    val_ds = PTBXLDataset(val_df, data_dir, preprocessor, max_samples=max_val)
    test_ds = PTBXLDataset(test_df, data_dir, preprocessor, max_samples=max_val)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=num_workers)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)

    return train_loader, val_loader, test_loader, train_df, val_df, test_df
