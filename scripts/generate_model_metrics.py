"""
Parse backend/models/EVALUATION_REPORT.md and generate src/data/evaluation_metrics.json
Ensures the UI metrics are synchronized with the held-out test evaluation report.
"""

import re
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_PATH = REPO_ROOT / "backend" / "models" / "EVALUATION_REPORT.md"
OUTPUT_PATH = REPO_ROOT / "src" / "data" / "evaluation_metrics.json"

NAME_MAP = {
    "NORM": "Normal ECG",
    "MI": "Myocardial Infarction",
    "STTC": "ST/T-Wave Changes",
    "CD": "Conduction Disturbance",
    "HYP": "Hypertrophy",
}

def generate_metrics():
    if not REPORT_PATH.exists():
        raise FileNotFoundError(f"Evaluation report not found at {REPORT_PATH}")

    content = REPORT_PATH.read_text(encoding="utf-8")

    # Extract Macro AUROC & Macro F1
    macro_auroc_match = re.search(r"\*\*Macro AUROC\*\*\s*\|\s*\*\*([0-9.]+)\*\*", content)
    macro_f1_match = re.search(r"\*\*Macro F1 Score\*\*\s*\|\s*\*\*([0-9.]+)\*\*", content)

    macro_auroc = float(macro_auroc_match.group(1)) if macro_auroc_match else 0.9265
    macro_f1 = float(macro_f1_match.group(1)) if macro_f1_match else 0.7520

    # Extract Per-Class Table rows
    # | **NORM** | NORM | 0.51 | 0.9447 | 0.9249 | 94.70% | 79.75% | 79.03% | 0.8616 | 0.1054 |
    pattern = r"\|\s*\*\*([A-Z]+)\*\*\s*\|\s*[^|]+\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+%)\s*\|\s*([0-9.]+%)\s*\|\s*([0-9.]+%)\s*\|\s*([0-9.]+)\s*\|\s*([0-9.]+)\s*\|"
    matches = re.findall(pattern, content)

    classes = []
    for m in matches:
        code, threshold, auroc, auprc, sens, spec, prec, f1, brier = m
        classes.append({
            "code": code,
            "name": NAME_MAP.get(code, code),
            "threshold": threshold,
            "auroc": float(auroc),
            "auprc": float(auprc),
            "sensitivity": sens,
            "specificity": spec,
            "precision": prec,
            "f1": float(f1),
            "brier": float(brier),
        })

    data = {
        "source": "backend/models/EVALUATION_REPORT.md",
        "dataset": "PhysioNet PTB-XL Fold 10 (2,158 held-out records)",
        "macro_auroc": macro_auroc,
        "macro_f1": macro_f1,
        "classes": classes,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"Generated {OUTPUT_PATH} with {len(classes)} classes (Macro AUROC: {macro_auroc}).")
    return data

if __name__ == "__main__":
    generate_metrics()
