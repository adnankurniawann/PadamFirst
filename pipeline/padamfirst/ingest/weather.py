"""Ambil cuaca harian Open-Meteo untuk sel aktif lalu hitung kode FWI.

python -m padamfirst.ingest.weather                                  # sel aktif dari tabel hotspots
python -m padamfirst.ingest.weather --date 2019-09-30 --lat 0.5 --lon 101.4   # satu titik
"""

import argparse
import hashlib
import json
import time
from datetime import date, timedelta
from pathlib import Path

import h3
import httpx
import pandas as pd
from sqlalchemy import text

from padamfirst.config import H3_RESOLUTION
from padamfirst.db import get_engine
from padamfirst.features.fwi import fwi_series

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
CACHE_DIR = Path(__file__).parents[3] / "data/cache/weather"

BATCH_SIZE = 100
SPIN_UP_DAYS = 60
# ERA5 di API arsip tertinggal sekitar 5 hari, data yang lebih baru diambil dari API prakiraan.
ARCHIVE_LAG_DAYS = 7
# Satu titik cuaca per sel H3 resolusi 5 (sekitar 15 km antar centroid), dipakai bersama sel
# resolusi 7 di dalamnya. Model cuaca Open-Meteo sendiri 9 sampai 28 km, dan per centroid sel
# resolusi 7 akan melewati batas gratis 10.000 call per hari saat musim kebakaran.
WEATHER_RESOLUTION = 5
RETRIES = 4

DAILY = {
    "temperature_2m_max": "temp_max",
    "relative_humidity_2m_min": "rh_min",
    "precipitation_sum": "rain",
    "wind_speed_10m_mean": "wind_speed",
    "wind_direction_10m_dominant": "wind_dir",
}
# FWI memakai cuaca jam 12 waktu setempat sesuai standar CFFWIS.
NOON = {
    "temperature_2m": "temp_noon",
    "relative_humidity_2m": "rh_noon",
    "wind_speed_10m": "wind_noon",
}
SOIL = "soil_moisture_0_to_7cm"


def weather_points(cells) -> pd.DataFrame:
    rows = []
    for cell in cells:
        point = h3.cell_to_parent(cell, WEATHER_RESOLUTION)
        lat, lon = h3.cell_to_latlng(point)
        rows.append((cell, point, round(lat, 4), round(lon, 4)))
    return pd.DataFrame(rows, columns=["h3_index", "point", "lat", "lon"])


def endpoint(end: date, today: date) -> str:
    return ARCHIVE_URL if end <= today - timedelta(days=ARCHIVE_LAG_DAYS) else FORECAST_URL


def fetch_json(url: str, params: dict, cache_dir: Path) -> list[dict]:
    """GET dengan retry. Respons di-cache per hari, run ulang di hari sama tidak ke API lagi."""
    key = hashlib.sha1(json.dumps([url, params], sort_keys=True).encode()).hexdigest()
    path = cache_dir / date.today().isoformat() / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text())

    for attempt in range(RETRIES):
        try:
            response = httpx.get(url, params=params, timeout=120)
        except httpx.TransportError:
            if attempt == RETRIES - 1:
                raise
        else:
            if response.status_code == 200:
                break
            if response.status_code != 429 and response.status_code < 500:
                raise RuntimeError(f"Open-Meteo HTTP {response.status_code}: {response.text[:200]}")
            if attempt == RETRIES - 1:
                raise RuntimeError(f"Open-Meteo HTTP {response.status_code} setelah {RETRIES} kali")
        time.sleep(2**attempt * 5)

    body = response.json()
    # Satu koordinat dibalas objek, banyak koordinat dibalas list.
    locations = body if isinstance(body, list) else [body]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(locations))
    return locations


def parse_location(location: dict) -> pd.DataFrame:
    daily = pd.DataFrame(location["daily"]).rename(columns={"time": "date", **DAILY})
    hourly = pd.DataFrame(location["hourly"])
    hourly["date"] = hourly["time"].str[:10]
    noon = hourly[hourly["time"].str.endswith("T12:00")].rename(columns=NOON)
    soil = hourly.groupby("date")[SOIL].mean().rename("soil_moisture")

    frame = daily.merge(noon[["date", *NOON.values()]], on="date").merge(soil, on="date")
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    return frame


def fetch_weather(points: pd.DataFrame, start: date, end: date, cache_dir: Path) -> pd.DataFrame:
    """Cuaca harian per titik dari start sampai end, maksimal BATCH_SIZE koordinat per request."""
    unique = points.drop_duplicates("point").reset_index(drop=True)
    url = endpoint(end, date.today())
    frames = []
    for offset in range(0, len(unique), BATCH_SIZE):
        batch = unique.iloc[offset : offset + BATCH_SIZE]
        params = {
            "latitude": ",".join(map(str, batch["lat"])),
            "longitude": ",".join(map(str, batch["lon"])),
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "daily": ",".join(DAILY),
            "hourly": ",".join([*NOON, SOIL]),
            "timezone": "auto",
        }
        locations = fetch_json(url, params, cache_dir)
        if len(locations) != len(batch):
            raise RuntimeError(f"Open-Meteo membalas {len(locations)} lokasi untuk {len(batch)}")
        for point, location in zip(batch["point"], locations, strict=True):
            frames.append(parse_location(location).assign(point=point))
    return pd.concat(frames, ignore_index=True)


def weather_with_fwi(cells, day: date, cache_dir: Path = CACHE_DIR) -> pd.DataFrame:
    """Cuaca dan FWI per sel untuk day dan SPIN_UP_DAYS hari sebelumnya.

    Rantai FWI mulai dari nilai awal di hari pertama, jadi hanya baris day yang sudah stabil.
    """
    points = weather_points(cells)
    weather = fetch_weather(points, day - timedelta(days=SPIN_UP_DAYS), day, cache_dir)
    lat = points.drop_duplicates("point").set_index("point")["lat"]
    inputs = pd.DataFrame(
        {
            "h3_index": weather["point"],
            "date": weather["date"],
            "lat": weather["point"].map(lat),
            "temp": weather["temp_noon"],
            "rh": weather["rh_noon"],
            "wind": weather["wind_noon"],
            # shortcut: hujan per hari kalender, standar CFFWIS memakai 24 jam sampai jam 12
            "rain": weather["rain"],
        }
    )
    codes = fwi_series(inputs).rename(columns={"h3_index": "point"})
    per_point = weather.merge(codes, on=["point", "date"])
    return points[["h3_index", "point"]].merge(per_point, on="point").drop(columns="point")


def active_cells(day: date) -> list[str]:
    """Sel yang punya titik api di day atau sehari sebelumnya (tanggal UTC)."""
    with get_engine().connect() as conn:
        return list(
            conn.execute(
                text(
                    "SELECT DISTINCT h3_index FROM hotspots "
                    "WHERE acq_datetime >= :start AND acq_datetime < :end"
                ),
                {"start": day - timedelta(days=1), "end": day + timedelta(days=1)},
            ).scalars()
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    args = parser.parse_args(argv)

    if (args.lat is None) != (args.lon is None):
        parser.error("--lat dan --lon harus diisi bersama")
    if args.lat is not None:
        cells = [h3.latlng_to_cell(args.lat, args.lon, H3_RESOLUTION)]
    else:
        cells = active_cells(args.date)
        if not cells:
            print(f"Tidak ada sel aktif di {args.date}, jalankan ingest FIRMS dulu")
            return 1

    result = weather_with_fwi(cells, args.date)
    if len(cells) == 1:
        columns = ["date", "rain", "temp_noon", "rh_noon", "wind_noon", "ffmc", "dmc", "dc", "fwi"]
        print(result[columns].round(1).to_string(index=False))
        return 0

    today = result[result["date"] == args.date]
    print(f"{len(cells)} sel aktif, {today.isna().any(axis=1).sum()} sel dengan nilai kosong")
    print(today.drop(columns=["h3_index", "date"]).describe().round(1).T.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
