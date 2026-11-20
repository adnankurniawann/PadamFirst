from datetime import date

import numpy as np
import pandas as pd
import pytest

from padamfirst.model.dataset import FEATURES
from padamfirst.model.evaluate import baseline_spread, recall_at_k, reliability, report
from padamfirst.model.train import calibrate, features, predict, split, tune


def rows(n, year=2019, seed=0):
    """Baris dataset sintetis: label ikut dc dan persistensi, supaya model bisa belajar."""
    rng = np.random.default_rng(seed)
    frame = pd.DataFrame({f: rng.random(n) for f in FEATURES})
    frame["landcover_class"] = rng.choice(["hutan", "pertanian", "gambut_semak"], n)
    frame["label"] = frame["dc"] + frame["persistence_days"] + 0.3 * rng.random(n) > 1.1
    frame["label"] = frame["label"].astype(int)
    frame["date"] = [date(year, 9, 1 + i % 5) for i in range(n)]
    frame["year"] = year
    return frame


def test_recall_at_k_counts_top_per_day():
    frame = pd.DataFrame(
        {"date": [1, 1, 1, 2, 2], "label": [1, 0, 1, 1, 0]},
    )
    # Hari 1: top-1 skor 0.9 label 1, label 1 lain terlewat. Hari 2: top-1 label 1.
    assert recall_at_k(frame, [0.9, 0.5, 0.1, 0.8, 0.2], k=1) == pytest.approx(2 / 3)


def test_baseline_spread_ranks_by_weighted_percentiles():
    reference = pd.DataFrame(
        {"dc": [1, 2, 3], "persistence_days": [1, 2, 3], "wind_speed": [1, 2, 3]}
    ).assign(peat_pct=[0.0, 0.5, 1.0])
    frame = pd.DataFrame(
        {"dc": [0, 9], "persistence_days": [0, 9], "wind_speed": [0, 9], "peat_pct": [None, 1.0]}
    )
    low, high = baseline_spread(frame, reference)
    assert low == 0.0
    # Semua komponen di atas data latih, peat 1.0 setara 2 dari 3 nilai acuan.
    assert high == pytest.approx(0.35 + 0.25 + 0.20 + 0.20 * 2 / 3)


def test_reliability_bins_follow_observed_rate():
    labels = [0, 0, 1, 1]
    curve = reliability(labels, [0.1, 0.2, 0.8, 0.9], bins=2)
    assert curve["predicted"] == pytest.approx([0.15, 0.85])
    assert curve["observed"] == [0.0, 1.0]


def test_split_by_year_and_rejects_missing_years():
    data = pd.concat([rows(3, 2015), rows(3, 2023), rows(3, 2025)])
    splits = split(data)
    assert {k: v["year"].unique().tolist() for k, v in splits.items()} == {
        "train": [2015],
        "validation": [2023],
        "test": [2025],
    }
    with pytest.raises(ValueError, match="validation, test"):
        split(rows(3, 2015))


def test_calibration_interpolates_isotonic_points():
    calibration = calibrate([0.1, 0.4, 0.6, 0.9], [0, 0, 1, 1])
    assert np.interp([0.0, 0.4, 0.6, 1.0], calibration["x"], calibration["y"]).tolist() == [
        0.0,
        0.0,
        1.0,
        1.0,
    ]


def test_tuned_model_beats_random_and_reports_both_scores():
    train, validation, test = rows(600, 2019, 0), rows(300, 2023, 1), rows(300, 2024, 2)
    params, booster = tune(train, validation, trials=2)
    assert "num_leaves" in params
    raw = booster.predict(features(validation), num_iteration=booster.best_iteration)
    calibration = calibrate(raw, validation["label"])
    probs = predict(booster, calibration, test)
    assert ((probs >= 0) & (probs <= 1)).all()

    result = report(test, probs, train)
    assert result["model"]["pr_auc"] > test["label"].mean() + 0.2
    assert set(result["baseline"]) == {"pr_auc", "roc_auc", "recall_top50"}
