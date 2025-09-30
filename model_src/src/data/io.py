import os
from pathlib import Path
import numpy as np
import pandas as pd
import random
import re
from sklearn.preprocessing import StandardScaler

def split_samples_random(base_folder, train_ratio=0.8, val_ratio=0.1, seed=42):
    base = Path(base_folder)
    # Gather all sample IDs from subfolders
    sample_ids = sorted([
        int(d.name.split("_")[-1])
        for d in base.iterdir()
        if d.is_dir() and d.name.startswith("sample_")
    ])
    # Shuffle + split
    random.seed(seed)
    random.shuffle(sample_ids)
    n = len(sample_ids)
    n_train = int(train_ratio * n)
    n_val = int(val_ratio * n)
    train_ids = sample_ids[:n_train]
    val_ids   = sample_ids[n_train:n_train + n_val]
    test_ids  = sample_ids[n_train + n_val:]

    # Collect CSVs for each split (looks for *.csv inside each sample_<id> folder)
    def gather(ids):
        files = []
        for sid in ids:
            for csv in (base / f"sample_{sid:02d}").glob("*.csv"):
                files.append(csv)  # Path objects are fine for pandas
        return files

    return gather(train_ids), gather(val_ids), gather(test_ids)

def load_coefs(coef_csv_path):
    df = pd.read_csv(coef_csv_path).set_index('sample_id')
    # Drop columns constant across all rows
    non_constant_df = df.loc[:, (df != df.iloc[0]).any()]
    coef_names = list(non_constant_df.columns)
    coef_map = {
        int(sample_id): row.values.astype(float)
        for sample_id, row in non_constant_df.iterrows()
    }
    return coef_map, coef_names


def load_data(file_list, constants_csv="constants.csv"):
    # Read the map and the names
    coef_map, coef_names = load_coefs(constants_csv)
    pattern = re.compile(r"sample_(\d+)_stepwise\.csv$")

    X_list, y_list = [], []
    for f in file_list:
        f = Path(f)
        m = pattern.search(f.name)
        if not m:
            continue
        sid = int(m.group(1))
        if sid not in coef_map:
            continue

        df = pd.read_csv(f).drop(columns=['Time'], errors='ignore')
        df = df.select_dtypes(include=[np.number])

        if df.shape[0] != 366:
            continue

        X_list.append(df.values.astype(float))
        y_list.append(coef_map[sid])

    return np.stack(X_list, axis=0), np.stack(y_list, axis=0), coef_names

def standardize_features(X_train: np.ndarray, X_test: np.ndarray, X_val: np.ndarray):
    N_train, T, F = X_train.shape
    N_test  = X_test.shape[0]
    N_val   = X_val.shape[0]

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train.reshape(-1, F)).reshape(N_train, T, F)
    X_test_scaled  = scaler.transform(X_test.reshape(-1, F)).reshape(N_test, T, F)
    X_val_scaled   = scaler.transform(X_val.reshape(-1, F)).reshape(N_val,  T, F)

    return X_train_scaled, X_test_scaled, X_val_scaled, scaler