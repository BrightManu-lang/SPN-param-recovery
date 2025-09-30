from typing import Optional
import os
import numpy as np
import pandas as pd
import torch
import matplotlib.pyplot as plt
from scipy import stats
from torch.utils.data import DataLoader

@torch.no_grad()
def evaluate_model(
    model,
    test_loader: DataLoader,
    n_mc_samples: int = 1,
    device: torch.device = torch.device("cpu"),
    param_names=None,        
    out_csv: str | None = None,
    plot_dir: str | None = None,
    sigma: float = 1.0,
):
    
    model = model.to(device)

    # Enable dropout only during MC sampling
    model.eval()
    means, stds, trues = [], [], []

    for xb, yb in test_loader:
        xb = xb.to(device, non_blocking=True)
        yb = yb.to(device, non_blocking=True)

        # MC sampling with dropout enabled during the sampling loop
        outs = []
        if n_mc_samples > 1:
            model.train()
            for _ in range(n_mc_samples):
                outs.append(model(xb).detach().cpu().numpy())
            model.eval()
        else:
            outs.append(model(xb).detach().cpu().numpy())

        mc = np.stack(outs, axis=0)              # (S, B, K)
        mean_pred = mc.mean(axis=0)              # (B, K)
        std_pred  = mc.std(axis=0, ddof=0) if n_mc_samples > 1 else np.zeros_like(mean_pred)

        means.append(mean_pred)
        stds.append(std_pred)
        trues.append(yb.detach().cpu().numpy())

    mu  = np.concatenate(means, axis=0)         # (N, K)
    sd  = np.concatenate(stds,  axis=0)         # (N, K)
    y   = np.concatenate(trues, axis=0)         # (N, K)
    N, K = mu.shape

    assert param_names is not None and len(param_names) == K, \
        f"`param_names` must be provided with length == output dim (got {len(param_names) if param_names else None} vs {K})"

    cols = {}
    for j, name in enumerate(param_names):
        cols[f"pred_{name}"] = mu[:, j]
        cols[f"std_{name}"]  = sd[:, j]
        cols[f"true_{name}"] = y[:, j]
    df = pd.DataFrame(cols)

    # Save predictions CSV
    if out_csv:
        os.makedirs(os.path.dirname(out_csv), exist_ok=True)
        df.to_csv(out_csv, index=False)

    # Per-parameter metrics
    rows = []
    for j, name in enumerate(param_names):
        rmse   = float(np.sqrt(np.mean((mu[:, j] - y[:, j]) ** 2)))
        avg_sd = float(sd[:, j].mean())
        cover  = float(np.mean(np.abs(mu[:, j] - y[:, j]) <= sigma * (sd[:, j] + 1e-12)))
        rows.append({
            "Parameter": name,
            "Mean_True": float(y[:, j].mean()),
            "Mean_Pred": float(mu[:, j].mean()),
            "Bias": float(mu[:, j].mean() - y[:, j].mean()),
            "MSE": float(np.mean((mu[:, j] - y[:, j]) ** 2)),
            "RMSE": rmse,
            f"Coverage(@{sigma}σ)": cover,
            "Avg Std": avg_sd,
            "N": int(N),
        })
    metrics_df = pd.DataFrame(rows)
    if out_csv:
        metrics_path = os.path.join(os.path.dirname(out_csv), "predictions_summary.csv")
        metrics_df.to_csv(metrics_path, index=False)

    # Overview plots (name-labeled)
    if plot_dir:
        os.makedirs(plot_dir, exist_ok=True)
        labels = list(param_names)
        x = np.arange(K, dtype=float)
        w = 0.35

        # Boxplot: true vs predicted per parameter
        data, positions = [], []
        for j in range(K):
            data.append(y[:, j]);  positions.append(j - w/2)
            data.append(mu[:, j]); positions.append(j + w/2)

        fig, ax = plt.subplots(figsize=(12, 4))
        bp = ax.boxplot(data, positions=positions, widths=w*0.9, notch=True,
                        patch_artist=True, labels=[''] * len(data), manage_ticks=False)
        # color even (true) vs odd (pred)
        for t, box in enumerate(bp['boxes']):
            box.set(facecolor=('#69b3ff' if t % 2 == 0 else '#ff7f7f'))
        ax.set_xticks(np.arange(K))
        ax.set_xticklabels(labels, rotation=30, ha="right")
        ax.set_ylabel("Parameter value")
        ax.legend([bp["boxes"][0], bp["boxes"][1]], ["True", "Predicted"])
        ax.set_title("True vs Predicted — distribution per parameter")
        fig.tight_layout()
        fig.savefig(os.path.join(plot_dir, "true_vs_pred_box.png"), dpi=200)
        plt.close(fig)

        # Bar chart: cross-sample means ± cross-sample std
        true_mean = y.mean(axis=0); true_std = y.std(axis=0)
        pred_mean = mu.mean(axis=0); pred_std = mu.std(axis=0)

        fig, ax = plt.subplots(figsize=(12, 4))
        ax.bar(x - w/2, true_mean, width=w, yerr=true_std, capsize=3, label="True")
        ax.bar(x + w/2, pred_mean, width=w, yerr=pred_std, capsize=3, label="Predicted")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right")
        ax.set_ylabel("Parameter Mean")
        ax.set_title("Parameter means ± cross-sample std")
        ax.legend()
        fig.tight_layout()
        fig.savefig(os.path.join(plot_dir, "bar_param_comp.png"), dpi=200)
        plt.close(fig)

    return df