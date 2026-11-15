import os
import subprocess
from pathlib import Path

import h3
import pytest
from sqlalchemy import create_engine, text

# Sama seperti test pipeline: hanya menyentuh Postgres compose lokal, database test dibuat sendiri.
SERVER_URL = "postgresql+psycopg://padamfirst:padamfirst@localhost:5433"
TEST_DB = "padamfirst_api_test"
DAY = "2026-11-11"
HOT = h3.latlng_to_cell(-3.3, 105.6, 7)  # Ogan Komering Ilir
MILD = h3.latlng_to_cell(0.5, 101.4, 7)  # Riau

SEED = f"""
INSERT INTO cell_static (h3_index, peat_pct, landcover_class, pop_density, dist_road_km,
                         province, regency) VALUES
  ('{HOT}', 80, 'Tree cover', 40, 3.2, 'Sumatera Selatan', 'Ogan Komering Ilir'),
  ('{MILD}', 0, 'Cropland', 300, 0.5, 'Riau', 'Kota Pekanbaru');
INSERT INTO cell_daily (h3_index, date, n_hotspots, frp_sum, persistence_days, wind_speed,
                        wind_dir, dc)
VALUES ('{HOT}', '{DAY}', 12, 250, 4, 12, 90, 420),
       ('{MILD}', '{DAY}', 1, 3, 1, 5, 180, 100),
       ('{HOT}', '2026-11-10', 8, 120, 3, 10, 90, 410);
INSERT INTO predictions (h3_index, date, model_version, priority_score, priority_class,
                         confidence_level) VALUES
  ('{HOT}', '{DAY}', 'baseline-v1', 81.5, 'merah', 'rendah'),
  ('{MILD}', '{DAY}', 'baseline-v1', 22.0, 'hijau', 'rendah'),
  ('{HOT}', '2026-11-10', 'baseline-v1', 75.0, 'merah', 'rendah');
INSERT INTO hotspots (satellite, instrument, lat, lon, acq_datetime, frp, confidence, h3_index)
VALUES ('N20', 'VIIRS', -3.3, 105.6, '{DAY} 06:00+00', 12.5, 'high', '{HOT}'),
       -- 18:30 UTC tanggal 10 adalah 01:30 waktu setempat tanggal 11
       ('N21', 'VIIRS', -3.3, 105.6, '2026-11-10 18:30+00', 4.0, 'nominal', '{HOT}'),
       ('N21', 'VIIRS', -3.3, 105.6, '2026-11-10 06:00+00', 4.0, 'nominal', '{HOT}');
INSERT INTO ingest_runs (source, started_at, finished_at, rows, status) VALUES
  ('VIIRS_NOAA20_NRT', '{DAY} 01:00+00', '{DAY} 01:01+00', 10, 'failed'),
  ('VIIRS_NOAA20_NRT', '{DAY} 04:00+00', '{DAY} 04:01+00', 5989, 'success');
"""


@pytest.fixture(scope="session", autouse=True)
def database():
    admin = create_engine(f"{SERVER_URL}/postgres", isolation_level="AUTOCOMMIT")
    drop = text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
    with admin.connect() as conn:
        conn.execute(drop)
        conn.execute(text(f"CREATE DATABASE {TEST_DB}"))

    url = f"{SERVER_URL}/{TEST_DB}"
    # Skema hanya didefinisikan di migrasi pipeline, jadi test API memakainya juga.
    pipeline = Path(__file__).parents[2] / "pipeline"
    subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=pipeline,
        env={**os.environ, "DATABASE_URL": url},
        check=True,
        capture_output=True,
    )
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.exec_driver_sql(SEED)
    engine.dispose()

    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", url)
        yield
        from app.db import get_engine

        get_engine().dispose()

    with admin.connect() as conn:
        conn.execute(drop)
    admin.dispose()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    return TestClient(app)
