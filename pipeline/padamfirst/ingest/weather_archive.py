"""Cuaca ERA5 dari Open-Meteo Archive untuk sel yang pernah aktif, per musim kebakaran.

python -m padamfirst.ingest.weather_archive              # semua tahun yang belum selesai
python -m padamfirst.ingest.weather_archive --year 2019

Butuh data/processed/firms/<tahun>.parquet dari firms_archive. Respons di-cache permanen di
data/cache/weather_archive/, jadi run yang terputus tinggal dijalankan lagi. Hasil per tahun di
data/processed/weather/<tahun>.parquet.
"""

import argparse
import math
import time
from datetime import timedelta
from pathlib import Path

import h3
import httpx
import pandas as pd

from padamfirst.features.cells import aggregate_hotspots
from padamfirst.ingest.weather import (
    ARCHIVE_URL,
    DAILY,
    NOON,
    SOIL,
    SPIN_UP_DAYS,
    add_fwi,
    fetch_json,
    parse_location,
)

ROOT = Path(__file__).parents[3]
FIRMS_DIR = ROOT / "data/processed/firms"
OUT_DIR = ROOT / "data/processed/weather"
CACHE_DIR = ROOT / "data/cache/weather_archive"

# Satu titik cuaca per kotak 0,5 derajat. Grid asli ERA5 0,25 derajat butuh sekitar 281 ribu
# call untuk 2015 sampai 2025, jauh di atas batas gratis 10.000 call per hari.
GRID_DEG = 0.5
# Batas per jam atau per hari habis, tunggu lalu coba lagi sampai berhasil.
LIMIT_WAIT_SECONDS = 600


def cell_points(cells) -> pd.DataFrame:
    """Kotak grid tiap sel, plus centroid sel untuk menghitung koordinat titik."""
    rows = []
    for cell in cells:
        lat, lon = h3.cell_to_latlng(cell)
        box = f"{round(lat / GRID_DEG) * GRID_DEG:.1f},{round(lon / GRID_DEG) * GRID_DEG:.1f}"
        rows.append((cell, box, lat, lon))
    return pd.DataFrame(rows, columns=["h3_index", "point", "lat", "lon"])


def season_points(fires: pd.DataFrame) -> pd.DataFrame:
    """Satu baris per titik cuaca: koordinat dan rentang tanggal yang perlu diambil.

    Koordinatnya rata-rata centroid sel aktif di kotak itu, bukan tengah kotak, supaya titik
    pantai tidak jatuh di laut. start mundur SPIN_UP_DAYS dari api pertama lalu dibulatkan ke
    awal bulan, supaya titik bisa dihitung FWI-nya bersama dalam beberapa kelompok saja.
    """
    span = fires.groupby("h3_index")["date"].agg(["min", "max"]).reset_index()
    cells = cell_points(span["h3_index"]).merge(span, on="h3_index")
    points = cells.groupby("point").agg(
        lat=("lat", "mean"), lon=("lon", "mean"), first=("min", "min"), end=("max", "max")
    )
    points["lat"] = points["lat"].round(4)
    points["lon"] = points["lon"].round(4)
    points["start"] = [
        (day - timedelta(days=SPIN_UP_DAYS)).replace(day=1) for day in points["first"]
    ]
    return points.drop(columns="first").reset_index()


def fetch_point(point: pd.Series, cache_dir: Path) -> list[dict]:
    params = {
        "latitude": str(point["lat"]),
        "longitude": str(point["lon"]),
        "start_date": point["start"].isoformat(),
        "end_date": point["end"].isoformat(),
        "daily": ",".join(DAILY),
        "hourly": ",".join([*NOON, SOIL]),
        "timezone": "auto",
    }
    while True:
        try:
            return fetch_json(ARCHIVE_URL, params, cache_dir)
        except (RuntimeError, httpx.TransportError) as exc:
            # fetch_json sudah retry untuk 429 dan 5xx, pesan "setelah" berarti retry-nya habis.
            if isinstance(exc, RuntimeError) and "setelah" not in str(exc):
                raise
            print(f"{type(exc).__name__}: {exc}, tunggu {LIMIT_WAIT_SECONDS} detik", flush=True)
            time.sleep(LIMIT_WAIT_SECONDS)


def season_weather(points: pd.DataFrame, cache_dir: Path = CACHE_DIR) -> pd.DataFrame:
    """Cuaca harian dan kode FWI per titik dari start sampai end titik itu."""
    frames = []
    for i, point in points.iterrows():
        (location,) = fetch_point(point, cache_dir)
        frames.append(parse_location(location).assign(point=point["point"]))
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(points)} titik", flush=True)
    weather = pd.concat(frames, ignore_index=True)
    lat = points.set_index("point")["lat"]
    groups = points.groupby("start")["point"]
    return pd.concat(
        [add_fwi(weather[weather["point"].isin(members)], lat) for _, members in groups],
        ignore_index=True,
    )


def weighted_calls(points: pd.DataFrame) -> int:
    """Perkiraan kuota Open-Meteo: tiap 14 hari per lokasi dihitung satu call."""
    days = [
        (end - start).days + 1 for start, end in zip(points["start"], points["end"], strict=True)
    ]
    return sum(math.ceil(d / 14) for d in days)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--year", type=int)
    args = parser.parse_args(argv)

    paths = sorted(FIRMS_DIR.glob("*.parquet"))
    if args.year:
        paths = [p for p in paths if p.stem == str(args.year)]
    if not paths:
        raise SystemExit(f"Tidak ada parquet di {FIRMS_DIR}, jalankan firms_archive dulu")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in paths:
        out = OUT_DIR / path.name
        if out.exists():
            print(f"{path.stem}: sudah ada, lewati")
            continue
        points = season_points(aggregate_hotspots(pd.read_parquet(path)))
        print(
            f"{path.stem}: {len(points)} titik, sekitar {weighted_calls(points)} call", flush=True
        )
        season_weather(points).to_parquet(out, index=False)
        print(f"{path.stem}: selesai", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
