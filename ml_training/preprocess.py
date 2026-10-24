"""
PTB-XL ECG Preprocessing Module
================================
Enforces:
- Fixed lead order: ['I', 'II', 'III', 'aVR', 'aVL', 'aVF', 'V1', 'V2', 'V3', 'V4', 'V5', 'V6']
- Standard signal shape: (1000, 12) at 100 Hz in float32
- Per-lead normalization computed strictly on the TRAINING set (Folds 1–8)
- Serialization to JSON config so inference can reuse it identically.
"""
import os
import json
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from .config import (
    STANDARD_LEAD_ORDER,
    SAMPLING_RATE,
    SIGNAL_LENGTH,
    NUM_LEADS,
    RAW_SIGNAL_SHAPE,
    DIAGNOSTIC_SUPERCLASSES,
    PREPROCESSING_CONFIG_FILE,
)


class ECGPreprocessor:
    """
    Standardizes 12-lead ECG signals:
    1. Reorders channels to match STANDARD_LEAD_ORDER.
    2. Resizes / pads / crops signal to exact length (1000 samples @ 100 Hz).
    3. Normalizes leads using precomputed training set statistics: (signal - lead_mean) / lead_std.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.lead_order = list(STANDARD_LEAD_ORDER)
        self.sampling_rate = SAMPLING_RATE
        self.signal_length = SIGNAL_LENGTH
        self.num_leads = NUM_LEADS
        self.labels = list(DIAGNOSTIC_SUPERCLASSES)

        # Default standard physiological ECG scales (baseline ~0 mV, std ~0.2 mV)
        # Will be overwritten with exact training set stats when fitted or loaded
        self.lead_means = np.zeros(self.num_leads, dtype=np.float32)
        self.lead_stds = np.ones(self.num_leads, dtype=np.float32)
        self.is_fitted = False

        if config_path and os.path.exists(config_path):
            self.load_config(config_path)

    def fit_from_training_signals(self, train_signals_list: List[np.ndarray]) -> "ECGPreprocessor":
        """
        Compute per-lead mean and std strictly on training set signals.
        Each signal should be shape (1000, 12) or (12, 1000).
        """
        if len(train_signals_list) == 0:
            raise ValueError("Cannot fit on empty training signals list.")

        # Ensure all signals are (1000, 12)
        standardized = []
        for sig in train_signals_list:
            if sig.shape == (self.num_leads, self.signal_length):
                sig = sig.T  # Transpose to (1000, 12)
            elif sig.shape != (self.signal_length, self.num_leads):
                raise ValueError(f"Unexpected signal shape {sig.shape}, expected (1000, 12) or (12, 1000)")
            standardized.append(sig)

        all_signals = np.stack(standardized, axis=0)  # (N, 1000, 12)

        # Compute mean and std per lead across samples and time steps
        means = np.mean(all_signals, axis=(0, 1)).astype(np.float32)
        stds = np.std(all_signals, axis=(0, 1)).astype(np.float32)
        stds = np.where(stds < 1e-6, 1.0, stds).astype(np.float32)

        self.lead_means = means
        self.lead_stds = stds
        self.is_fitted = True
        return self

    def set_stats(self, lead_means: np.ndarray, lead_stds: np.ndarray) -> "ECGPreprocessor":
        """Directly set per-lead normalization parameters computed from training set."""
        assert len(lead_means) == self.num_leads, f"Expected {self.num_leads} lead means"
        assert len(lead_stds) == self.num_leads, f"Expected {self.num_leads} lead stds"
        self.lead_means = np.array(lead_means, dtype=np.float32)
        self.lead_stds = np.where(np.array(lead_stds, dtype=np.float32) < 1e-6, 1.0, np.array(lead_stds, dtype=np.float32))
        self.is_fitted = True
        return self

    def preprocess_signal(self, raw_signal: np.ndarray, current_lead_names: Optional[List[str]] = None) -> np.ndarray:
        """
        Preprocess a single raw ECG signal to shape (1000, 12) float32.

        Args:
            raw_signal: array of shape (samples, leads) or (leads, samples).
            current_lead_names: list of lead names if signal needs reordering.

        Returns:
            Preprocessed normalized signal of shape (1000, 12) in float32.
        """
        sig = np.array(raw_signal, dtype=np.float32)

        # Transpose if channels-first: (12, N) -> (N, 12)
        if sig.ndim == 2 and sig.shape[0] == self.num_leads and sig.shape[1] != self.num_leads:
            sig = sig.T

        # Reorder leads if names provided
        if current_lead_names is not None:
            name_to_idx = {name.upper(): i for i, name in enumerate(current_lead_names)}
            reordered = []
            for target_name in self.lead_order:
                t_upper = target_name.upper()
                if t_upper in name_to_idx:
                    reordered.append(sig[:, name_to_idx[t_upper]])
                else:
                    # Fallback zero lead if missing
                    reordered.append(np.zeros(sig.shape[0], dtype=np.float32))
            sig = np.stack(reordered, axis=-1)

        # Handle NaNs and Infs
        sig = np.nan_to_num(sig, nan=0.0, posinf=0.0, neginf=0.0)

        # Ensure exact length of 1000 samples (10 seconds @ 100 Hz)
        if sig.shape[0] > self.signal_length:
            sig = sig[:self.signal_length, :]
        elif sig.shape[0] < self.signal_length:
            pad = self.signal_length - sig.shape[0]
            sig = np.pad(sig, ((0, pad), (0, 0)), mode="edge")

        # Per-lead normalization using training set statistics
        normalized = (sig - self.lead_means) / self.lead_stds
        normalized = np.clip(normalized, -10.0, 10.0).astype(np.float32)

        assert normalized.shape == RAW_SIGNAL_SHAPE, f"Expected shape {RAW_SIGNAL_SHAPE}, got {normalized.shape}"
        assert normalized.dtype == np.float32, f"Expected float32, got {normalized.dtype}"
        return normalized

    def to_torch_channels_first(self, preprocessed_signal: np.ndarray) -> np.ndarray:
        """
        Convert shape (1000, 12) -> (12, 1000) for PyTorch Conv1d input.
        """
        assert preprocessed_signal.shape == (self.signal_length, self.num_leads)
        return preprocessed_signal.T.astype(np.float32)

    def save_config(self, out_path: Optional[str] = None) -> str:
        """Save preprocessing configuration to JSON for exact reuse in inference."""
        if out_path is None:
            out_path = PREPROCESSING_CONFIG_FILE

        config_data = {
            "dataset": "PhysioNet PTB-XL v1.0.3",
            "lead_order": self.lead_order,
            "sampling_rate": self.sampling_rate,
            "signal_shape": list(RAW_SIGNAL_SHAPE),
            "torch_signal_shape": [self.num_leads, self.signal_length],
            "labels": self.labels,
            "normalization": {
                "method": "per_lead_z_score",
                "computed_on": "Folds 1-8 (Training set only)",
                "lead_means": [float(m) for m in self.lead_means],
                "lead_stds": [float(s) for s in self.lead_stds],
            },
        }

        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)

        return out_path

    def load_config(self, config_path: str):
        """Load preprocessing configuration from JSON."""
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.lead_order = data["lead_order"]
        self.sampling_rate = data["sampling_rate"]
        self.labels = data["labels"]
        norm = data["normalization"]
        self.lead_means = np.array(norm["lead_means"], dtype=np.float32)
        self.lead_stds = np.array(norm["lead_stds"], dtype=np.float32)
        self.is_fitted = True
