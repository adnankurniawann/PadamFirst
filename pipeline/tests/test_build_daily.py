from datetime import date, timedelta

import h3
import pandas as pd
import pytest

from padamfirst.features.build_daily import build_daily, fire_features, rain_features

DAY = date(2026, 11, 10)
CELL = h3.latlng_to_cell(-3.3, 105.6, 7)
NEIGHBOR, OTHER_NEIGHBOR = h3.grid_ring(CELL, 1)[:2]
FAR = h3.latlng_to_cell(0.5, 101.4, 7)


def fires_on(cell, days_ago, n=1):
    return pd.DataFrame(
        {
            "h3_index": cell,
            "date": [DAY - timedelta(days=d) for d in days_ago],
            "n_hotspots": n,
            "frp_sum": 10.0,
            "frp_max": 10.0,
            "conf_mean": 0.5,
        }
    )


def persistence(days_ago):
    result = fire_features(fires_on(CELL, days_ago))
    return result.loc[result["date"] == DAY, "persistence_days"].item()


@pytest.mark.parametrize(
    ("days_ago", "expected"),
    [
        ([0], 1),
        ([2, 1, 0], 3),
        # Satu hari bolong (awan) tidak memutus rentetan, hitungannya hari kalender.
        ([5, 4, 2, 1, 0], 6),
        ([2, 0], 3),
        # Dua hari bolong memutus rentetan.
        ([4, 3, 0], 1),
        ([6, 5, 2, 1, 0], 3),
    ],
)
def test_persistence_tolerates_one_missing_day(days_ago, expected):
    assert persistence(days_ago) == expected


def test_persistence_is_per_cell():
    fires = pd.concat([fires_on(CELL, [3, 2, 1, 0]), fires_on(FAR, [0])])
    result = fire_features(fires).set_index(["h3_index", "date"])
    assert result.loc[(FAR, DAY), "persistence_days"] == 1
    assert result.loc[(CELL, DAY), "persistence_days"] == 4


def test_growth_compares_with_previous_day():
    fires = pd.concat([fires_on(CELL, [1], n=3), fires_on(CELL, [0], n=5), fires_on(FAR, [0], 4)])
    result = fire_features(fires).set_index(["h3_index", "date"])
    assert result.loc[(CELL, DAY), "growth_24h"] == 2
    assert result.loc[(FAR, DAY), "growth_24h"] == 4


def test_neighbors_burning_counts_ring_one_on_same_day():
    fires = pd.concat(
        [
            fires_on(CELL, [0]),
            fires_on(NEIGHBOR, [0]),
            fires_on(OTHER_NEIGHBOR, [1]),
            fires_on(FAR, [0]),
        ]
    )
    result = fire_features(fires).set_index(["h3_index", "date"])
    assert result.loc[(CELL, DAY), "neighbors_burning"] == 1
    assert result.loc[(NEIGHBOR, DAY), "neighbors_burning"] == 1
    assert result.loc[(FAR, DAY), "neighbors_burning"] == 0


def weather_for(cell, rain):
    days = len(rain)
    return pd.DataFrame(
        {
            "h3_index": cell,
            "date": [DAY - timedelta(days=days - 1 - i) for i in range(days)],
            "rain": rain,
            "temp_max": 33.0,
            "rh_min": 45.0,
            "wind_speed": 6.0,
            "wind_dir": 120.0,
            "soil_moisture": 0.3,
            "ffmc": 88.0,
            "dmc": 20.0,
            "dc": 300.0,
            "fwi": 12.0,
        }
    )


def test_rain_features_windows_and_dry_days():
    # 30 hari: 10 mm di hari ke-25 dari akhir, 0.5 mm (masih kering) di hari terakhir.
    rain = [0.0] * 30
    rain[5] = 10.0
    rain[-1] = 0.5
    result = rain_features(weather_for(CELL, rain)).set_index("date")

    today = result.loc[DAY]
    assert today["rain_7d"] == pytest.approx(0.5)
    assert today["rain_30d"] == pytest.approx(10.5)
    assert today["dry_days"] == 24
    assert pd.isna(result.loc[DAY - timedelta(days=29), "rain_30d"])


def test_dry_days_is_zero_on_wet_day():
    result = rain_features(weather_for(CELL, [0.0, 0.0, 5.0])).set_index("date")
    assert result.loc[DAY, "dry_days"] == 0
    assert result.loc[DAY - timedelta(days=1), "dry_days"] == 2


def test_build_daily_returns_full_rows_for_active_cells_only():
    fires = pd.concat([fires_on(CELL, [1, 0]), fires_on(FAR, [1])])
    weather = pd.concat([weather_for(CELL, [0.0] * 31), weather_for(FAR, [0.0] * 31)])
    result = build_daily(fires, weather, DAY)

    assert result["h3_index"].tolist() == [CELL]
    assert set(result.columns) == {
        "h3_index", "date", "n_hotspots", "frp_sum", "frp_max", "conf_mean",
        "persistence_days", "growth_24h", "neighbors_burning",
        "wind_speed", "wind_dir", "rain_1d", "rain_7d", "rain_30d", "dry_days",
        "temp_max", "rh_min", "soil_moisture", "ffmc", "dmc", "dc", "fwi",
    }  # fmt: skip
    assert not result.isna().any(axis=None)
    assert result["dry_days"].item() == 31
