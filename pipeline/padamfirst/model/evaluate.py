"""Metrik model dan baseline di data uji, PRD bagian 5.

python -m padamfirst.model.evaluate

Butuh models/lgbm-v1.txt dan models/lgbm-v1.json dari train.py. Metrik ditulis ulang ke
models/lgbm-v1.json.
"""

import argparse
import json

import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import average_precision_score, roc_auc_score

from padamfirst.config import BASELINE_SPREAD_WEIGHTS
from padamfirst.scoring import percentile_rank, weighted

TOP_K = 50
RELIABILITY_BINS = 10


def recall_at_k(rows: pd.DataFrame, scores, k: int = TOP_K) -> float:
    """Porsi label 1 yang masuk k sel teratas di harinya, dijumlah dari semua hari."""
    ranked = rows[["date", "label"]].assign(score=np.asarray(scores))
    top = ranked.sort_values("score", ascending=False).groupby("date").head(k)
    return float(top["label"].sum() / ranked["label"].sum())


def baseline_spread(rows: pd.DataFrame, reference: pd.DataFrame) -> np.ndarray:
    """P_spread baseline-v1 dari scoring.py, persentil terhadap data latih.

    Di scoring.py gambut dipersentilkan terhadap semua sel cell_static, di sini terhadap baris
    latih, karena yang dibandingkan cuma urutan antar sel.
    """
    columns = {"dc": "dc", "persistence_days": "persistence_days", "wind_speed": "wind_speed"}
    columns["peat"] = "peat_pct"
    pct = {
        name: percentile_rank(rows[col].fillna(0.0), reference[col].fillna(0.0))
        for name, col in columns.items()
    }
    return weighted(pct, BASELINE_SPREAD_WEIGHTS)


def metrics(rows: pd.DataFrame, scores) -> dict[str, float]:
    return {
        "pr_auc": float(average_precision_score(rows["label"], scores)),
        "roc_auc": float(roc_auc_score(rows["label"], scores)),
        f"recall_top{TOP_K}": recall_at_k(rows, scores),
    }


def reliability(labels, probs, bins: int = RELIABILITY_BINS) -> dict[str, list[float]]:
    """Rata-rata probabilitas dan frekuensi label 1 per kelompok probabilitas."""
    observed, predicted = calibration_curve(labels, probs, n_bins=bins, strategy="quantile")
    return {"predicted": predicted.tolist(), "observed": observed.tolist()}


def report(rows: pd.DataFrame, probs, reference: pd.DataFrame) -> dict:
    """Metrik model terkalibrasi dan baseline untuk rows, plus reliability model."""
    return {
        "rows": len(rows),
        "label_rate": float(rows["label"].mean()),
        "model": metrics(rows, probs),
        "baseline": metrics(rows, baseline_spread(rows, reference)),
        "reliability": reliability(rows["label"], probs),
    }


def main(argv: list[str] | None = None) -> int:
    from padamfirst.model import train

    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    meta = json.loads(train.META_PATH.read_text())
    booster = train.load_booster()
    splits = train.split(pd.read_parquet(train.DATASET_PATH))
    for name in ("validation", "test"):
        probs = train.predict(booster, meta["calibration"], splits[name])
        meta["metrics"][name] = report(splits[name], probs, splits["train"])
    train.META_PATH.write_text(json.dumps(meta, indent=2))
    train.print_metrics(meta["metrics"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
