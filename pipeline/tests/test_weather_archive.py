from datetime import date

import h3
import pandas as pd
import pytest

from padamfirst.ingest import weather, weather_archive
from tests.test_weather import FakeApi


@pytest.fixture
def api(monkeypatch):
    fake = FakeApi()
    monkeypatch.setattr(weather.httpx, "get", fake.get)
    monkeypatch.setattr(weather.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(weather_archive.time, "sleep", lambda seconds: None)
    return fake


def fires(rows):
    return pd.DataFrame(rows, columns=["h3_index", "date"])


RIAU = h3.latlng_to_cell(0.6, 101.6, 7)
RIAU_NEAR = h3.latlng_to_cell(0.65, 101.65, 7)
JAMBI = h3.latlng_to_cell(-1.6, 103.6, 7)


def test_season_points_shares_box_and_spans_season():
    points = weather_archive.season_points(
        fires(
            [
                (RIAU, date(2019, 8, 20)),
                (RIAU_NEAR, date(2019, 9, 30)),
                (JAMBI, date(2019, 6, 1)),
            ]
        )
    ).set_index("point")

    assert len(points) == 2
    riau = points.loc["0.5,101.5"]
    # 60 hari sebelum 20 Agustus jatuh di Juni, dibulatkan ke 1 Juni.
    assert (riau["start"], riau["end"]) == (date(2019, 6, 1), date(2019, 9, 30))
    assert 0.6 <= riau["lat"] <= 0.65
    assert points.loc["-1.5,103.5", "start"] == date(2019, 4, 1)


def test_season_weather_computes_fwi_for_points_with_different_starts(api, tmp_path):
    points = weather_archive.season_points(
        fires([(RIAU, date(2019, 9, 5)), (JAMBI, date(2019, 7, 15))])
    )

    result = weather_archive.season_weather(points, tmp_path)

    assert len(api.calls) == 2
    assert not result[["ffmc", "dc", "fwi"]].isna().any().any()
    for _, rows in result.groupby("point"):
        # Tanpa hujan DC terus naik dari hari pertama tiap titik.
        assert rows.sort_values("date")["dc"].is_monotonic_increasing


def test_fetch_point_waits_out_rate_limit(api, tmp_path):
    api.statuses = [429] * (weather.RETRIES + 1) + [200]
    point = weather_archive.season_points(fires([(RIAU, date(2019, 9, 5))])).iloc[0]

    assert len(weather_archive.fetch_point(point, tmp_path)) == 1
    assert len(api.calls) == weather.RETRIES + 2


def test_weighted_calls_counts_two_week_blocks():
    points = pd.DataFrame({"start": [date(2019, 9, 1)], "end": [date(2019, 9, 15)]})
    assert weather_archive.weighted_calls(points) == 2
