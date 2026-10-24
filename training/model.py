"""
Residual 1D CNN Architecture for 12-Lead ECG Classification
-----------------------------------------------------------
Tailored for 12-lead ECG signals:
  Input shape: (batch_size, 12, 1000)
  Output: Logits for 5 diagnostic superclasses (NORM, MI, STTC, CD, HYP)

Designed for clean ONNX export without proprietary custom ops.
"""

import torch
import torch.nn as nn


class ConvBlock1D(nn.Module):
    """
    Basic Residual Block for 1D Signals.
    Conv1D -> BatchNorm1D -> ReLU -> Conv1D -> BatchNorm1D + Shortcut -> ReLU
    """
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 7, stride: int = 1):
        super().__init__()
        padding = kernel_size // 2
        self.conv1 = nn.Conv1d(
            in_channels, out_channels,
            kernel_size=kernel_size, stride=stride, padding=padding, bias=False
        )
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        self.conv2 = nn.Conv1d(
            out_channels, out_channels,
            kernel_size=kernel_size, stride=1, padding=padding, bias=False
        )
        self.bn2 = nn.BatchNorm1d(out_channels)

        if stride != 1 or in_channels != out_channels:
            self.shortcut = nn.Sequential(
                nn.Conv1d(in_channels, out_channels, kernel_size=1, stride=stride, bias=False),
                nn.BatchNorm1d(out_channels)
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
        out = out + residual
        out = self.relu(out)
        return out


class ResNet1D(nn.Module):
    """
    1D Residual CNN for 12-lead ECG signal classification.
    Input: (B, 12, L) -> Output: (B, num_classes)
    """
    def __init__(self, in_channels: int = 12, num_classes: int = 5, base_filters: int = 64):
        super().__init__()
        self.in_channels = in_channels
        self.num_classes = num_classes

        # Stem: Initial convolution with wide kernel (15) to capture broad ECG morphologies
        self.stem = nn.Sequential(
            nn.Conv1d(in_channels, base_filters, kernel_size=15, stride=2, padding=7, bias=False),
            nn.BatchNorm1d(base_filters),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=3, stride=2, padding=1)
        )

        # 4 Residual Stages: [2, 2, 2, 2] blocks (ResNet-18 1D)
        self.stage1 = nn.Sequential(
            ConvBlock1D(base_filters, base_filters, kernel_size=7, stride=1),
            ConvBlock1D(base_filters, base_filters, kernel_size=7, stride=1),
        )
        self.stage2 = nn.Sequential(
            ConvBlock1D(base_filters, base_filters * 2, kernel_size=7, stride=2),
            ConvBlock1D(base_filters * 2, base_filters * 2, kernel_size=7, stride=1),
        )
        self.stage3 = nn.Sequential(
            ConvBlock1D(base_filters * 2, base_filters * 4, kernel_size=7, stride=2),
            ConvBlock1D(base_filters * 4, base_filters * 4, kernel_size=7, stride=1),
        )
        self.stage4 = nn.Sequential(
            ConvBlock1D(base_filters * 4, base_filters * 8, kernel_size=7, stride=2),
            ConvBlock1D(base_filters * 8, base_filters * 8, kernel_size=7, stride=1),
        )

        # Classifier head
        self.global_pool = nn.AdaptiveAvgPool1d(1)
        self.dropout = nn.Dropout(p=0.3)
        self.fc = nn.Linear(base_filters * 8, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.stem(x)
        out = self.stage1(out)
        out = self.stage2(out)
        out = self.stage3(out)
        out = self.stage4(out)
        out = self.global_pool(out)      # Shape: (B, 512, 1)
        out = torch.flatten(out, 1)      # Shape: (B, 512)
        out = self.dropout(out)
        logits = self.fc(out)            # Shape: (B, num_classes)
        return logits
