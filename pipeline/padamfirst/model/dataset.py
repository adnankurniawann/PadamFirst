"""Dataset latih per sel per hari api dengan label 48 jam, PRD bagian 5.

python -m padamfirst.model.dataset

Butuh data/processed/firms/<tahun>.parquet, data/processed/weather/<tahun>.parquet, dan
data/processed/cell_static.parquet. Tahun yang cuacanya belum lengkap dilewati. Hasil
data/processed/train.parquet.
"""

import argparse
from datetime import date, timedelta
from pathlib import Path

import h3
import pandas as pd

from padamfirst.features.build_daily import WEATHER_COLUMNS, fire_features, rain_features
from padamfirst.features.cells import aggregate_hotspots
from padamfirst.ingest.weather_archive import cell_points

ROOT = Path(__file__).parents[3]
PROCESSED = ROOT / "data/processed"
OUT_PATH = PROCESSED / "train.parquet"

LABEL_DAYS = 2
# Arsip diambil Juni sampai November, jadi hari ke-1 musim kemarau dihitung dari 1 Juni.
SEASON_START = (6, 1)
SEASON_END = (11, 30)

FIRE = ["n_hotspots", "frp_sum", "frp_max", "conf_mean"]
FIRE += ["persistence_days", "growth_24h", "neighbors_burning"]
WEATHER = [*WEATHER_COLUMNS.values(), "rain_7d", "rain_30d", "dry_days"]
LAND = ["peat_pct", "landcover_class", "dist_road_km", "dist_plantation_km"]
TIME = ["month", "season_day"]
FEATURES = [*FIRE, *WEATHER, *LAND, *TIME]


def label_48h(fires: pd.DataFrame) -> list[int]:
    """1 kalau dalam 2 hari berikutnya sel itu masih ada api atau tetangga ring 1 mulai terbakar.

    Tetangga yang sudah terbakar di hari t tidak dihitung, karena itu api tetangga sendiri yang
    bertahan, bukan api yang menyebar.
    """
    burning = set(zip(fires["h3_index"], fires["date"], strict=True))
    ahead = [timedelta(days=k) for k in range(1, LABEL_DAYS + 1)]

    def burns_soon(cell, day):
        return any((cell, day + step) in burning for step in ahead)

    return [
        int(
            burns_soon(cell, day)
            or any(
                (neighbor, day) not in burning and burns_soon(neighbor, day)
                for neighbor in h3.grid_ring(cell, 1)
            )
        )
        for cell, day in zip(fires["h3_index"], fires["date"], strict=True)
    ]


def year_dataset(
    hotspots: pd.DataFrame, weather: pd.DataFrame, static: pd.DataFrame, year: int
) -> pd.DataFrame:
    """Baris fitur dan label untuk tiap sel bertitik api di musim year.

    Hari terakhir musim yang 48 jam berikutnya di luar arsip dibuang, karena labelnya tidak
    diketahui.
    """
    fires = fire_features(aggregate_hotspots(hotspots))
    fires["label"] = label_48h(fires)
    start, end = date(year, *SEASON_START), date(year, *SEASON_END)
    fires = fires[(fires["date"] >= start) & (fires["date"] <= end - timedelta(LABEL_DAYS))]
    points = cell_points(fires["h3_index"].unique())[["h3_index", "point"]]
    fires = fires.merge(points, on="h3_index")

    daily = weather.assign(date=pd.to_datetime(weather["date"]).dt.date)
    daily = daily.rename(columns={"point": "h3_index"})
    daily = daily.merge(rain_features(daily), on=["h3_index", "date"])
    daily = daily.rename(columns={"h3_index": "point", **WEATHER_COLUMNS})
    rows = fires.merge(daily[["point", "date", *WEATHER]], on=["point", "date"], how="left")
    rows = rows.merge(static[["h3_index", *LAND]], on="h3_index", how="left")

    dates = pd.to_datetime(rows["date"])
    rows["month"] = dates.dt.month
    rows["season_day"] = (dates - pd.Timestamp(start)).dt.days + 1
    rows["year"] = year
    return rows[["h3_index", "date", "year", *FEATURES, "label"]].reset_index(drop=True)


def summary(dataset: pd.DataFrame) -> pd.DataFrame:
    """Jumlah baris, sel, dan proporsi label 1 per tahun."""
    return dataset.groupby("year").agg(
        rows=("label", "size"), cells=("h3_index", "nunique"), label_rate=("label", "mean")
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    static = pd.read_parquet(PROCESSED / "cell_static.parquet")
    frames, missing = [], []
    for path in sorted((PROCESSED / "firms").glob("*.parquet")):
        weather_path = PROCESSED / "weather" / path.name
        if not weather_path.exists():
            missing.append(path.stem)
            continue
        year = int(path.stem)
        weather = pd.read_parquet(weather_path)
        frames.append(year_dataset(pd.read_parquet(path), weather, static, year))
    if not frames:
        raise SystemExit("Belum ada tahun dengan cuaca lengkap, jalankan weather_archive dulu")

    dataset = pd.concat(frames, ignore_index=True)
    dataset.to_parquet(OUT_PATH, index=False)
    print(f"{len(dataset)} baris, {len(FEATURES)} fitur ke {OUT_PATH.relative_to(ROOT)}")
    print(summary(dataset).round(3).to_string())
    empty = dataset[FEATURES].isna().mean()
    print("Kolom dengan nilai kosong:", empty[empty > 0].round(4).to_dict())
    if missing:
        print("Cuaca belum lengkap, belum masuk:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
