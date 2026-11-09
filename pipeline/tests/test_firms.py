from datetime import UTC, datetime

import h3
import httpx
import pytest
import shapely
from sqlalchemy import text

from padamfirst.ingest import firms

HEADER = (
    "latitude,longitude,bright_ti4,scan,track,acq_date,acq_time,satellite,instrument,"
    "confidence,version,bright_ti5,frp,daynight\n"
)
CSV = HEADER + (
    "-3.4,105.2,335.8,0.57,0.69,2026-09-01,325,N20,VIIRS,n,2.0NRT,292.31,4.05,D\n"
    "-3.5,105.3,340.8,0.56,0.69,2026-09-01,1742,N20,VIIRS,h,2.0NRT,294.79,10.14,N\n"
    "4.0,120.0,340.8,0.56,0.69,2026-09-01,1742,N20,VIIRS,l,2.0NRT,294.79,1.5,N\n"
)
# Dua titik pertama di CSV ada di dalam kotak ini, titik ketiga di luar.
LAND = shapely.box(100, -5, 110, 0)
KEY = "secretkey123"


@pytest.fixture
def clean_tables(engine):
    def truncate():
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE hotspots, ingest_runs"))

    truncate()
    yield
    truncate()


def rows_of(engine, sql):
    with engine.connect() as conn:
        return conn.execute(text(sql)).all()


def test_parse_csv_normalizes_fields():
    parsed = firms.parse_csv(CSV)

    assert parsed["confidence"].tolist() == ["nominal", "high", "low"]
    assert parsed["acq_datetime"].iloc[0] == datetime(2026, 9, 1, 3, 25, tzinfo=UTC)
    assert parsed["acq_datetime"].iloc[1] == datetime(2026, 9, 1, 17, 42, tzinfo=UTC)
    assert parsed["h3_index"].iloc[0] == h3.latlng_to_cell(-3.4, 105.2, 7)
    assert parsed["satellite"].iloc[0] == "N20"
    assert parsed["frp"].iloc[0] == 4.05


def test_parse_csv_accepts_header_only_response():
    assert firms.parse_csv(HEADER).empty


@pytest.mark.parametrize("body", ["Invalid MAP_KEY.", "Exceeding allowed transaction limit."])
def test_parse_csv_rejects_non_csv_body(body):
    with pytest.raises(ValueError, match="kolom hilang"):
        firms.parse_csv(body)


def test_parse_csv_rejects_unknown_confidence():
    with pytest.raises(ValueError, match="85"):
        firms.parse_csv(CSV.replace(",n,2.0NRT", ",85,2.0NRT"))


def test_keep_on_land_drops_points_outside():
    kept = firms.keep_on_land(firms.parse_csv(CSV), LAND)
    assert kept["lat"].tolist() == [-3.4, -3.5]


def test_keep_on_land_handles_empty_frame():
    assert firms.keep_on_land(firms.parse_csv(HEADER), LAND).empty


def test_fetch_csv_error_does_not_leak_key(monkeypatch):
    response = httpx.Response(400, text="Invalid MAP_KEY.")
    monkeypatch.setattr(firms.httpx, "get", lambda url, timeout: response)

    with pytest.raises(RuntimeError) as error:
        firms.fetch_csv("VIIRS_NOAA20_NRT", 2, KEY)
    assert "Invalid MAP_KEY" in str(error.value)
    assert KEY not in str(error.value)


def test_fetch_csv_builds_documented_url(monkeypatch):
    seen = []

    def fake_get(url, timeout):
        seen.append(url)
        return httpx.Response(200, text=HEADER)

    monkeypatch.setattr(firms.httpx, "get", fake_get)
    assert firms.fetch_csv("VIIRS_NOAA21_NRT", 3, KEY) == HEADER
    assert seen == [
        "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{KEY}/VIIRS_NOAA21_NRT/94.5,-11.5,141.5,6.5/3"
    ]


def test_ingest_source_is_idempotent_and_logs_runs(engine, clean_tables, monkeypatch):
    monkeypatch.setattr(firms, "fetch_csv", lambda source, days, key: CSV)

    assert firms.ingest_source(engine, "VIIRS_NOAA20_NRT", 2, KEY, LAND)
    assert firms.ingest_source(engine, "VIIRS_NOAA20_NRT", 2, KEY, LAND)

    assert rows_of(engine, "SELECT count(*) FROM hotspots")[0][0] == 2
    runs = rows_of(
        engine, "SELECT source, status, rows, error, finished_at FROM ingest_runs ORDER BY id"
    )
    assert [tuple(run)[:4] for run in runs] == [("VIIRS_NOAA20_NRT", "success", 2, None)] * 2
    assert all(run.finished_at is not None for run in runs)


def test_ingest_source_stores_missing_frp_as_null(engine, clean_tables, monkeypatch):
    csv = HEADER + "-3.4,105.2,335.8,0.57,0.69,2026-09-01,325,N20,VIIRS,n,2.0NRT,292.31,,D\n"
    monkeypatch.setattr(firms, "fetch_csv", lambda source, days, key: csv)

    assert firms.ingest_source(engine, "VIIRS_NOAA20_NRT", 2, KEY, LAND)
    assert rows_of(engine, "SELECT frp FROM hotspots")[0][0] is None


def test_ingest_source_logs_empty_source_as_success(engine, clean_tables, monkeypatch):
    monkeypatch.setattr(firms, "fetch_csv", lambda source, days, key: HEADER)

    assert firms.ingest_source(engine, "VIIRS_SNPP_NRT", 2, KEY, LAND)
    assert tuple(rows_of(engine, "SELECT status, rows FROM ingest_runs")[0]) == ("success", 0)


def test_ingest_source_failure_is_logged_without_key(engine, clean_tables, monkeypatch):
    def boom(source, days, key):
        raise httpx.ConnectError(f"cannot reach https://example.test/{key}/x")

    monkeypatch.setattr(firms, "fetch_csv", boom)

    assert not firms.ingest_source(engine, "VIIRS_NOAA20_NRT", 2, KEY, LAND)
    status, error = rows_of(engine, "SELECT status, error FROM ingest_runs")[0]
    assert status == "failed"
    assert "ConnectError" in error
    assert KEY not in error
    assert rows_of(engine, "SELECT count(*) FROM hotspots")[0][0] == 0


def test_ingest_source_invalid_body_writes_nothing(engine, clean_tables, monkeypatch):
    monkeypatch.setattr(firms, "fetch_csv", lambda source, days, key: "Invalid MAP_KEY.")

    assert not firms.ingest_source(engine, "VIIRS_NOAA20_NRT", 2, KEY, LAND)
    assert rows_of(engine, "SELECT count(*) FROM hotspots")[0][0] == 0


@pytest.mark.parametrize(("results", "code"), [([True, True, True], 0), ([True, False, True], 1)])
def test_main_runs_every_source_and_reports_failure(monkeypatch, results, code):
    outcomes = iter(results)
    called = []

    def fake_ingest(engine, source, days, key, land):
        called.append((source, days))
        return next(outcomes)

    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@example.test/db")
    monkeypatch.setenv("FIRMS_MAP_KEY", KEY)
    monkeypatch.setattr(firms, "load_land", lambda: LAND)
    monkeypatch.setattr(firms, "ingest_source", fake_ingest)

    assert firms.main(["--days", "3"]) == code
    assert called == [(source, 3) for source in firms.SOURCES]


@pytest.mark.parametrize("days", ["0", "6"])
def test_main_rejects_days_outside_firms_range(days):
    with pytest.raises(SystemExit):
        firms.main(["--days", days])
