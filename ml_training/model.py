"""
Residual 1D CNN Architecture for 12-Lead ECG Classification
===========================================================
Tailored for 12-lead ECG signals with shape (B, 12, 1000).
Features wide kernel stem convolution (size 15) to capture cardiac waveform morphologies
followed by 4 residual downsampling blocks and a multi-label classification head.
"""
import torch
import torch.nn as nn
from typing import Optional

from .config import NUM_CLASSES, NUM_LEADS


class ResidualBlock1D(nn.Module):
    """Basic 1D Residual Block with 2 Conv1d layers and skip connection."""

    def __init__(self, in_channels: int, out_channels: int, stride: int = 1, kernel_size: int = 7):
        super().__init__()
        padding = (kernel_size - 1) // 2

        self.conv1 = nn.Conv1d(in_channels, out_channels, kernel_size=kernel_size, stride=stride, padding=padding, bias=False)
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)

        self.conv2 = nn.Conv1d(out_channels, out_channels, kernel_size=kernel_size, stride=1, padding=padding, bias=False)
        self.bn2 = nn.BatchNorm1d(out_channels)

        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv1d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm1d(out_channels),
            )
        else:
            self.shortcut = nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.shortcut(x)
        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)
        out = self.conv2(out)
        out = self.bn2(out)
        out += residual
        out = self.relu(out)
        return out


class ResNet1D(nn.Module):
    """
    1D Residual Convolutional Neural Network for multi-label 12-lead ECG diagnosis.
    Input:  (B, 12, 1000)
    Output: (B, 5) raw logits
    """

    def __init__(self, in_channels: int = NUM_LEADS, num_classes: int = NUM_CLASSES, dropout_rate: float = 0.2):
        super().__init__()
        self.in_channels = in_channels
        self.num_classes = num_classes

        # Stem: Wide convolution to capture P-QRS-T complexes
        self.stem = nn.Sequential(
            nn.Conv1d(in_channels, 64, kernel_size=15, stride=2, padding=7, bias=False),
            nn.BatchNorm1d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=3, stride=2, padding=1),
        )

        # 4 Residual Stages: 64 -> 128 -> 256 -> 512
        self.stage1 = self._make_stage(64, 64, num_blocks=2, stride=1, kernel_size=7)
        self.stage2 = self._make_stage(64, 128, num_blocks=2, stride=2, kernel_size=7)
        self.stage3 = self._make_stage(128, 256, num_blocks=2, stride=2, kernel_size=7)
        self.stage4 = self._make_stage(256, 512, num_blocks=2, stride=2, kernel_size=7)

        # Head: Global Average Pooling + Classifier
        self.global_pool = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(p=dropout_rate)
        self.fc = nn.Linear(512, num_classes)

    def _make_stage(self, in_channels: int, out_channels: int, num_blocks: int, stride: int, kernel_size: int) -> nn.Sequential:
        layers = [ResidualBlock1D(in_channels, out_channels, stride=stride, kernel_size=kernel_size)]
        for _ in range(1, num_blocks):
            layers.append(ResidualBlock1D(out_channels, out_channels, stride=1, kernel_size=kernel_size))
        return nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.stem(x)
        out = self.stage1(out)
        out = self.stage2(out)
        out = self.stage3(out)
        out = self.stage4(out)
        out = self.global_pool(out)
        out = torch.flatten(out, 1)
        out = self.dropout(out)
        logits = self.fc(out)
        return logits


def get_model(in_channels: int = NUM_LEADS, num_classes: int = NUM_CLASSES) -> ResNet1D:
    """Instantiate and return the ResNet1D model."""
    return ResNet1D(in_channels=in_channels, num_classes=num_classes)
