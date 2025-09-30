import os
from typing import Dict
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import norm

try:
    import matplotlib.pyplot as plt
    _HAVE_MPL = True
except Exception:
    plt = None
    _HAVE_MPL = False

def plot_true_vs_pred(true_vals, mean_vals, std_vals, param_name, outdir: str):

    os.makedirs(outdir, exist_ok=True)

    plt.figure(figsize=(5, 5))
    plt.errorbar(mean_vals, true_vals, xerr=std_vals, fmt='o', alpha=0.6,
                 ecolor='gray', elinewidth=0.8, capsize=2)
    lims = [
        min(np.min(true_vals), np.min(mean_vals)),
        max(np.max(true_vals), np.max(mean_vals)),
    ]
    plt.plot(lims, lims, '--', color='red')
    plt.xlabel("Predicted mean")
    plt.ylabel("True value")
    plt.title(f"{param_name}: True vs Predicted")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()

    out_path = os.path.join(outdir, f"true_vs_pred_{param_name}.png")
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    return out_path

def fit_std_scales_from_val_csv(val_csv_path: str, per_param: bool = True):
    df = pd.read_csv(val_csv_path)
    pred_cols = [c for c in df.columns if c.startswith("pred_")]
    true_cols = [c for c in df.columns if c.startswith("true_")]
    std_cols  = [c for c in df.columns if c.startswith("std_")]
    if not (pred_cols and true_cols and std_cols):
        raise ValueError("CSV must include pred_*, true_*, std_*.")

    params = sorted(
        set(c.replace("pred_","") for c in pred_cols)
        .intersection(c.replace("true_","") for c in true_cols)
        .intersection(c.replace("std_","")  for c in std_cols)
    )

    if per_param:
        scales = {}
        for p in params:
            mu  = df[f"pred_{p}"].to_numpy()
            tru = df[f"true_{p}"].to_numpy()
            sd  = df[f"std_{p}"].to_numpy()
            num = np.mean((mu - tru) ** 2)
            den = np.mean(sd ** 2)
            alpha = np.sqrt(num / den)
            scales[p] = float(alpha)
        return scales
    else:
        err2_all = []
        var_all  = []
        for p in params:
            mu  = df[f"pred_{p}"].to_numpy()
            tru = df[f"true_{p}"].to_numpy()
            sd  = df[f"std_{p}"].to_numpy()
            err2_all.append((mu - tru) ** 2)
            var_all.append(sd ** 2)
        num = np.mean(np.concatenate(err2_all))
        den = np.mean(np.concatenate(var_all))
        alpha = np.sqrt(num / den)
        return float(alpha)

def apply_std_scales_to_csv(in_csv_path: str, out_csv_path: str, scales):
    df = pd.read_csv(in_csv_path).copy()
    if isinstance(scales, dict):
        for p, s in scales.items():
            col = f"std_{p}"
            if col in df.columns:
                df[col] = df[col] * float(s)
    else:
        for c in df.columns:
            if c.startswith("std_"):
                df[c] = df[c] * float(scales)
    df.to_csv(out_csv_path, index=False)
    return df

def _rank_quantile_bins(values, n_bins=10):
    order = np.argsort(values, kind="mergesort")
    return np.array_split(order, n_bins)

def compute_ence_from_csv(csv_path: str, param: str, n_bins: int = 10) -> float:
    df  = pd.read_csv(csv_path)
    mu  = df[f"pred_{param}"].to_numpy()
    sd  = df[f"std_{param}"].to_numpy()
    tru = df[f"true_{param}"].to_numpy()
    bins = _rank_quantile_bins(sd, n_bins=n_bins)
    terms = []
    for idx in bins:
        if len(idx) == 0: continue
        rmse = float(np.sqrt(np.mean((mu[idx] - tru[idx])**2)))
        rmv  = float(np.sqrt(np.mean(sd[idx]**2)))
        terms.append(abs(rmse - rmv) / (rmv + 1e-12))
    return float(np.mean(terms) if terms else 0.0)

def rmse_rmv_per_bin(df_or_csv, param: str, n_bins: int = 10) -> pd.DataFrame:
    df = pd.read_csv(df_or_csv) if isinstance(df_or_csv, (str, os.PathLike)) else df_or_csv
    mu  = df[f"pred_{param}"].to_numpy()
    sd  = df[f"std_{param}"].to_numpy()
    tru = df[f"true_{param}"].to_numpy()

    q = np.linspace(0, 1, n_bins+1)
    edges = np.quantile(sd, q)
    rows = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i+1]
        mask = (sd >= lo) & (sd <= hi if i == n_bins-1 else sd < hi)
        if not np.any(mask):
            rows.append({"Bin": i, "RMSE": np.nan, "RMV": np.nan, "Count": 0}); continue
        rmse = float(np.sqrt(np.mean((mu[mask] - tru[mask])**2)))
        rmv  = float(np.sqrt(np.mean(sd[mask]**2)))
        rows.append({"Bin": i, "RMSE": rmse, "RMV": rmv, "Count": int(mask.sum())})
    return pd.DataFrame(rows)

def calibration_curve_from_csv(csv_path: str, param: str, levels=(0.5, 0.68, 0.9, 0.95)):
    df = pd.read_csv(csv_path)
    mu  = df[f"pred_{param}"].to_numpy()
    tru = df[f"true_{param}"].to_numpy()
    sd  = df[f"std_{param}"].to_numpy()
    z_th = norm.ppf((1 + np.array(levels)) / 2.0)
    empirical = [(np.abs(mu - tru) <= z * sd).mean() for z in z_th]
    return np.array(levels), np.array(empirical)

def _ensure_dir(path: str):
    if path: os.makedirs(path, exist_ok=True)

def _savefig(fig, out_path: str):
    _ensure_dir(os.path.dirname(out_path))
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)

def plot_param_calibration(pre_csv: str, post_csv: str, param: str, outdir: str,
                           levels=(0.5,0.68,0.9,0.95)):
    if not _HAVE_MPL or not outdir:
        return

    lv, emp_pre  = calibration_curve_from_csv(pre_csv,  param, levels)
    _,  emp_post = calibration_curve_from_csv(post_csv, param, levels)

    plt.figure(figsize=(5,4))
    plt.plot(lv, lv, 'k--', label="Ideal")
    plt.plot(lv, emp_pre,  'o-', label="Pre recalibration",  color='red')
    plt.plot(lv, emp_post, 'o-', label="Post recalibration", color='blue')
    plt.xlabel("Nominal coverage"); plt.ylabel("Empirical coverage")
    plt.title(f"Calibration: {param}")
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(); plt.tight_layout()
    os.makedirs(outdir, exist_ok=True)
    plt.savefig(f"{outdir}/calibration_{param}.png", dpi=150)
    plt.close()

def plot_rmse_rmv_panel(pre_csv: str, post_csv: str, param: str,
                        outdir: str, n_bins: int = 10):
    if not _HAVE_MPL or not outdir:
        return

    pre_tbl  = rmse_rmv_per_bin(pre_csv,  param, n_bins=n_bins)
    post_tbl = rmse_rmv_per_bin(post_csv, param, n_bins=n_bins)

    vals = [pre_tbl["RMV"].max(), pre_tbl["RMSE"].max(),
            post_tbl["RMV"].max(), post_tbl["RMSE"].max()]
    lim = np.nanmax(vals)
    lim = 1.05 * (lim if np.isfinite(lim) and lim > 0 else 1e-6)
    xs = np.linspace(0, lim, 100)

    plt.figure(figsize=(5,4))
    plt.plot(xs, xs, 'k--', label="Ideal")
    plt.plot(pre_tbl["RMV"],  pre_tbl["RMSE"],  'o-', label="Pre recalibration",  color='red')
    plt.plot(post_tbl["RMV"], post_tbl["RMSE"], 'o-', label="Post recalibration", color='green')
    plt.xlabel("RMV"); plt.ylabel("RMSE")
    plt.title(param)
    plt.xlim(0, lim); plt.ylim(0, lim)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend(); plt.tight_layout()
    os.makedirs(outdir, exist_ok=True)
    plt.savefig(f"{outdir}/rmse_rmv_{param}.png", dpi=150, bbox_inches="tight")
    plt.close()

def summarize_post_recal_csv(csv_path: str | Path, sigma: float = 1.0) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    params = sorted(c.removeprefix("std_") for c in df.columns if c.startswith("std_"))

    cov_col = f"covered@{sigma:.1f}".rstrip("0").rstrip(".")
    have_cov = cov_col in df.columns

    rows = []
    for p in params:
        std_mean = float(df[f"std_{p}"].mean())
        if have_cov:
            cov = float(df[cov_col].mean())
        else:
            pred = df[f"pred_{p}"].to_numpy()
            true = df[f"true_{p}"].to_numpy()
            std  = df[f"std_{p}"].to_numpy()
            cov  = float(np.mean(np.abs(pred - true) <= sigma * std))
        rows.append({"Parameter": p,
                     "Avg_Std_Post": std_mean,
                     f"Coverage(@{sigma:.1f})_Post": cov})
    return pd.DataFrame(rows)


def write_post_recal_summary(csv_path: str | Path, out_path: str | Path, sigma: float = 1.0) -> pd.DataFrame:
    df = summarize_post_recal_csv(csv_path, sigma=sigma)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    return df