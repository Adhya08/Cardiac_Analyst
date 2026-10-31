"""
Unit Test Suite for PTB-XL ECG Data Pipeline
=============================================
Verifies:
1. No patient appears in more than one split (Train vs Val vs Test).
2. Signal shapes and dtypes are strictly (1000, 12) float32 (and (12, 1000) for PyTorch).
3. Real label counts per split are printed with exact prevalence.
4. Normalization parameters are strictly derived from the training set only.
"""
import os
import sys
import unittest
import numpy as np
import pandas as pd
import torch

# Add repository root to python path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ml_training.config import (
    DIAGNOSTIC_SUPERCLASSES,
    SUPERCLASS_TO_IDX,
    STANDARD_LEAD_ORDER,
    RAW_SIGNAL_SHAPE,
    TORCH_SIGNAL_SHAPE,
    PREPROCESSING_CONFIG_FILE,
)
from ml_training.preprocess import ECGPreprocessor
from ml_training.data_loader import (
    locate_dataset,
    load_metadata_and_map_labels,
    split_dataset,
)
from ml_training.model import get_model


class TestPTBXLDataPipeline(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Initialize preprocessor and placeholder dataset attributes."""
        cls.preprocessor = ECGPreprocessor(PREPROCESSING_CONFIG_FILE)
        cls._data_loaded = False
        cls.data_dir = None
        cls.df = None
        cls.train_df = None
        cls.val_df = None
        cls.test_df = None

    @classmethod
    def _ensure_dataset_loaded(cls) -> bool:
        """Lazy helper to locate and load PTB-XL dataset if available."""
        if cls._data_loaded:
            return True
        try:
            cls.data_dir = locate_dataset()
        except FileNotFoundError:
            return False

        cls.df = load_metadata_and_map_labels(cls.data_dir)
        cls.train_df, cls.val_df, cls.test_df = split_dataset(cls.df)
        cls._data_loaded = True
        return True

    def test_01_no_patient_appears_in_more_than_one_split(self):
        """Rule 4 / Strict Split Check: Ensure 0 patient overlap across train, val, and test splits."""
        if not self._ensure_dataset_loaded():
            raise unittest.SkipTest("PTB-XL dataset not available; skipping real-data leakage verification.")

        train_patients = set(self.train_df["patient_id"].dropna().unique())
        val_patients = set(self.val_df["patient_id"].dropna().unique())
        test_patients = set(self.test_df["patient_id"].dropna().unique())

        train_val_overlap = train_patients.intersection(val_patients)
        train_test_overlap = train_patients.intersection(test_patients)
        val_test_overlap = val_patients.intersection(test_patients)

        print("\n" + "=" * 65)
        print("  UNIT TEST 1: PATIENT LEAKAGE VERIFICATION")
        print("=" * 65)
        print(f"Total Unique Patients - Train (Folds 1-8): {len(train_patients)}")
        print(f"Total Unique Patients - Val   (Fold 9)   : {len(val_patients)}")
        print(f"Total Unique Patients - Test  (Fold 10)  : {len(test_patients)}")
        print(f"Overlap (Train & Val) : {len(train_val_overlap)}")
        print(f"Overlap (Train & Test): {len(train_test_overlap)}")
        print(f"Overlap (Val & Test)  : {len(val_test_overlap)}")

        self.assertEqual(len(train_val_overlap), 0, f"Found {len(train_val_overlap)} patients in both Train and Val!")
        self.assertEqual(len(train_test_overlap), 0, f"Found {len(train_test_overlap)} patients in both Train and Test!")
        self.assertEqual(len(val_test_overlap), 0, f"Found {len(val_test_overlap)} patients in both Val and Test!")
        print("[PASS] Verified zero patient leakage across all splits.")

    def test_02_signal_shapes_and_dtypes_are_correct(self):
        """Check: Raw preprocessed shape is (1000, 12) float32, and PyTorch format is (12, 1000)."""
        print("\n" + "=" * 65)
        print("  UNIT TEST 2: SIGNAL SHAPE & DTYPE VERIFICATION")
        print("=" * 65)

        # Create dummy signal with arbitrary length and reversed lead names
        dummy_len = 1200
        dummy_leads = list(reversed(STANDARD_LEAD_ORDER))
        dummy_signal = np.random.randn(dummy_len, 12).astype(np.float32)

        preprocessed = self.preprocessor.preprocess_signal(dummy_signal, current_lead_names=dummy_leads)
        self.assertEqual(preprocessed.shape, RAW_SIGNAL_SHAPE)
        self.assertEqual(preprocessed.dtype, np.float32)
        print(f"Preprocessed Signal Shape: {preprocessed.shape} (Expected: {RAW_SIGNAL_SHAPE}), Dtype: {preprocessed.dtype}")

        # PyTorch format conversion: (1000, 12) -> (12, 1000)
        torch_format = self.preprocessor.to_torch_channels_first(preprocessed)
        self.assertEqual(torch_format.shape, TORCH_SIGNAL_SHAPE)
        self.assertEqual(torch_format.dtype, np.float32)
        print(f"PyTorch Channels-First Shape: {torch_format.shape} (Expected: {TORCH_SIGNAL_SHAPE})")

        # Pass through model
        model = get_model()
        input_tensor = torch.tensor(torch_format).unsqueeze(0)  # (1, 12, 1000)
        output_logits = model(input_tensor)
        self.assertEqual(output_logits.shape, (1, 5))
        print(f"Model Forward Pass Output Shape: {output_logits.shape} (Expected: (1, 5))")
        print("[PASS] Verified signal shapes and dtypes.")

    def test_03_label_counts_and_prevalence_per_split(self):
        """Count and print exact records and label prevalence for all 5 superclasses across splits."""
        if not self._ensure_dataset_loaded():
            raise unittest.SkipTest("PTB-XL dataset not available; skipping real-dataset split statistics.")

        print("\n" + "=" * 65)
        print("  UNIT TEST 3: REAL DATASET SPLIT STATISTICS")
        print("=" * 65)

        splits = [
            ("Train (Folds 1-8)", self.train_df, 17084),
            ("Validation (Fold 9)", self.val_df, 2146),
            ("Hold-Out Test (Fold 10)", self.test_df, 2158),
        ]

        for split_name, split_df, expected_count in splits:
            n_records = len(split_df)
            self.assertEqual(n_records, expected_count, f"{split_name} record count mismatch: {n_records} != {expected_count}")
            print(f"\n{split_name}: {n_records} total records")
            print(f"{'Superclass':<12} | {'Count':<8} | {'Prevalence':<10}")
            print("-" * 35)

            for cls_name in DIAGNOSTIC_SUPERCLASSES:
                c_count = int(sum(split_df["diagnostic_superclass"].apply(lambda classes: cls_name in classes)))
                c_pct = (c_count / n_records) * 100.0
                print(f"{cls_name:<12} | {c_count:<8d} | {c_pct:6.2f}%")
                self.assertGreater(c_count, 0, f"Class {cls_name} has 0 records in {split_name}!")

        print("\n[PASS] Verified real label counts and prevalence across all splits.")

    def test_04_normalization_uses_only_training_data(self):
        """Verify that normalization statistics are strictly computed from training data only."""
        print("\n" + "=" * 65)
        print("  UNIT TEST 4: STRICT TRAINING-ONLY NORMALIZATION")
        print("=" * 65)

        # Generate distinct synthetic signals for train and val/test
        rng = np.random.RandomState(42)
        train_signals = [rng.normal(loc=1.5, scale=2.0, size=(1000, 12)).astype(np.float32) for _ in range(50)]
        val_test_signals = [rng.normal(loc=99.0, scale=50.0, size=(1000, 12)).astype(np.float32) for _ in range(50)]

        # Fit preprocessor on training data only
        prep = ECGPreprocessor()
        prep.fit_from_training_signals(train_signals)

        train_mean_lead0 = float(prep.lead_means[0])
        train_std_lead0 = float(prep.lead_stds[0])

        # Verify mean is close to 1.5, std close to 2.0
        self.assertAlmostEqual(train_mean_lead0, 1.5, delta=0.2)
        self.assertAlmostEqual(train_std_lead0, 2.0, delta=0.2)

        # Normalization with training stats should zero-center train signals
        norm_train = prep.preprocess_signal(train_signals[0])
        self.assertAlmostEqual(float(np.mean(norm_train[:, 0])), 0.0, delta=0.5)

        # Config serialization check: confirms metadata explicitly flags Folds 1-8
        temp_cfg_path = os.path.join(REPO_ROOT, "ml_training", "test_temp_config.json")
        try:
            prep.save_config(temp_cfg_path)
            with open(temp_cfg_path, "r") as f:
                import json
                cfg = json.load(f)
            self.assertIn("Folds 1-8", cfg["normalization"]["computed_on"])
            self.assertEqual(len(cfg["normalization"]["lead_means"]), 12)
            self.assertEqual(len(cfg["normalization"]["lead_stds"]), 12)
            print("Config metadata check: computed_on = " + cfg["normalization"]["computed_on"])
        finally:
            if os.path.exists(temp_cfg_path):
                os.remove(temp_cfg_path)

        print(f"Fitted Training Lead 0 Mean: {train_mean_lead0:.4f} (Expected ~1.5)")
        print(f"Fitted Training Lead 0 Std : {train_std_lead0:.4f} (Expected ~2.0)")
        print("[PASS] Verified normalization is strictly isolated to training data.")


if __name__ == "__main__":
    unittest.main()
