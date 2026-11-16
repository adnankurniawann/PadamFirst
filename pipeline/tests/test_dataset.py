from datetime import UTC, date, datetime, timedelta

import h3
import pandas as pd

from padamfirst.ingest.weather_archive import cell_points
from padamfirst.model.dataset import FEATURES, label_48h, summary, year_dataset

CELL = h3.latlng_to_cell(0.6, 101.6, 7)
NEIGHBOR = sorted(h3.grid_ring(CELL, 1))[0]
FAR = h3.latlng_to_cell(-2.0, 113.0, 7)
D = date(2019, 9, 10)


def fires(rows):
    return pd.DataFrame(rows, columns=["h3_index", "date"])


def day(n):
    return D + timedelta(days=n)


def test_label_one_when_fire_persists_within_two_days():
    frame = fires([(CELL, day(0)), (CELL, day(2))])
    assert label_48h(frame) == [1, 0]


def test_label_one_when_neighbor_starts_burning():
    frame = fires([(CELL, day(0)), (NEIGHBOR, day(1))])
    # Api tetangga di hari 1 sendiri padam sesudahnya, sel asal tidak terbakar lagi.
    assert label_48h(frame) == [1, 0]


def test_label_ignores_neighbor_that_was_already_burning():
    frame = fires([(CELL, day(0)), (NEIGHBOR, day(0)), (NEIGHBOR, day(1))])
    assert label_48h(frame) == [0, 1, 0]


def test_label_zero_when_fire_dies_or_far_cell_burns():
    frame = fires([(CELL, day(0)), (FAR, day(1)), (CELL, day(3))])
    assert label_48h(frame) == [0, 0, 0]


def hotspot(cell, when):
    lat, lon = h3.cell_to_latlng(cell)
    return {
        "h3_index": cell,
        # Jam 04 UTC di bujur 101 sekitar jam 10.45 waktu setempat, tanggalnya tetap.
        "acq_datetime": pd.Timestamp(datetime.combine(when, datetime.min.time(), UTC))
        + pd.Timedelta(hours=4),
        "lon": lon,
        "frp": 5.0,
        "confidence": "nominal",
    }


def test_year_dataset_joins_weather_land_time_and_drops_unknown_horizon():
    end = date(2019, 11, 30)
    hotspots = pd.DataFrame(
        [hotspot(CELL, D), hotspot(CELL, day(1)), hotspot(CELL, end - timedelta(1))]
    )
    point = cell_points([CELL])["point"].iloc[0]
    dates = pd.date_range(D - timedelta(days=40), end).date
    weather = pd.DataFrame(
        {
            "point": point,
            "date": dates,
            "rain": [2.0 if d == D else 0.0 for d in dates],
            **{column: 1.0 for column in ["temp_max", "rh_min", "wind_speed", "wind_dir"]},
            **{column: 1.0 for column in ["soil_moisture", "ffmc", "dmc", "dc", "fwi"]},
        }
    )
    static = pd.DataFrame(
        {
            "h3_index": [CELL],
            "peat_pct": [80.0],
            "landcover_class": ["Shrubland"],
            "dist_road_km": [3.0],
            "dist_plantation_km": [1.0],
        }
    )

    rows = year_dataset(hotspots, weather, static, 2019)

    # 29 November dibuang, 48 jam sesudahnya di luar arsip Juni sampai November.
    assert rows["date"].tolist() == [D, day(1)]
    assert rows["label"].tolist() == [1, 0]
    assert list(rows.columns) == ["h3_index", "date", "year", *FEATURES, "label"]
    first = rows.iloc[0]
    assert (first["rain_1d"], first["rain_7d"], first["dry_days"]) == (2.0, 2.0, 0)
    assert rows.iloc[1]["dry_days"] == 1
    assert first["peat_pct"] == 80.0
    assert (first["month"], first["season_day"]) == (9, 102)
    assert rows.iloc[1]["persistence_days"] == 2


def test_summary_counts_rows_and_label_rate_per_year():
    frame = pd.DataFrame(
        {"year": [2019, 2019, 2020], "h3_index": ["a", "a", "b"], "label": [1, 0, 1]}
    )
    result = summary(frame)
    assert result.loc[2019].tolist() == [2, 1, 0.5]
