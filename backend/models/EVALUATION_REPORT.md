# PTB-XL Fold 10 Final Evaluation Report

> **Regulatory Disclaimer**: This model is a **research and educational prototype only**. It is **not** a certified medical device and must never be used for primary clinical diagnosis or direct patient treatment.

---

## 1. Executive Summary & Macro Performance

- **Model**: Residual 1D CNN (TensorFlow/Keras, 12-lead, 1000 time steps @ 100 Hz).
- **Evaluation Dataset**: PhysioNet PTB-XL (v1.0.3) official **Fold 10** strictly held out.
- **Records Evaluated**: 2158 held-out ECG records (1877 unique patients).
- **Decision Threshold Selection**: Locked on Fold 9 (Validation) before Fold 10 evaluation.
- **Execution Date**: 2026-10-25 17:04:35 UTC.

### Macro Metrics (with 95% Confidence Intervals via 1,000 Bootstraps)

| Metric | Score | 95% Confidence Interval |
| :--- | :--- | :--- |
| **Macro AUROC** | **0.9265** | [0.9194, 0.9330] |
| **Macro AUPRC** | **0.8196** | [0.8038, 0.8351] |
| **Macro F1 Score** | **0.752** | [0.7350, 0.7658] |
| **Macro Sensitivity** | **0.7725** | [0.7546, 0.7891] |
| **Macro Specificity** | **0.8985** | [0.8924, 0.9045] |
| **Macro Precision** | **0.7382** | — |

---

## 2. Per-Class Test Performance (Fold 10)

| Class | Description | Locked Threshold | AUROC | AUPRC | Sensitivity (Recall) | Specificity | Precision | F1 Score | Brier Score |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **NORM** | NORM | 0.51 | 0.9447 | 0.9249 | 94.70% | 79.75% | 79.03% | 0.8616 | 0.1054 |
| **MI** | MI | 0.41 | 0.9244 | 0.8288 | 80.00% | 87.81% | 69.18% | 0.7420 | 0.0990 |
| **STTC** | STTC | 0.70 | 0.9351 | 0.8314 | 80.04% | 91.63% | 75.27% | 0.7758 | 0.0996 |
| **CD** | CD | 0.66 | 0.9259 | 0.8509 | 75.81% | 93.86% | 78.66% | 0.7721 | 0.0901 |
| **HYP** | HYP | 0.75 | 0.9021 | 0.6621 | 55.73% | 96.20% | 66.97% | 0.6083 | 0.0847 |

---

## 3. Confusion Counts & False-Negative Analysis

| Class | Total Positives | True Positives (TP) | False Positives (FP) | True Negatives (TN) | **False Negatives (FN)** | False Negative Rate (FNR) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **NORM** | 963 | 912 | 242 | 953 | **51** | 5.30% |
| **MI** | 550 | 440 | 196 | 1412 | **110** | 20.00% |
| **STTC** | 521 | 417 | 137 | 1500 | **104** | 19.96% |
| **CD** | 496 | 376 | 102 | 1560 | **120** | 24.19% |
| **HYP** | 262 | 146 | 72 | 1824 | **116** | 44.27% |

---

## 4. Calibration Check (Reliability & Brier Scores)

The Brier score measures the mean squared error between predicted probabilities and binary ground truth (lower is better; beating the training prior baseline confirms predictive skill over trivial guessing, though it does not guarantee calibrated probabilities). In the reliability analysis below, uncalibrated raw sigmoid outputs exhibit noticeable overconfidence in the mid-to-high probability ranges.

| Class | Model Brier Score | Prior Baseline Brier Score | Skill & Reliability Assessment |
| :--- | :--- | :--- | :--- |
| **NORM** | 0.1054 | 0.2471 | Demonstrates predictive skill over prior baseline; exhibits mid-to-high-range overconfidence |
| **MI** | 0.0990 | 0.1899 | Demonstrates predictive skill over prior baseline; exhibits mid-to-high-range overconfidence |
| **STTC** | 0.0996 | 0.1832 | Demonstrates predictive skill over prior baseline; exhibits mid-to-high-range overconfidence |
| **CD** | 0.0901 | 0.1770 | Demonstrates predictive skill over prior baseline; exhibits mid-to-high-range overconfidence |
| **HYP** | 0.0847 | 0.1067 | Demonstrates predictive skill over prior baseline; exhibits mid-to-high-range overconfidence |

### Reliability Data (10 Probability Bins per Class)

```

--- Class: NORM ---
Bin Range    | Count   | Mean Pred Prob   | Empirical Fraction
------------------------------------------------------------
[0.0, 0.1]   | 745     | 0.0180           | 0.0107            
[0.1, 0.2]   | 91      | 0.1475           | 0.0549            
[0.2, 0.3]   | 57      | 0.2462           | 0.2982            
[0.3, 0.4]   | 47      | 0.3506           | 0.1489            
[0.4, 0.5]   | 57      | 0.4523           | 0.2456            
[0.5, 0.6]   | 67      | 0.5468           | 0.3731            
[0.6, 0.7]   | 44      | 0.6483           | 0.4773            
[0.7, 0.8]   | 79      | 0.7504           | 0.4937            
[0.8, 0.9]   | 147     | 0.8511           | 0.6463            
[0.9, 1.0]   | 824     | 0.9801           | 0.8883            

--- Class: MI ---
Bin Range    | Count   | Mean Pred Prob   | Empirical Fraction
------------------------------------------------------------
[0.0, 0.1]   | 1227    | 0.0160           | 0.0334            
[0.1, 0.2]   | 141     | 0.1477           | 0.1489            
[0.2, 0.3]   | 88      | 0.2521           | 0.3068            
[0.3, 0.4]   | 60      | 0.3522           | 0.2833            
[0.4, 0.5]   | 60      | 0.4548           | 0.3667            
[0.5, 0.6]   | 53      | 0.5465           | 0.5472            
[0.6, 0.7]   | 58      | 0.6500           | 0.5172            
[0.7, 0.8]   | 72      | 0.7461           | 0.4861            
[0.8, 0.9]   | 100     | 0.8532           | 0.6500            
[0.9, 1.0]   | 299     | 0.9670           | 0.8796            

--- Class: STTC ---
Bin Range    | Count   | Mean Pred Prob   | Empirical Fraction
------------------------------------------------------------
[0.0, 0.1]   | 1158    | 0.0141           | 0.0242            
[0.1, 0.2]   | 132     | 0.1446           | 0.1136            
[0.2, 0.3]   | 74      | 0.2468           | 0.0946            
[0.3, 0.4]   | 66      | 0.3458           | 0.1212            
[0.4, 0.5]   | 47      | 0.4539           | 0.2553            
[0.5, 0.6]   | 68      | 0.5533           | 0.2353            
[0.6, 0.7]   | 59      | 0.6497           | 0.3051            
[0.7, 0.8]   | 87      | 0.7513           | 0.5287            
[0.8, 0.9]   | 121     | 0.8592           | 0.5950            
[0.9, 1.0]   | 346     | 0.9666           | 0.8642            

--- Class: CD ---
Bin Range    | Count   | Mean Pred Prob   | Empirical Fraction
------------------------------------------------------------
[0.0, 0.1]   | 1057    | 0.0327           | 0.0189            
[0.1, 0.2]   | 240     | 0.1442           | 0.1167            
[0.2, 0.3]   | 134     | 0.2492           | 0.1343            
[0.3, 0.4]   | 79      | 0.3473           | 0.1392            
[0.4, 0.5]   | 74      | 0.4457           | 0.2162            
[0.5, 0.6]   | 59      | 0.5429           | 0.2712            
[0.6, 0.7]   | 61      | 0.6533           | 0.3607            
[0.7, 0.8]   | 76      | 0.7587           | 0.5526            
[0.8, 0.9]   | 82      | 0.8553           | 0.6220            
[0.9, 1.0]   | 296     | 0.9722           | 0.9189            

--- Class: HYP ---
Bin Range    | Count   | Mean Pred Prob   | Empirical Fraction
------------------------------------------------------------
[0.0, 0.1]   | 1417    | 0.0139           | 0.0254            
[0.1, 0.2]   | 159     | 0.1439           | 0.0629            
[0.2, 0.3]   | 93      | 0.2472           | 0.0860            
[0.3, 0.4]   | 78      | 0.3437           | 0.1923            
[0.4, 0.5]   | 60      | 0.4481           | 0.2000            
[0.5, 0.6]   | 52      | 0.5469           | 0.1923            
[0.6, 0.7]   | 49      | 0.6513           | 0.2245            
[0.7, 0.8]   | 57      | 0.7493           | 0.5263            
[0.8, 0.9]   | 59      | 0.8545           | 0.4407            
[0.9, 1.0]   | 134     | 0.9633           | 0.7761            
```

---

## 5. Sanity Checks & Leakage Audits

1. **Patient Leakage**: Confirmed **0 overlapping patient IDs** between training (Folds 1–8), validation (Fold 9), and held-out test (Fold 10).
2. **Leakage Metric Audit**: No metric is artificially inflated (no AUROC = 1.0000 or 0.9999). Macro AUROC of **0.9265** is consistent with published PTB-XL deep learning benchmarks (Strodthoff et al., IEEE JBHI 2021 reported ~0.90–0.92 for ResNet models).
3. **Threshold Selection Audit**: Thresholds were optimized strictly on Fold 9 validation data and locked before any evaluation on Fold 10.
4. **Baseline Superiority**: Model outperforms trivial prevalence baselines and random guess baselines across all diagnostic superclasses.

---

## 6. Plain-Language Clinical Discussion & Honest Limitations

### Honest Assessment of Weaknesses
1. **Hypertrophy (`HYP`) Performance**:
   - `HYP` exhibits the lowest sensitivity (55.73%) and lowest F1 score (0.6083).
   - *Underlying Reason*: Hypertrophy diagnoses in ECG are based on subtle voltage amplitude criteria (e.g., Sokolow-Lyon or Cornell voltage) which exhibit high inter-patient anatomical variability (body mass index, chest wall thickness) and account for only 12.4% of the dataset.

2. **Myocardial Infarction (`MI`) False Negatives**:
   - The model missed **110** acute/subacute or old MI cases out of 550 true positive cases (False Negative Rate: 20.00%).
   - *Clinical Consequence*: In an emergency department triage scenario, a false negative for Myocardial Infarction can delay life-saving reperfusion therapy (primary PCI). Therefore, **this system must NEVER be used as a sole rule-out tool for acute coronary syndrome (ACS)**. Any patient presenting with chest pain, dyspnea, or anginal equivalents requires immediate emergency physician review regardless of model score.

3. **Conduction Disturbance (`CD`) & ST/T Changes (`STTC`)**:
   - Conduction disturbances (bundle branch blocks, AV blocks) and ST/T changes show strong AUROC (0.9259 and 0.9351), but moderate precision due to overlapping ischemic vs non-ischemic repolarization abnormalities.

### Inherent System Limitations
- **Sampling Rate**: Model operates on 100 Hz downsampled records. Subtle high-frequency features (such as epsilon waves or pacemaker spikes) may be smoothed.
- **Single-Lead vs Multi-Lead Discordance**: Severe limb lead artifacts or noise can lead to degraded predictions. The model expects clean 12-lead placement.
- **Prototype Status**: Designed strictly for research and paired assistive evaluation. Not certified under FDA 510(k), CE-MDR, or CDSCO.
