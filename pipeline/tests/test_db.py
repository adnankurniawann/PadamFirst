from datetime import UTC, date, datetime

import pytest
from alembic import command
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from padamfirst.db import get_engine, upsert

TABLES = {"hotspots", "cell_static", "cell_daily", "predictions", "ingest_runs"}
HOTSPOT_KEY = ("satellite", "lat", "lon", "acq_datetime")


def hotspot(**overrides):
    return {
        "satellite": "N20",
        "instrument": "VIIRS",
        "lat": -3.4,
        "lon": 105.2,
        "acq_datetime": datetime(2026, 9, 1, 6, 30, tzinfo=UTC),
        "frp": 10.0,
        "confidence": "nominal",
        "h3_index": "876526a2bffffff",
        **overrides,
    }


def scalar(conn, sql):
    return conn.execute(text(sql)).scalar_one()


def test_get_engine_forces_psycopg_driver(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:p%40ss@example.test:5432/db")
    url = get_engine().url
    assert url.drivername == "postgresql+psycopg"
    assert url.password == "p@ss"


def test_migration_creates_tables_and_indexes(conn):
    inspector = inspect(conn)
    assert TABLES <= set(inspector.get_table_names())
    assert {"ix_hotspots_h3_index", "ix_hotspots_acq_datetime", "ix_hotspots_geom"} <= {
        ix["name"] for ix in inspector.get_indexes("hotspots")
    }
    assert "USING gist" in scalar(
        conn, "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_hotspots_geom'"
    )


def test_migration_is_reversible(engine, alembic_config):
    command.downgrade(alembic_config, "base")
    try:
        assert not TABLES & set(inspect(engine).get_table_names())
    finally:
        command.upgrade(alembic_config, "head")
    assert TABLES <= set(inspect(engine).get_table_names())


def test_upsert_inserts_then_updates_without_duplicates(conn):
    assert upsert(conn, "hotspots", [hotspot()], HOTSPOT_KEY) == 1
    upsert(conn, "hotspots", [hotspot(frp=99.5, confidence="high")], HOTSPOT_KEY)

    row = conn.execute(text("SELECT frp, confidence FROM hotspots")).one()
    assert tuple(row) == (99.5, "high")
    assert scalar(conn, "SELECT count(*) FROM hotspots") == 1


def test_upsert_writes_every_batch(conn):
    rows = [hotspot(lat=-3.0 - i / 10) for i in range(5)]
    assert upsert(conn, "hotspots", rows, HOTSPOT_KEY, batch_size=2) == 5
    assert scalar(conn, "SELECT count(*) FROM hotspots") == 5


def test_upsert_tolerates_repeated_key_in_one_call(conn):
    rows = [hotspot(frp=1.0), hotspot(frp=2.0)]
    upsert(conn, "hotspots", rows, HOTSPOT_KEY)
    assert scalar(conn, "SELECT frp FROM hotspots") == 2.0


def test_upsert_empty_rows_is_noop(conn):
    assert upsert(conn, "hotspots", [], HOTSPOT_KEY) == 0
    assert scalar(conn, "SELECT count(*) FROM hotspots") == 0


def test_upsert_stores_jsonb(conn):
    shap = [{"feature": "dc", "value": 0.31}]
    row = {
        "h3_index": "876526a2bffffff",
        "date": date(2026, 9, 1),
        "model_version": "baseline-v1",
        "priority_score": 72.5,
        "priority_class": "merah",
        "shap_top": shap,
    }
    upsert(conn, "predictions", [row], ("h3_index", "date", "model_version"))
    assert scalar(conn, "SELECT shap_top FROM predictions") == shap


def test_cell_daily_upsert_is_unique_per_cell_and_date(conn):
    key = ("h3_index", "date")
    row = {"h3_index": "876526a2bffffff", "date": date(2026, 9, 1), "n_hotspots": 3}
    upsert(conn, "cell_daily", [row], key)
    upsert(conn, "cell_daily", [{**row, "n_hotspots": 7}], key)
    assert scalar(conn, "SELECT n_hotspots FROM cell_daily") == 7
    assert scalar(conn, "SELECT count(*) FROM cell_daily") == 1


def test_geom_follows_lat_lon(conn):
    upsert(conn, "hotspots", [hotspot()], HOTSPOT_KEY)
    assert scalar(conn, "SELECT ST_AsText(geom) FROM hotspots") == "POINT(105.2 -3.4)"
    assert scalar(conn, "SELECT ST_SRID(geom) FROM hotspots") == 4326


def test_hotspots_reject_unknown_confidence(conn):
    with pytest.raises(IntegrityError):
        upsert(conn, "hotspots", [hotspot(confidence="85")], HOTSPOT_KEY)
