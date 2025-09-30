#!/usr/bin/env python3
import os
import json
import argparse
import pandas as pd
import joblib
import torch
from torch.utils.data import TensorDataset, DataLoader
from pathlib import Path
import logging
import re

from src.utils.seed import set_seed
from src.data.io import (
    split_samples_random, load_coefs, load_data, standardize_features
)
from src.model.resnet1d import Conv1DRegressor
from src.train.train_loop import NoisyTensorDataset, train_model
from src.eval.infer import evaluate_model
from src.metrics.calibration import (
    fit_std_scales_from_val_csv, apply_std_scales_to_csv,
    compute_ence_from_csv, rmse_rmv_per_bin,
    plot_param_calibration, plot_rmse_rmv_panel, plot_true_vs_pred, write_post_recal_summary)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("run_model")


def _tag(dp: float) -> str:
    return f"dp{dp:.2f}".replace(".", "p")

def build_parser():
    p = argparse.ArgumentParser(description="Conv1D regression")

    default_base = "/scratch/bkmanu/NIH/spike-1.6.0rc2-linux64/Simulated_data/Sim_no_centering_new_funct"
    default_const = "/scratch/bkmanu/NIH/spike-1.6.0rc2-linux64/Simulated_data/Sim_no_centering_new_funct/constants.csv"

    # Data / splits
    p.add_argument("--base-folder",
                   default=str(default_base),
                   help="Folder with samples (defaulted in script)")
    p.add_argument("--constants",
                   default=str(default_const),
                   help="Path to constants.csv (defaulted in script)")
    p.add_argument("--splits-dir", default="splits")
    p.add_argument("--train-ratio", type=float, default=0.80)
    p.add_argument("--val-ratio",   type=float, default=0.10)

    # Model capacity
    p.add_argument("--nblocks",      type=int, default=3,   help="# residual Conv1D blocks")
    p.add_argument("--hidden_dim",   type=int, default=128, help="hidden channels")
    p.add_argument("--kernel_size",  type=int, default=5,   help="conv kernel size per block")
    p.add_argument("--out-dim",      type=int, default=12,  help="number of target outputs K")

    # Training
    p.add_argument("--epochs",      type=int,   default=50)
    p.add_argument("--batch-size",  type=int,   default=8)
    p.add_argument("--lr",          type=float, default=1e-4)
    p.add_argument("--cpu",         action="store_true")
    p.add_argument("--patience",   type=int,   default=10, help="epochs to wait for val improvement")
    p.add_argument("--min-delta",  type=float, default=0.0, help="minimum improvement in val loss")

    # MC dropout & eval
    p.add_argument("--dropouts",        type=float, nargs="+", default=[0.1, 0.2],
                   help="Run variants for these dropout rates")
    p.add_argument("--n-mc",            type=int,   default=50)
    # p.add_argument("--eval-batch-size", type=int,   default=256)

    # Metrics / calibration
    p.add_argument("--param",   type=str, default="0",
                   help="Target index for quick single-parameter plots")
    p.add_argument("--n-bins",  type=int,   default=10)
    p.add_argument("--sigma",   type=float, default=1.0)
    p.add_argument("--plot",    default="", help="(unused now; plots go to outdir/plots)")

    # Outputs
    p.add_argument("--outdir",  default="runs/expC1")

    # Repro
    p.add_argument("--seed", type=int, default=42)
    return p

def main():
    args = build_parser().parse_args()
    set_seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
    log.info("Starting run")
    log.info("Base folder: %s", args.base_folder)
    log.info("Constants:   %s", args.constants)
    log.info("Splits dir:  %s", args.splits_dir)
    log.info("Device:      %s", device)
    log.info("Epochs: %d | Batch: %d | Eval batch: %d | LR: %.2e",
            args.epochs, args.batch_size, args.batch_size, args.lr)
    log.info("Dropouts to run: %s", ", ".join(str(d) for d in args.dropouts))

    # Split once (reused for all dropout variants)
    os.makedirs(args.splits_dir, exist_ok=True)
    tr, va, te = split_samples_random(
        args.base_folder, args.train_ratio, args.val_ratio, args.seed
    )
    split_paths = {
        "train": os.path.join(args.splits_dir, "train.csv"),
        "val":   os.path.join(args.splits_dir, "val.csv"),
        "test":  os.path.join(args.splits_dir, "test.csv"),
    }
    pd.Series(tr).to_csv(split_paths["train"], index=False, header=False)
    pd.Series(va).to_csv(split_paths["val"],   index=False, header=False)
    pd.Series(te).to_csv(split_paths["test"],  index=False, header=False)

    train_files = pd.read_csv(split_paths["train"], header=None)[0].tolist()
    val_files   = pd.read_csv(split_paths["val"],   header=None)[0].tolist()
    test_files  = pd.read_csv(split_paths["test"],  header=None)[0].tolist()

    # coef names
    _, coef_names = load_coefs(args.constants)

    param_names = [
        'lambda1_MH', 'lambda2_MH', 'gamma1_HM', 'gamma2_HM',
        'delta1_MH', 'delta2_MH', 'eta1_HM', 'eta2_HM',
        'p1_mortality', 'p2_mortality', 'iota1', 'iota2'
    ]
    
    name_to_idx_all = {name: i for i, name in enumerate(coef_names)}
    targets = [t for t in param_names if t in name_to_idx_all]
    if not targets:
        raise ValueError("None of the requested param_names are present in constants.csv")
    target_idxs = [name_to_idx_all[t] for t in targets]
    K = len(targets)
    log.info("Training on %d targets: %s", K, ", ".join(targets))

    # Loop over dropout variants
    for dp in args.dropouts:
        tag      = _tag(dp)
        outdir   = f"{args.outdir}_{tag}"
        pred_dir = os.path.join("predictions", tag)
        plot_dir = os.path.join(outdir, "plots")

        log.info("─" * 72)
        log.info("Run %s | dropout=%.3f | outdir=%s | preds=%s", tag, dp, outdir, pred_dir)

        os.makedirs(outdir, exist_ok=True)
        os.makedirs(pred_dir, exist_ok=True)
        os.makedirs(plot_dir, exist_ok=True)

        # Load & standardize (X only)
        X_train, y_train, _ = load_data(train_files, constants_csv=args.constants)
        X_val,   y_val,   _ = load_data(val_files,   constants_csv=args.constants)
        X_test,  y_test,  _ = load_data(test_files,  constants_csv=args.constants)
        X_train_std, X_test_std, X_val_std, x_scaler = standardize_features(X_train, X_test, X_val)

        log.info(
            "%s data shapes | X_train: %s | y_train: %s | X_val: %s | y_val: %s",
            tag, tuple(X_train_std.shape), tuple(y_train.shape),
            tuple(X_val_std.shape), tuple(y_val.shape)
        )

        y_train = y_train[:, target_idxs]
        y_val   = y_val[:,   target_idxs]
        y_test  = y_test[:,  target_idxs]

        # Loaders
        train_ds = NoisyTensorDataset(
            torch.tensor(X_train_std).float(),
            torch.tensor(y_train).float(),
            noise_std=0.05
        )
        train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True)

        val_ds = TensorDataset(torch.tensor(X_val_std).float(),
                               torch.tensor(y_val).float())
        val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False)

        test_ds = TensorDataset(torch.tensor(X_test_std).float(),
                                torch.tensor(y_test).float())
        test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False)

        # Model
        device = torch.device("cuda" if torch.cuda.is_available() and not args.cpu else "cpu")
        model = Conv1DRegressor(
            input_dim=X_train.shape[2],
            num_filters=args.hidden_dim,
            kernel_size=args.kernel_size,
            num_blocks=args.nblocks,
            output_dim=K,
            dropout=dp,
        ).to(device)

        # Train
        best_ckpt = os.path.join(outdir, "best.pt")
        history = train_model(
            model, train_loader, val_loader,
            epochs=args.epochs, lr=args.lr,
            device=device, out_path=best_ckpt,
            epoch_tag=tag,
            patience=args.patience,
            min_delta=args.min_delta,
        )
        torch.save(model.state_dict(), os.path.join(outdir, "last.pt"))
        joblib.dump({"x": x_scaler}, os.path.join(outdir, "scalers.pkl"))

        # Save meta for reproducibility
        meta = {
            "seed": args.seed, "dropout": dp,
            "hidden_dim": args.hidden_dim, "nblocks": args.nblocks,
            "lr": args.lr, "coef_names": coef_names
        }
        with open(os.path.join(outdir, "history.json"), "w") as f:
            json.dump(history, f, indent=2)
        with open(os.path.join(outdir, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)

        # Eval helper
        def _eval_to_csv(files, out_csv):
            X, y, _ = load_data(files, constants_csv=args.constants)
            N, T, D = X.shape
            X_std = x_scaler.transform(X.reshape(-1, D)).reshape(N, T, D)
            y = y[:, target_idxs]

            m = Conv1DRegressor(
                input_dim=X.shape[2],
                num_filters=args.hidden_dim,
                kernel_size=args.kernel_size,
                num_blocks=args.nblocks,
                output_dim=K,
                dropout=dp,
            ).to(device)

            state = torch.load(best_ckpt, map_location=device)
            m.load_state_dict(state)

            ds = TensorDataset(torch.tensor(X_std).float(), torch.tensor(y).float())
            ld = DataLoader(ds, batch_size=args.batch_size, shuffle=False)

            # This call writes out_csv and the overview plots into plot_dir
            _ = evaluate_model(
                m, ld,
                n_mc_samples=args.n_mc,
                device=device,
                param_names=targets,
                out_csv=out_csv,
                plot_dir=plot_dir,
                sigma=args.sigma,
            )

        # Evaluate val & test
        val_raw_csv  = os.path.join(pred_dir, "val_raw.csv")
        test_raw_csv = os.path.join(pred_dir, "test_raw.csv")

        torch.manual_seed(args.seed)
        _eval_to_csv(val_files,  val_raw_csv)

        torch.manual_seed(args.seed)
        _eval_to_csv(test_files, test_raw_csv)

        # Recal + metrics
        scales = fit_std_scales_from_val_csv(val_raw_csv, per_param=True)
        test_cal_csv = os.path.join(pred_dir, "test_cal.csv")
        _ = apply_std_scales_to_csv(test_raw_csv, test_cal_csv, scales)
        # out_df.to_csv(test_cal_csv, index=False)

        post_summary_csv = os.path.join(pred_dir, "post_recal_summary.csv")
        post_df = write_post_recal_summary(test_cal_csv, post_summary_csv, sigma=args.sigma)

        # ---------- ENCE table (pre vs post) ----------
        ence_rows = []
        for name in targets:
            pre  = compute_ence_from_csv(test_raw_csv,  param=name, n_bins=args.n_bins)
            post = compute_ence_from_csv(test_cal_csv, param=name, n_bins=args.n_bins)
            ence_rows.append({
                "Parameter": name,
                "ENCE (Pre-recal)": pre,
                "ENCE (Post-recal)": post,
                "ΔENCE": post - pre
            })

        ence_path = os.path.join(pred_dir, "ence_table.csv")
        pd.DataFrame(ence_rows).to_csv(ence_path, index=False)
        log.info("%s saved ENCE table -> %s", tag, ence_path)

        # Per-parameter calibration + RMSE–RMV plots
        for name in targets:
            param_plot_dir = os.path.join(plot_dir, name)
            os.makedirs(param_plot_dir, exist_ok=True)
            plot_param_calibration(test_raw_csv, test_cal_csv, param=name, outdir=param_plot_dir)
            plot_rmse_rmv_panel(test_raw_csv, test_cal_csv, param=name, outdir=param_plot_dir)
            df_raw = pd.read_csv(test_raw_csv)
            true_vals = df_raw[f"true_{name}"].to_numpy()
            mean_vals = df_raw[f"pred_{name}"].to_numpy()
            std_vals  = df_raw[f"std_{name}"].to_numpy()
            plot_true_vs_pred(true_vals, mean_vals, std_vals, name, param_plot_dir)

        # Quick single-parameter ENCE (for the index passed with --param)
        param_name = targets[int(args.param)] if args.param.isdigit() else args.param
        ence = compute_ence_from_csv(test_cal_csv, param=param_name, n_bins=args.n_bins)

        log.info("%s best checkpoint: %s", tag, best_ckpt)
        log.info("%s wrote: %s", tag, val_raw_csv)
        log.info("%s wrote: %s", tag, test_raw_csv)
        log.info("%s calibration csv: %s", tag, test_cal_csv)
        log.info("%s ENCE (param=%s): %.6f", tag, args.param, ence)
        log.info("%s plots saved under: %s", tag, plot_dir)

if __name__ == "__main__":
    main()