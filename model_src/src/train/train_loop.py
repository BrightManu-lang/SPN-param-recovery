from typing import Optional, Dict, List
import numpy as np
import copy
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

class NoisyTensorDataset(Dataset):
    def __init__(self, X: torch.Tensor, y: torch.Tensor, noise_std: float = 0.05):
        X = X.cpu().numpy() if isinstance(X, torch.Tensor) else X
        y = y.cpu().numpy() if isinstance(y, torch.Tensor) else y
        self.X = X.astype("float32")
        self.y = y.astype("float32")
        self.s = float(noise_std)

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        x = self.X[idx].copy()
        if self.s > 0:
            x += np.random.normal(0, self.s, size=x.shape).astype("float32")
        return torch.from_numpy(x), torch.from_numpy(self.y[idx])

def train_model(
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: Optional[DataLoader],
    epochs: int = 50,
    lr: float = 1e-3,
    device: torch.device = torch.device("cpu"),
    out_path: Optional[str] = None,
    epoch_tag: str = "",
    patience: int = 10,
    min_delta: float = 0.0,
) -> Dict[str, List[float]]:
    model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    best_val = float("inf")
    best_state = None
    no_improve = 0

    history = {"train": [], "val": []}

    for epoch in range(1, epochs + 1):
        # --- train ---
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            xb, yb = xb.to(device), yb.to(device)
            pred = model(xb)
            loss = loss_fn(pred, yb)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            # train_loss += loss.item() * xb.size(0)
            train_loss += loss.item()
        # train_loss /= len(train_loader.dataset)
        train_loss /= len(train_loader)
        history["train"].append(train_loss)

        # --- validate ---
        val_loss = float("nan")
        if val_loader is not None:
            model.eval()
            total = 0.0
            with torch.no_grad():
                for xb, yb in val_loader:
                    xb, yb = xb.to(device), yb.to(device)
                    # total += loss_fn(model(xb), yb).item() * xb.size(0)
                    total += loss_fn(model(xb), yb).item()
            # val_loss = total / len(val_loader.dataset)
            val_loss = total / len(val_loader)
            history["val"].append(val_loss)

            improved = (val_loss + min_delta) < best_val
            if improved:
                best_val = val_loss
                no_improve = 0
                if out_path:
                    torch.save(model.state_dict(), out_path)
                best_state = copy.deepcopy(model.state_dict())
            else:
                no_improve += 1

        print(f"{epoch_tag} [{epoch:03d}/{epochs:03d}] "
              f"train={train_loss:.6f} val={val_loss:.6f}", flush=True)

        # Early stopping
        if val_loader is not None and patience > 0 and no_improve >= patience:
            print(f"{epoch_tag} Early stopping at epoch {epoch} "
                  f"(best_val={best_val:.6f})", flush=True)
            break

    if best_state is not None:
        model.load_state_dict(best_state)

    return history