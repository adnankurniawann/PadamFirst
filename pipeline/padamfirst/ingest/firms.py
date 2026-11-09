"""Tarik titik api VIIRS dari NASA FIRMS ke tabel hotspots.

python -m padamfirst.ingest.firms --days 2
"""

import argparse
import io
import os
import warnings
from pathlib import Path

import geopandas
import h3
import httpx
import pandas as pd
import shapely
from sqlalchemy import Engine, text

from padamfirst.config import BBOX_INDONESIA, H3_RESOLUTION
from padamfirst.db import get_engine, upsert

SOURCES = ("VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT")
API_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{bbox}/{days}"
LAND_PATH = Path(__file__).parents[3] / "data/raw/admin/idn_admin_boundaries.gdb.zip"

CONFIDENCE = {"l": "low", "n": "nominal", "h": "high"}
REQUIRED_COLUMNS = {
    "latitude",
    "longitude",
    "acq_date",
    "acq_time",
    "satellite",
    "instrument",
    "confidence",
    "frp",
}
HOTSPOT_KEY = ("satellite", "lat", "lon", "acq_datetime")


def fetch_csv(source: str, days: int, key: str) -> str:
    bbox = ",".join(map(str, BBOX_INDONESIA))
    url = API_URL.format(key=key, source=source, bbox=bbox, days=days)
    response = httpx.get(url, timeout=120)
    if response.status_code != 200:
        # Pesan dibuat sendiri karena pesan bawaan httpx memuat URL, dan URL memuat MAP_KEY.
        raise RuntimeError(f"HTTP {response.status_code}: {response.text[:200]}")
    return response.text


def parse_csv(csv_text: str) -> pd.DataFrame:
    raw = pd.read_csv(io.StringIO(csv_text))

    missing = REQUIRED_COLUMNS - set(raw.columns)
    if missing:
        raise ValueError(f"CSV FIRMS tidak valid, kolom hilang: {sorted(missing)}")

    confidence = raw["confidence"].map(CONFIDENCE)
    if confidence.isna().any():
        unknown = raw.loc[confidence.isna(), "confidence"].unique().tolist()
        raise ValueError(f"Nilai confidence tidak dikenal: {unknown}")

    # acq_time berupa HHMM tanpa nol di depan (325 berarti 03:25) dan selalu UTC.
    acquired = raw["acq_date"] + " " + raw["acq_time"].astype(str).str.zfill(4)
    lat = raw["latitude"].astype(float)
    lon = raw["longitude"].astype(float)
    return pd.DataFrame(
        {
            "satellite": raw["satellite"],
            "instrument": raw["instrument"],
            "lat": lat,
            "lon": lon,
            "acq_datetime": pd.to_datetime(acquired, format="%Y-%m-%d %H%M", utc=True),
            "frp": raw["frp"].astype(float),
            "confidence": confidence,
            "h3_index": [
                h3.latlng_to_cell(y, x, H3_RESOLUTION) for y, x in zip(lat, lon, strict=True)
            ],
        }
    )


def load_land() -> shapely.MultiPolygon:
    # shortcut: file mentah ini tidak ada di GitHub Actions, perlu masker ringkas di Fase 13
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="organizePolygons")
        land = geopandas.read_file(LAND_PATH, layer="idn_admin0", columns=[]).geometry.iloc[0]
    shapely.prepare(land)
    return land


def keep_on_land(hotspots: pd.DataFrame, land: shapely.Geometry) -> pd.DataFrame:
    return hotspots[shapely.contains_xy(land, hotspots["lon"], hotspots["lat"])]


def _finish_run(engine: Engine, run_id: int, status: str, rows: int, error: str | None) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE ingest_runs SET finished_at = now(), status = :status, rows = :rows, "
                "error = :error WHERE id = :id"
            ),
            {"id": run_id, "status": status, "rows": rows, "error": error},
        )


def ingest_source(engine: Engine, source: str, days: int, key: str, land: shapely.Geometry) -> bool:
    """Ingest satu sumber dan catat ke ingest_runs. Gagal tidak membatalkan sumber lain."""
    with engine.begin() as conn:
        run_id = conn.execute(
            text(
                "INSERT INTO ingest_runs (source, started_at, status) "
                "VALUES (:source, now(), 'running') RETURNING id"
            ),
            {"source": source},
        ).scalar_one()

    try:
        hotspots = parse_csv(fetch_csv(source, days, key))
        on_land = keep_on_land(hotspots, land)
        # Kosongkan NaN: satu NaN di kolom double akan merusak hasil SUM di Postgres.
        rows = on_land.astype(object).where(on_land.notna(), None).to_dict("records")
        with engine.begin() as conn:
            upsert(conn, "hotspots", rows, HOTSPOT_KEY)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        if key:
            error = error.replace(key, "***")
        _finish_run(engine, run_id, "failed", 0, error)
        print(f"{source}: GAGAL, {error}")
        return False

    _finish_run(engine, run_id, "success", len(rows), None)
    print(f"{source}: {len(hotspots)} titik dari FIRMS, {len(rows)} di daratan Indonesia")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=2, choices=range(1, 6))
    args = parser.parse_args(argv)

    engine = get_engine()
    key = os.environ["FIRMS_MAP_KEY"]
    land = load_land()
    results = [ingest_source(engine, source, args.days, key, land) for source in SOURCES]
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
