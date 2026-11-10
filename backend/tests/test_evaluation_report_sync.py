import json
import re
from pathlib import Path

def test_evaluation_metrics_sync_with_evaluation_report():
    repo_root = Path(__file__).resolve().parent.parent.parent
    report_file = repo_root / "backend" / "models" / "EVALUATION_REPORT.md"
    metrics_file = repo_root / "src" / "data" / "evaluation_metrics.json"

    assert report_file.exists(), "EVALUATION_REPORT.md must exist"
    assert metrics_file.exists(), "src/data/evaluation_metrics.json must exist"

    with open(metrics_file, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    report_text = report_file.read_text(encoding="utf-8")

    # Check macro auroc in report
    macro_match = re.search(r"\*\*Macro AUROC\*\*\s*\|\s*\*\*([0-9.]+)\*\*", report_text)
    assert macro_match is not None
    assert float(macro_match.group(1)) == metrics["macro_auroc"]

    # Verify per-class AUROCs
    class_map = {c["code"]: c["auroc"] for c in metrics["classes"]}
    assert class_map["NORM"] == 0.9447
    assert class_map["MI"] == 0.9244
    assert class_map["STTC"] == 0.9351
    assert class_map["CD"] == 0.9259
    assert class_map["HYP"] == 0.9021
