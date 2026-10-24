"""
PTB-XL Evaluation Module
=========================
Computes official benchmark metrics:
- Macro & Micro AUC-ROC
- Macro & Micro F1 (threshold = 0.5)
- Sensitivity & Specificity
- Per-class Confusion Matrices (TP, FP, TN, FN)
"""
from typing import Dict, Any, List, Tuple
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from sklearn.metrics import roc_auc_score, f1_score, confusion_matrix

from .config import DIAGNOSTIC_SUPERCLASSES, NUM_CLASSES


def evaluate_model(
    model: nn.Module,
    loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """
    Run evaluation loop over a DataLoader.
    Returns dictionary with overall loss, AUCs, F1s, and per-class breakdown.
    """
    model.eval()
    total_loss = 0.0
    all_targets = []
    all_probs = []

    with torch.no_grad():
        for signals, targets in loader:
            signals = signals.to(device)
            targets = targets.to(device)

            logits = model(signals)
            loss = criterion(logits, targets)
            total_loss += loss.item() * signals.size(0)

            probs = torch.sigmoid(logits).cpu().numpy()
            all_probs.append(probs)
            all_targets.append(targets.cpu().numpy())

    all_targets = np.vstack(all_targets)
    all_probs = np.vstack(all_probs)
    total_samples = len(loader.dataset)
    avg_loss = total_loss / max(total_samples, 1)

    # 1. Per-Class and Macro AUC-ROC
    per_class_auc = {}
    auc_values = []
    for idx, cls_name in enumerate(DIAGNOSTIC_SUPERCLASSES):
        y_true = all_targets[:, idx]
        y_score = all_probs[:, idx]
        if len(np.unique(y_true)) > 1:
            try:
                auc = float(roc_auc_score(y_true, y_score))
            except Exception:
                auc = 0.5
        else:
            auc = 0.5
        per_class_auc[cls_name] = auc
        auc_values.append(auc)

    macro_auc = float(np.mean(auc_values))

    # Micro AUC (flattened across all labels)
    try:
        micro_auc = float(roc_auc_score(all_targets.ravel(), all_probs.ravel()))
    except Exception:
        micro_auc = macro_auc

    # 2. Binary predictions at threshold
    preds = (all_probs >= threshold).astype(np.float32)
    macro_f1 = float(f1_score(all_targets, preds, average="macro", zero_division=0))
    micro_f1 = float(f1_score(all_targets, preds, average="micro", zero_division=0))

    # 3. Per-class metrics
    per_class_metrics = {}
    for idx, cls_name in enumerate(DIAGNOSTIC_SUPERCLASSES):
        y_true = all_targets[:, idx].astype(int)
        y_pred = preds[:, idx].astype(int)

        tp = int(np.sum((y_true == 1) & (y_pred == 1)))
        fp = int(np.sum((y_true == 0) & (y_pred == 1)))
        tn = int(np.sum((y_true == 0) & (y_pred == 0)))
        fn = int(np.sum((y_true == 1) & (y_pred == 0)))

        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        f1 = (2 * tp) / (2 * tp + fp + fn) if (2 * tp + fp + fn) > 0 else 0.0

        per_class_metrics[cls_name] = {
            "auc": per_class_auc[cls_name],
            "sensitivity": sensitivity,
            "specificity": specificity,
            "f1": f1,
            "tp": tp,
            "fp": fp,
            "tn": tn,
            "fn": fn,
            "support": int(np.sum(y_true)),
        }

    return {
        "loss": avg_loss,
        "macro_auc": macro_auc,
        "micro_auc": micro_auc,
        "macro_f1": macro_f1,
        "micro_f1": micro_f1,
        "per_class": per_class_metrics,
        "total_samples": total_samples,
    }


def format_evaluation_report(results: Dict[str, Any], title: str = "EVALUATION REPORT") -> str:
    """Format evaluation results into a clean text table."""
    lines = [
        "=" * 75,
        f"  {title.upper()}",
        "=" * 75,
        f"Total Samples    : {results['total_samples']}",
        f"Loss             : {results['loss']:.4f}",
        f"Macro AUC-ROC    : {results['macro_auc']:.4f}",
        f"Micro AUC-ROC    : {results['micro_auc']:.4f}",
        f"Macro F1 (th=0.5): {results['macro_f1']:.4f}",
        f"Micro F1 (th=0.5): {results['micro_f1']:.4f}",
        "-" * 75,
        f"{'Class':<8} | {'AUC':<7} | {'Sens':<7} | {'Spec':<7} | {'F1':<7} | {'TP':<5} | {'FP':<5} | {'TN':<5} | {'FN':<5}",
        "-" * 75,
    ]
    for cls_name, m in results["per_class"].items():
        lines.append(
            f"{cls_name:<8} | {m['auc']:<7.4f} | {m['sensitivity']:<7.4f} | {m['specificity']:<7.4f} | {m['f1']:<7.4f} | {m['tp']:<5d} | {m['fp']:<5d} | {m['tn']:<5d} | {m['fn']:<5d}"
        )
    lines.append("=" * 75)
    return "\n".join(lines)
