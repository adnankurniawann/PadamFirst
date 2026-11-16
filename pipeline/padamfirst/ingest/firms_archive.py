"""Arsip FIRMS VIIRS per negara jadi parquet musim kebakaran per tahun.

python -m padamfirst.ingest.firms_archive

Sumber data/raw/firms_archive/viirs-snpp_<tahun>_Indonesia.csv, hasil
data/processed/firms/<tahun>.parquet berisi Juni sampai November saja.
"""

import argparse
from pathlib import Path

import pandas as pd

from padamfirst.ingest.firms import parse_frame

ROOT = Path(__file__).parents[3]
ARCHIVE_DIR = ROOT / "data/raw/firms_archive"
OUT_DIR = ROOT / "data/processed/firms"
SEASON_MONTHS = range(6, 12)
# Kolom type arsip: 0 api vegetasi, 1 gunung api, 2 sumber panas tetap (pabrik, flare), 3 laut.
VEGETATION_FIRE = 0


def season_hotspots(raw: pd.DataFrame) -> pd.DataFrame:
    """Titik api vegetasi Juni sampai November (tanggal UTC) dari CSV arsip."""
    month = pd.to_datetime(raw["acq_date"]).dt.month
    keep = month.isin(SEASON_MONTHS) & (raw["type"] == VEGETATION_FIRE)
    return parse_frame(raw[keep].reset_index(drop=True))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)

    paths = sorted(ARCHIVE_DIR.glob("viirs-snpp_*_Indonesia.csv"))
    if not paths:
        raise SystemExit(f"Tidak ada arsip di {ARCHIVE_DIR}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in paths:
        year = path.stem.split("_")[1]
        hotspots = season_hotspots(pd.read_csv(path))
        hotspots.to_parquet(OUT_DIR / f"{year}.parquet", index=False)
        print(f"{year}: {len(hotspots)} titik, {hotspots['h3_index'].nunique()} sel")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
