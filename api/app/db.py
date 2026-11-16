import os
from collections.abc import Iterator
from datetime import date
from functools import cache
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import Connection, Engine, create_engine, make_url, text

# Fase 12 mengganti ini ke versi LightGBM.
MODEL_VERSION = "baseline-v1"


@cache
def get_engine() -> Engine:
    # Paksa driver psycopg: URL "postgresql://" polos akan memilih psycopg2 yang tidak terpasang.
    url = make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql+psycopg")
    return create_engine(url)


def get_conn() -> Iterator[Connection]:
    with get_engine().connect() as conn:
        yield conn


Conn = Annotated[Connection, Depends(get_conn)]


def resolve_date(conn: Connection, day: date | None) -> date:
    """Tanggal yang diminta, atau tanggal skor terbaru kalau kosong."""
    if day is not None:
        return day
    latest = conn.execute(
        text("SELECT max(date) FROM predictions WHERE model_version = :version"),
        {"version": MODEL_VERSION},
    ).scalar()
    if latest is None:
        raise HTTPException(404, "Belum ada skor prioritas, jalankan padamfirst.scoring")
    return latest


# Satu baris per sel aktif: skor, fitur harian, dan faktor statis.
CELLS_SQL = """
SELECT p.h3_index, p.date, p.priority_score, p.priority_class, p.p_spread, p.impact_score,
       p.fire_score, p.confidence_level, p.shap_top,
       d.n_hotspots, d.frp_sum, d.frp_max, d.conf_mean, d.persistence_days, d.growth_24h,
       d.neighbors_burning, d.wind_speed, d.wind_dir, d.rain_1d, d.rain_7d, d.rain_30d,
       d.dry_days, d.temp_max, d.rh_min, d.soil_moisture, d.ffmc, d.dmc, d.dc, d.fwi,
       s.peat_pct, s.peat_depth_cm, s.landcover_class, s.pop_density, s.dist_road_km,
       s.dist_plantation_km, s.province, s.regency
FROM predictions p
JOIN cell_daily d USING (h3_index, date)
LEFT JOIN cell_static s USING (h3_index)
WHERE p.model_version = :version AND p.date = :date
  AND (CAST(:province AS text) IS NULL OR s.province = :province)
  AND (CAST(:regency AS text) IS NULL OR s.regency = :regency)
"""


def fetch_cells(
    conn: Connection,
    day: date,
    province: str | None,
    extra: str = "",
    regency: str | None = None,
    **params,
) -> list[dict]:
    """Baris CELLS_SQL, extra untuk filter atau urutan tambahan dengan parameternya di params."""
    rows = conn.execute(
        text(CELLS_SQL + extra),
        {"version": MODEL_VERSION, "date": day, "province": province, "regency": regency, **params},
    )
    return [dict(row) for row in rows.mappings()]
