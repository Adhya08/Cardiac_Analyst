"""
Configuration module for PTB-XL 12-lead ECG Training Pipeline.
==============================================================
Defines dataset paths, constants, signal dimensions, and training hyperparameters.
"""
import os

# -------------------------------------------------------------
# 1. Dataset & Class Definitions
# -------------------------------------------------------------
DIAGNOSTIC_SUPERCLASSES = ["NORM", "MI", "STTC", "CD", "HYP"]
SUPERCLASS_TO_IDX = {cls_name: idx for idx, cls_name in enumerate(DIAGNOSTIC_SUPERCLASSES)}
NUM_CLASSES = len(DIAGNOSTIC_SUPERCLASSES)

STANDARD_LEAD_ORDER = ["I", "II", "III", "aVR", "aVL", "aVF", "V1", "V2", "V3", "V4", "V5", "V6"]
SAMPLING_RATE = 100
SIGNAL_LENGTH = 1000  # 10 seconds at 100 Hz
NUM_LEADS = 12
RAW_SIGNAL_SHAPE = (SIGNAL_LENGTH, NUM_LEADS)  # (1000, 12)
TORCH_SIGNAL_SHAPE = (NUM_LEADS, SIGNAL_LENGTH)  # (12, 1000)

# Strict Split Definition (Rule 4)
TRAIN_FOLDS = list(range(1, 9))  # Folds 1–8
VAL_FOLDS = [9]                  # Fold 9
TEST_FOLDS = [10]                # Fold 10 (Strictly held-out)

# -------------------------------------------------------------
# 2. Hyperparameters
# -------------------------------------------------------------
BATCH_SIZE = 64
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-2
SMOKE_TEST_EPOCHS = 2
FULL_EPOCHS = 20
SMOKE_TEST_MAX_TRAIN_SAMPLES = 500
SMOKE_TEST_MAX_VAL_SAMPLES = 100

# -------------------------------------------------------------
# 3. Path Resolution
# -------------------------------------------------------------
DEFAULT_LOCAL_DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "scratch", "ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3")
)

KAGGLE_DATA_DIR_CANDIDATES = [
    "/kaggle/input/ptb-xl-1-0-3/ptb-xl-a-large-publicly-available-electrocardiography-dataset-1.0.3",
    "/kaggle/input/ptb-xl-1-0-3",
    "/kaggle/input/ptb-xl-dataset",
]

PREPROCESSING_CONFIG_FILE = os.path.join(os.path.dirname(__file__), "preprocessing_config.json")
