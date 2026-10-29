# Model Card: Cardiac Analyst Residual 1D CNN (PTB-XL)

## Model Details
- **Architecture**: Residual 1D Convolutional Neural Network (`ResNet1D`)
- **Framework**: TensorFlow 2.x / Keras
- **Input Dimensions**: `(batch_size, 1000, 12)` — 12-lead ECG, 1,000 samples @ 100 Hz (10 seconds)
- **Output Activation**: Multi-label Sigmoid (5 independent binary probabilities)
- **Target Superclasses**: `NORM` (Normal), `MI` (Myocardial Infarction), `STTC` (ST/T Changes), `CD` (Conduction Disturbance), `HYP` (Hypertrophy)
- **Training Date**: 2026-10-25
- **Kaggle Kernel**: `cyberfocus2410/cardiac-analyst-phase-4-full-training`
- **Trained Artifact**: `best_model.keras`

## Intended Use
- **Primary Use**: Educational and research demonstration of deep learning for automated 12-lead ECG classification.
- **Out of Scope**: Direct primary diagnosis, triage decisions without clinical review, or use as an autonomous medical diagnostic device.

## Training Data & Methodology
- **Dataset**: PhysioNet PTB-XL (v1.0.3), official 100 Hz records (`records100/`).
- **Data Splits**:
  - **Training**: Folds 1–8 (17084 records, 14823 unique patients).
  - **Validation**: Fold 9 (2146 records, 1917 unique patients).
  - **Held-Out Test**: Fold 10 (2158 records, 1877 unique patients). Evaluated strictly once.
  - **Patient Leakage**: Verified **0 patient overlap** between splits.
- **Preprocessing**: Per-lead z-score standardization computed **strictly on Folds 1–8** training set.
- **Augmentation (Train Only)**: Small physiological amplitude scaling (0.95–1.05), random time shift (±20 samples), slight Gaussian noise (sigma 0.005).
- **Optimization**: AdamW optimizer, Cosine Decay schedule, Weighted Binary Cross-Entropy loss for class imbalance.
- **Early Stopping**: Monitored Validation Macro-AUROC on Fold 9 (Patience = 5).

## Evaluation Metrics (Fold 10 Single-Pass Held-Out Test)
- **Macro AUROC**: **0.9265** (95% CI: [0.9194, 0.9330])
- **Macro AUPRC**: **0.8196** (95% CI: [0.8038, 0.8351])
- **Macro F1**: **0.752** (95% CI: [0.7350, 0.7658])
- **Macro Sensitivity**: **0.7725**
- **Macro Specificity**: **0.8985**

## Limitations & Ethical Considerations
- Not a certified medical device.
- Lower sensitivity on Hypertrophy (55.73%) due to low class prevalence and subtle voltage variations.
- False negative rate for Myocardial Infarction is 20.00%; must never replace emergency medical evaluation.
