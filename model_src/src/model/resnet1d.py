import torch
import torch.nn as nn
import torch.nn.functional as F


class ResidualBlock(nn.Module):
    def __init__(self, channels, kernel_size=5, dropout=0.2):
        super().__init__()
        padding = kernel_size // 2
        self.conv1 = nn.Conv1d(channels, channels, kernel_size, padding=padding)
        self.conv2 = nn.Conv1d(channels, channels, kernel_size, padding=padding)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x):
        residual = x
        out = self.conv1(x)
        out = F.relu(out)
        out = self.dropout(out)

        out = self.conv2(out)
        out = self.dropout(out)

        # skip connection
        out = out + residual
        return F.relu(out)

class Conv1DRegressor(nn.Module):
    def __init__(
        self,
        input_dim: int,
        num_filters: int = 128,
        kernel_size: int = 5,
        num_blocks: int = 3,
        output_dim: int = 12,
        dropout: float = 0.1,
    ):
        super().__init__()

        # Initial projection D_in -> num_filters
        self.input_proj = nn.Sequential(
            nn.Conv1d(input_dim, num_filters, kernel_size=1),
            nn.ReLU()
        )

        # Stacked residual blocks
        self.encoder = nn.Sequential(
            *[ResidualBlock(num_filters, kernel_size=kernel_size, dropout=dropout)
              for _ in range(num_blocks)]
        )

        # Global average pool to 1 time-step
        self.global_pool = nn.AdaptiveAvgPool1d(1)

        # Head
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(num_filters, output_dim)

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, (nn.Conv1d, nn.Linear)):
                nn.init.kaiming_normal_(m.weight, nonlinearity="relu")
                if m.bias is not None:
                    nn.init.zeros_(m.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Expect x as (B, T, D) -> (B, D, T)
        x = x.permute(0, 2, 1)

        # Project & encode
        x = self.input_proj(x)
        x = self.encoder(x)

        # Global pool -> (B, C, 1) -> (B, C)
        x = self.global_pool(x).squeeze(-1)
        x = F.relu(x)
        x = self.dropout(x)
        out = self.fc(x)
        out = torch.sigmoid(out)
        return out