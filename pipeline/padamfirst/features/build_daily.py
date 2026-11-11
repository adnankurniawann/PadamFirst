"""Bangun fitur harian per sel aktif ke tabel cell_daily.

python -m padamfirst.features.build_daily                  # hari ini
python -m padamfirst.features.build_daily --date 2026-11-10
"""

import argparse
from datetime import date, timedelta

import h3
import pandas as pd
from sqlalchemy import text

from padamfirst.db import get_engine, upsert
from padamfirst.features.cells import aggregate_hotspots
from padamfirst.ingest.weather import SPIN_UP_DAYS, weather_with_fwi

# Satu hari tanpa deteksi tidak memutus persistensi, biasanya api tertutup awan.
MAX_GAP_DAYS = 1
# Ambang hari kering yang umum dipakai BMKG dan literatur kekeringan.
DRY_RAIN_MM = 1.0
HISTORY_DAYS = 60

WEATHER_COLUMNS = {
    "wind_speed": "wind_speed",
    "wind_dir": "wind_dir",
    "rain": "rain_1d",
    "temp_max": "temp_max",
    "rh_min": "rh_min",
    "soil_moisture": "soil_moisture",
    "ffmc": "ffmc",
    "dmc": "dmc",
    "dc": "dc",
    "fwi": "fwi",
}


def fire_features(fires: pd.DataFrame) -> pd.DataFrame:
    """Tambah persistence_days, growth_24h, neighbors_burning ke hasil aggregate_hotspots.

    persistence_days adalah jumlah hari kalender sejak awal rentetan api di sel itu sampai
    hari ini, dengan bolong paling lama MAX_GAP_DAYS hari tidak memutus rentetan.
    """
    frame = fires.sort_values(["h3_index", "date"]).reset_index(drop=True)
    dates = pd.to_datetime(frame["date"])
    gap = dates.groupby(frame["h3_index"]).diff().dt.days
    streak = (gap.isna() | (gap > MAX_GAP_DAYS + 1)).cumsum()
    frame["persistence_days"] = (dates - dates.groupby(streak).transform("min")).dt.days + 1

    count = frame.set_index(["h3_index", "date"])["n_hotspots"]
    yesterday = [(cell, day - timedelta(days=1)) for cell, day in count.index]
    frame["growth_24h"] = frame["n_hotspots"] - count.reindex(yesterday, fill_value=0).to_numpy()

    burning = set(count.index)
    frame["neighbors_burning"] = [
        sum((neighbor, day) in burning for neighbor in h3.grid_ring(cell, 1))
        for cell, day in count.index
    ]
    return frame


def rain_features(weather: pd.DataFrame) -> pd.DataFrame:
    """rain_7d, rain_30d, dry_days per sel per hari dari kolom rain harian.

    Hari awal yang belum punya 30 hari riwayat bernilai kosong. dry_days paling banyak sepanjang
    riwayat yang diberikan.
    """
    frame = weather[["h3_index", "date", "rain"]].sort_values(["h3_index", "date"])
    rain = frame.groupby("h3_index")["rain"]
    frame["rain_7d"] = rain.transform(lambda s: s.rolling(7).sum())
    frame["rain_30d"] = rain.transform(lambda s: s.rolling(30).sum())
    wet = frame["rain"] >= DRY_RAIN_MM
    since_wet = wet.groupby(frame["h3_index"]).cumsum()
    frame["dry_days"] = (~wet).groupby([frame["h3_index"], since_wet]).cumsum()
    return frame.drop(columns="rain")


def build_daily(fires: pd.DataFrame, weather: pd.DataFrame, day: date) -> pd.DataFrame:
    """Baris cell_daily untuk sel yang punya titik api di day.

    fires dari aggregate_hotspots dengan riwayat beberapa hari sebelum day, weather dari
    weather_with_fwi dengan riwayat minimal 30 hari.
    """
    today = fire_features(fires)
    today = today[today["date"] == day]
    weather_today = weather.merge(rain_features(weather), on=["h3_index", "date"])
    weather_today = weather_today[weather_today["date"] == day]
    columns = [*WEATHER_COLUMNS, "rain_7d", "rain_30d", "dry_days"]
    merged = today.merge(weather_today[["h3_index", *columns]], on="h3_index", how="left")
    return merged.rename(columns=WEATHER_COLUMNS)


def load_hotspots(day: date) -> pd.DataFrame:
    with get_engine().connect() as conn:
        return pd.read_sql(
            text(
                "SELECT h3_index, acq_datetime, lon, frp, confidence FROM hotspots "
                "WHERE acq_datetime >= :start AND acq_datetime < :end"
            ),
            conn,
            params={"start": day - timedelta(days=HISTORY_DAYS + 1), "end": day + timedelta(2)},
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    args = parser.parse_args(argv)

    fires = aggregate_hotspots(load_hotspots(args.date))
    fires = fires[fires["date"] <= args.date]
    cells = fires.loc[fires["date"] == args.date, "h3_index"].tolist()
    if not cells:
        print(f"Tidak ada sel aktif di {args.date}, jalankan ingest FIRMS dulu")
        return 1

    assert SPIN_UP_DAYS >= 30, "rain_30d butuh riwayat cuaca 30 hari"
    rows = build_daily(fires, weather_with_fwi(cells, args.date), args.date)
    # Kosongkan NaN supaya tersimpan sebagai NULL, bukan NaN, di kolom double.
    records = rows.astype(object).where(rows.notna(), None).to_dict("records")
    with get_engine().begin() as conn:
        upsert(conn, "cell_daily", records, ["h3_index", "date"])

    empty = rows.isna().any(axis=1).sum()
    print(f"{args.date}: {len(rows)} sel aktif ke cell_daily, {empty} sel dengan kolom kosong")
    print(rows.drop(columns=["h3_index", "date"]).describe().round(1).T.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
