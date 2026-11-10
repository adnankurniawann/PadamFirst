from datetime import date, timedelta

import h3
import httpx
import pandas as pd
import pytest

from padamfirst.ingest import weather


def fake_location(lat, start, end, rain=0.0):
    days = pd.date_range(start, end).strftime("%Y-%m-%d").tolist()
    hours = [f"{day}T{hour:02d}:00" for day in days for hour in range(24)]
    return {
        "latitude": lat,
        "daily": {
            "time": days,
            "temperature_2m_max": [lat + 40] * len(days),
            "relative_humidity_2m_min": [45] * len(days),
            "precipitation_sum": [rain] * len(days),
            "wind_speed_10m_mean": [6.0] * len(days),
            "wind_direction_10m_dominant": [120] * len(days),
        },
        "hourly": {
            "time": hours,
            # Jam 12 suhunya 32, selain itu 25, supaya kelihatan kalau salah ambil jam.
            "temperature_2m": [32.0 if h.endswith("T12:00") else 25.0 for h in hours],
            "relative_humidity_2m": [50 if h.endswith("T12:00") else 90 for h in hours],
            "wind_speed_10m": [10.0 if h.endswith("T12:00") else 2.0 for h in hours],
            "soil_moisture_0_to_7cm": [0.2, 0.4] * (len(hours) // 2),
        },
    }


class FakeApi:
    def __init__(self, statuses=(), rain=0.0):
        self.calls = []
        self.statuses = list(statuses)
        self.rain = rain

    def get(self, url, params, timeout):
        self.calls.append((url, params))
        if self.statuses:
            status = self.statuses.pop(0)
            if status != 200:
                return httpx.Response(status, json={"error": True, "reason": "nope"})
        lats = [float(lat) for lat in params["latitude"].split(",")]
        body = [
            fake_location(lat, params["start_date"], params["end_date"], self.rain) for lat in lats
        ]
        return httpx.Response(200, json=body[0] if len(body) == 1 else body)


@pytest.fixture
def api(monkeypatch):
    fake = FakeApi()
    monkeypatch.setattr(weather.httpx, "get", fake.get)
    monkeypatch.setattr(weather.time, "sleep", lambda seconds: None)
    return fake


def test_parse_location_takes_noon_values_and_daily_soil_mean():
    parsed = weather.parse_location(fake_location(-2.0, "2019-09-01", "2019-09-02"))

    assert parsed["date"].tolist() == [date(2019, 9, 1), date(2019, 9, 2)]
    assert parsed["temp_noon"].tolist() == [32.0, 32.0]
    assert parsed["rh_noon"].tolist() == [50, 50]
    assert parsed["wind_noon"].tolist() == [10.0, 10.0]
    assert parsed["soil_moisture"].tolist() == pytest.approx([0.3, 0.3])
    assert parsed["temp_max"].tolist() == [38.0, 38.0]


def test_endpoint_uses_archive_only_for_settled_days():
    today = date(2026, 11, 10)
    assert weather.endpoint(date(2019, 9, 30), today) == weather.ARCHIVE_URL
    assert weather.endpoint(today - timedelta(days=7), today) == weather.ARCHIVE_URL
    assert weather.endpoint(today - timedelta(days=6), today) == weather.FORECAST_URL


def test_weather_points_share_parent_cell():
    cell = h3.latlng_to_cell(-2.6, 105.36, 7)
    sibling = next(
        c
        for c in h3.grid_disk(cell, 1)
        if h3.cell_to_parent(c, 5) == h3.cell_to_parent(cell, 5) and c != cell
    )

    points = weather.weather_points([cell, sibling])

    assert points["point"].nunique() == 1
    assert points["point"].iloc[0] == h3.cell_to_parent(cell, weather.WEATHER_RESOLUTION)


def test_fetch_json_caches_per_day(api, tmp_path):
    params = {"latitude": "1.0", "start_date": "2019-09-01", "end_date": "2019-09-01"}

    first = weather.fetch_json(weather.ARCHIVE_URL, params, tmp_path)
    second = weather.fetch_json(weather.ARCHIVE_URL, params, tmp_path)

    assert first == second
    assert isinstance(first, list) and len(first) == 1
    assert len(api.calls) == 1
    assert (tmp_path / date.today().isoformat()).is_dir()


def test_fetch_json_retries_rate_limit_and_server_errors(api, tmp_path):
    api.statuses = [429, 503, 200]
    params = {"latitude": "1.0", "start_date": "2019-09-01", "end_date": "2019-09-01"}

    assert len(weather.fetch_json(weather.ARCHIVE_URL, params, tmp_path)) == 1
    assert len(api.calls) == 3


def test_fetch_json_gives_up_after_retries(api, tmp_path):
    api.statuses = [429] * weather.RETRIES
    with pytest.raises(RuntimeError, match="429"):
        weather.fetch_json(weather.ARCHIVE_URL, {"latitude": "1.0"}, tmp_path)
    assert len(api.calls) == weather.RETRIES


def test_fetch_json_does_not_retry_bad_request(api, tmp_path):
    api.statuses = [400]
    with pytest.raises(RuntimeError, match="nope"):
        weather.fetch_json(weather.ARCHIVE_URL, {"latitude": "1.0"}, tmp_path)
    assert len(api.calls) == 1


def test_fetch_weather_batches_and_keeps_order(api, tmp_path):
    points = pd.DataFrame(
        {"point": [f"p{i}" for i in range(250)], "lat": [i / 100 for i in range(250)], "lon": 100.0}
    )

    result = weather.fetch_weather(points, date(2019, 9, 1), date(2019, 9, 2), tmp_path)

    assert [len(params["latitude"].split(",")) for _, params in api.calls] == [100, 100, 50]
    assert len(result) == 500
    # temp_max palsu = lat + 40, jadi tiap titik harus dapat lokasinya sendiri.
    expected = points.set_index("point")["lat"] + 40
    assert (result["temp_max"] == result["point"].map(expected)).all()


def test_weather_with_fwi_covers_spin_up_and_target_day(api, tmp_path):
    cells = [h3.latlng_to_cell(0.5, 101.4, 7), h3.latlng_to_cell(-2.6, 105.36, 7)]
    day = date(2019, 9, 30)

    result = weather.weather_with_fwi(cells, day, tmp_path)

    assert len(result) == 2 * (weather.SPIN_UP_DAYS + 1)
    assert result["date"].min() == day - timedelta(days=weather.SPIN_UP_DAYS)
    assert not result.isna().any().any()
    # Tanpa hujan DC terus naik dari nilai awal 15.
    dc = result[result["h3_index"] == cells[0]].sort_values("date")["dc"]
    assert dc.is_monotonic_increasing and dc.iloc[0] > 15


def test_main_requires_lat_and_lon_together():
    with pytest.raises(SystemExit):
        weather.main(["--lat", "0.5"])
