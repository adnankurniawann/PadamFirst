"""Skor prioritas per sel aktif ke tabel predictions, rumus PRD bagian 5.

python -m padamfirst.scoring                    # tanggal cell_daily terbaru
python -m padamfirst.scoring --date 2026-11-11
"""

import argparse
import math
from datetime import date

import h3
import numpy as np
import pandas as pd
from sqlalchemy import text

from padamfirst.config import (
    BASELINE_MODEL_VERSION,
    BASELINE_SPREAD_WEIGHTS,
    CLASS_THRESHOLDS,
    FIRE_WEIGHTS,
    IMPACT_WEIGHTS,
    SCORE_WEIGHTS,
)
from padamfirst.db import get_engine, upsert

# Ring 4 sel resolusi 7 (jarak antar centroid sekitar 2,4 km) kira-kira radius 10 km.
EXPOSURE_RINGS = 4
# Sel dianggap searah angin kalau arahnya dari sel api paling jauh 45 derajat dari arah angin.
DOWNWIND_HALF_ANGLE = 45


def percentile_rank(values, reference) -> np.ndarray:
    """Porsi nilai historis yang lebih kecil dari tiap nilai, 0 sampai 1.

    Pakai "lebih kecil", bukan "lebih kecil atau sama", supaya nilai minimum (gambut 0 persen,
    api hari pertama) dapat 0 walaupun nilai itu paling banyak muncul.
    """
    reference = np.sort(np.asarray(reference, dtype=float))
    reference = reference[~np.isnan(reference)]
    if len(reference) == 0:
        return np.zeros(len(values))
    return np.searchsorted(reference, np.asarray(values, dtype=float), side="left") / len(reference)


def downwind_density(cell: str, wind_dir: float, density: pd.Series) -> float:
    """Rata-rata kepadatan penduduk sel searah angin dalam radius 10 km, termasuk sel itu sendiri.

    wind_dir arah datang angin (meteorologi), jadi asap bergerak ke wind_dir + 180.
    """
    lat0, lon0 = h3.cell_to_latlng(cell)
    downwind = (wind_dir + 180) % 360
    values = [density.get(cell, 0.0)]
    for other in h3.grid_disk(cell, EXPOSURE_RINGS):
        if other == cell:
            continue
        lat, lon = h3.cell_to_latlng(other)
        bearing = math.degrees(math.atan2((lon - lon0) * math.cos(math.radians(lat0)), lat - lat0))
        if abs((bearing - downwind + 180) % 360 - 180) <= DOWNWIND_HALF_ANGLE:
            # shortcut: sel di luar cell_static (lebih dari ring 2 dari api sejak 2015) dianggap
            # 0 jiwa, ganti ke WorldPop langsung kalau sel padat penduduk sering terlewat
            values.append(density.get(other, 0.0))
    return float(np.nanmean(values))


def priority_class(score: float) -> str:
    return next(name for name, low in CLASS_THRESHOLDS if score >= low)


def weighted(parts: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    return sum(weights[name] * parts[name] for name in weights)


def score_cells(cells: pd.DataFrame, history: pd.DataFrame, static: pd.DataFrame) -> pd.DataFrame:
    """Skor baseline untuk cells (cell_daily satu hari digabung cell_static).

    history adalah cell_daily semua tanggal, static adalah cell_static, keduanya jadi acuan
    persentil. Sel tanpa cell_static dianggap tanpa gambut dan tanpa penduduk.
    """
    density = static.set_index("h3_index")["pop_density"].fillna(0.0)
    exposure = [
        downwind_density(cell, wind, density)
        for cell, wind in zip(cells["h3_index"], cells["wind_dir"], strict=True)
    ]
    pct = {
        "dc": percentile_rank(cells["dc"], history["dc"]),
        "wind_speed": percentile_rank(cells["wind_speed"], history["wind_speed"]),
        "persistence_days": percentile_rank(cells["persistence_days"], history["persistence_days"]),
        "frp_sum": percentile_rank(cells["frp_sum"], history["frp_sum"]),
        "peat": percentile_rank(cells["peat_pct"].fillna(0.0), static["peat_pct"].fillna(0.0)),
        "exposure": percentile_rank(exposure, density),
    }
    p_spread = weighted(pct, BASELINE_SPREAD_WEIGHTS)
    impact = weighted(pct, IMPACT_WEIGHTS)
    fire = weighted(pct, FIRE_WEIGHTS)
    parts = {"p_spread": p_spread, "impact": impact, "fire": fire}
    score = np.round(100 * weighted(parts, SCORE_WEIGHTS), 1)
    return pd.DataFrame(
        {
            "h3_index": cells["h3_index"].to_numpy(),
            "date": cells["date"].to_numpy(),
            "model_version": BASELINE_MODEL_VERSION,
            "p_spread": p_spread,
            "impact_score": impact,
            "fire_score": fire,
            "priority_score": score,
            "priority_class": [priority_class(s) for s in score],
            # Baseline belum punya probabilitas terkalibrasi, jadi keyakinannya selalu rendah.
            "confidence_level": "rendah",
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--date", type=date.fromisoformat)
    args = parser.parse_args(argv)

    engine = get_engine()
    with engine.connect() as conn:
        day = args.date or conn.execute(text("SELECT max(date) FROM cell_daily")).scalar()
        history = pd.read_sql(text("SELECT * FROM cell_daily"), conn)
        static = pd.read_sql(text("SELECT h3_index, peat_pct, pop_density FROM cell_static"), conn)
    cells = history[history["date"] == day].merge(static, on="h3_index", how="left")
    if cells.empty:
        print(f"Tidak ada cell_daily di {day}, jalankan build_daily dulu")
        return 1

    result = score_cells(cells, history, static)
    with engine.begin() as conn:
        upsert(
            conn, "predictions", result.to_dict("records"), ["h3_index", "date", "model_version"]
        )

    print(f"{day}: {len(result)} sel diskor dengan {BASELINE_MODEL_VERSION}")
    print(result["priority_class"].value_counts().to_string())
    print(result[["p_spread", "impact_score", "fire_score", "priority_score"]].describe().round(2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
