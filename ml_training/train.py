"""
PTB-XL Residual 1D CNN Training Engine
=======================================
Supports:
- Tiny smoke test runs (fast GPU verification)
- Full production training with AdamW, Cosine Annealing, and Mixed Precision (AMP)
- Multi-label positive class weighting for class imbalance
- Automated checkpointing of best weights based on validation Macro AUC
"""
import os
import time
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from .config import (
    DIAGNOSTIC_SUPERCLASSES,
    BATCH_SIZE,
    LEARNING_RATE,
    WEIGHT_DECAY,
)
from .evaluate import evaluate_model, format_evaluation_report


def compute_positive_weights(targets: np.ndarray) -> torch.Tensor:
    """Compute pos_weight for BCEWithLogitsLoss: (total - pos) / pos."""
    pos_counts = np.sum(targets, axis=0)
    total_samples = len(targets)
    pos_weights = (total_samples - pos_counts) / np.maximum(pos_counts, 1.0)
    return torch.tensor(pos_weights, dtype=torch.float32)


def train_one_epoch(
    model: nn.Module,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    criterion: nn.Module,
    scaler: Optional[torch.amp.GradScaler],
    device: torch.device,
) -> float:
    """Train for one epoch."""
    model.train()
    total_loss = 0.0

    for signals, targets in loader:
        signals = signals.to(device)
        targets = targets.to(device)
        optimizer.zero_grad()

        if scaler is not None and device.type == "cuda":
            with torch.amp.autocast("cuda"):
                logits = model(signals)
                loss = criterion(logits, targets)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            logits = model(signals)
            loss = criterion(logits, targets)
            loss.backward()
            optimizer.step()

        total_loss += loss.item() * signals.size(0)

    return total_loss / max(len(loader.dataset), 1)


def run_training(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int = 2,
    lr: float = LEARNING_RATE,
    weight_decay: float = WEIGHT_DECAY,
    device: Optional[torch.device] = None,
    checkpoint_path: Optional[str] = None,
    pos_weights: Optional[torch.Tensor] = None,
) -> Dict[str, Any]:
    """
    Execute training loop.
    Returns dictionary with history and best metrics.
    """
    if device is None:
        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    model = model.to(device)

    # Set up criterion with positive class weighting
    if pos_weights is not None:
        pos_weights = pos_weights.to(device)
        criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weights)
    else:
        criterion = nn.BCEWithLogitsLoss()

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-5)
    scaler = torch.amp.GradScaler("cuda") if device.type == "cuda" else None

    history = {
        "epoch": [],
        "train_loss": [],
        "val_loss": [],
        "val_macro_auc": [],
        "val_macro_f1": [],
    }

    best_macro_auc = 0.0
    best_epoch = 0

    print(f"\n[Training Engine] Device: {device} | Epochs: {epochs} | Batch Size: {train_loader.batch_size}")
    print(f"                  Train Samples: {len(train_loader.dataset)} | Val Samples: {len(val_loader.dataset)}")

    for ep in range(1, epochs + 1):
        t0 = time.time()
        train_loss = train_one_epoch(model, train_loader, optimizer, criterion, scaler, device)
        scheduler.step()

        # Evaluate on validation split (Fold 9)
        val_res = evaluate_model(model, val_loader, criterion, device)
        elapsed = time.time() - t0

        history["epoch"].append(ep)
        history["train_loss"].append(train_loss)
        history["val_loss"].append(val_res["loss"])
        history["val_macro_auc"].append(val_res["macro_auc"])
        history["val_macro_f1"].append(val_res["macro_f1"])

        print(
            f"Epoch {ep:2d}/{epochs:2d} ({elapsed:4.1f}s) | "
            f"Train Loss: {train_loss:.4f} | "
            f"Val Loss: {val_res['loss']:.4f} | "
            f"Val AUC: {val_res['macro_auc']:.4f} | "
            f"Val F1: {val_res['macro_f1']:.4f}"
        )

        if val_res["macro_auc"] > best_macro_auc:
            best_macro_auc = val_res["macro_auc"]
            best_epoch = ep
            if checkpoint_path:
                torch.save(model.state_dict(), checkpoint_path)

    return {
        "best_epoch": best_epoch,
        "best_macro_auc": best_macro_auc,
        "history": history,
        "final_val_results": val_res,
    }
