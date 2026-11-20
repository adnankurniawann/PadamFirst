"""Latih LightGBM p_spread dengan split waktu PRD bagian 5, tuning Optuna, kalibrasi isotonic.

python -m padamfirst.model.train              # 50 trial
python -m padamfirst.model.train --trials 10

Butuh data/processed/train.parquet dari model.dataset. Hasil models/lgbm-v1.txt (booster) dan
models/lgbm-v1.json (parameter, titik kalibrasi, metrik validasi dan uji).
"""

import argparse
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import average_precision_score

from padamfirst.model.dataset import FEATURES
from padamfirst.model.dataset import OUT_PATH as DATASET_PATH
from padamfirst.model.evaluate import report

ROOT = Path(__file__).parents[3]
MODEL_VERSION = "lgbm-v1"
MODEL_PATH = ROOT / f"models/{MODEL_VERSION}.txt"
META_PATH = ROOT / f"models/{MODEL_VERSION}.json"

TRAIN_END, VALIDATION_YEAR = 2022, 2023
MAX_ROUNDS = 2000
EARLY_STOP = 100
SEED = 42
BASE_PARAMS = {
    "objective": "binary",
    "metric": "average_precision",
    # Class weight: bobot label 1 dinaikkan sesuai rasio label 0 per label 1.
    "is_unbalance": True,
    "verbosity": -1,
    "seed": SEED,
    "deterministic": True,
}


def split(dataset: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Latih 2015 sampai 2022, validasi 2023, uji 2024 ke atas."""
    year = dataset["year"]
    splits = {
        "train": dataset[year <= TRAIN_END],
        "validation": dataset[year == VALIDATION_YEAR],
        "test": dataset[year > VALIDATION_YEAR],
    }
    empty = [name for name, rows in splits.items() if rows.empty]
    if empty:
        raise ValueError(f"Split kosong: {', '.join(empty)}, cek tahun di train.parquet")
    return {name: rows.reset_index(drop=True) for name, rows in splits.items()}


def features(rows: pd.DataFrame) -> pd.DataFrame:
    # LightGBM menyimpan daftar kategori latih di model dan memetakan ulang saat prediksi.
    return rows[FEATURES].astype({"landcover_class": "category"})


def suggest_params(trial: optuna.Trial) -> dict:
    return {
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 15, 255, log=True),
        "min_child_samples": trial.suggest_int("min_child_samples", 20, 500, log=True),
        "feature_fraction": trial.suggest_float("feature_fraction", 0.5, 1.0),
        "bagging_fraction": trial.suggest_float("bagging_fraction", 0.5, 1.0),
        "bagging_freq": 1,
        "lambda_l2": trial.suggest_float("lambda_l2", 1e-3, 10.0, log=True),
    }


def fit(params: dict, train: pd.DataFrame, validation: pd.DataFrame) -> lgb.Booster:
    """Booster dengan early stopping pada PR-AUC validasi."""
    train_set = lgb.Dataset(features(train), train["label"])
    valid_set = lgb.Dataset(features(validation), validation["label"], reference=train_set)
    return lgb.train(
        {**BASE_PARAMS, **params},
        train_set,
        num_boost_round=MAX_ROUNDS,
        valid_sets=[valid_set],
        callbacks=[lgb.early_stopping(EARLY_STOP, verbose=False)],
    )


def tune(train: pd.DataFrame, validation: pd.DataFrame, trials: int) -> tuple[dict, lgb.Booster]:
    """Parameter dan booster trial dengan PR-AUC validasi tertinggi."""
    boosters = {}

    def objective(trial):
        booster = fit(suggest_params(trial), train, validation)
        boosters[trial.number] = booster
        raw = booster.predict(features(validation), num_iteration=booster.best_iteration)
        return average_precision_score(validation["label"], raw)

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=SEED))
    study.optimize(objective, n_trials=trials)
    return study.best_trial.params, boosters[study.best_trial.number]


def calibrate(raw_validation, labels) -> dict[str, list[float]]:
    """Titik isotonic regression, disimpan sebagai daftar supaya tidak perlu pickle."""
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    iso.fit(raw_validation, labels)
    return {"x": iso.X_thresholds_.tolist(), "y": iso.y_thresholds_.tolist()}


def predict(booster: lgb.Booster, calibration: dict, rows: pd.DataFrame) -> np.ndarray:
    """Probabilitas terkalibrasi; np.interp sama dengan IsotonicRegression clip."""
    raw = booster.predict(features(rows), num_iteration=booster.best_iteration or None)
    return np.interp(raw, calibration["x"], calibration["y"])


def load_booster() -> lgb.Booster:
    return lgb.Booster(model_file=str(MODEL_PATH))


def print_metrics(results: dict) -> None:
    for name, result in results.items():
        table = pd.DataFrame({k: result[k] for k in ("model", "baseline")}).round(4)
        print(f"{name}: {result['rows']} baris, label 1 {result['label_rate']:.3f}")
        print(table.to_string())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--trials", type=int, default=50, choices=range(1, 51), metavar="1-50")
    args = parser.parse_args(argv)

    splits = split(pd.read_parquet(DATASET_PATH))
    train, validation = splits["train"], splits["validation"]
    params, booster = tune(train, validation, args.trials)
    raw = booster.predict(features(validation), num_iteration=booster.best_iteration)
    calibration = calibrate(raw, validation["label"])

    results = {
        name: report(splits[name], predict(booster, calibration, splits[name]), train)
        for name in ("validation", "test")
    }
    MODEL_PATH.parent.mkdir(exist_ok=True)
    booster.save_model(str(MODEL_PATH), num_iteration=booster.best_iteration)
    meta = {
        "model_version": MODEL_VERSION,
        "features": FEATURES,
        "params": params,
        "best_iteration": booster.best_iteration,
        "trials": args.trials,
        "years": {name: sorted(rows["year"].unique().tolist()) for name, rows in splits.items()},
        "calibration": calibration,
        "metrics": results,
    }
    META_PATH.write_text(json.dumps(meta, indent=2))
    print_metrics(results)
    print(f"Model ke {MODEL_PATH.relative_to(ROOT)}, metrik ke {META_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
