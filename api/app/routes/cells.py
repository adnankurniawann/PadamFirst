from datetime import date, timedelta
from typing import Literal

import h3
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.db import MODEL_VERSION, Conn, fetch_cells, resolve_date
from app.layers import LAYER_COLUMNS, LAYERS

router = APIRouter()

LayerId = Literal[tuple(LAYER_COLUMNS)]


def polygon(cell: str) -> dict:
    ring = [[lng, lat] for lat, lng in h3.cell_to_boundary(cell)]
    return {"type": "Polygon", "coordinates": [[*ring, ring[0]]]}


@router.get("/layers")
def layers() -> list[dict]:
    keys = ("id", "column", "label", "group", "unit", "scheme")
    return [dict(zip(keys, layer, strict=True)) for layer in LAYERS]


@router.get("/cells")
def cells(
    conn: Conn,
    date: date | None = None,
    layer: LayerId = "priority",
    province: str | None = None,
    regency: str | None = None,
) -> dict:
    day = resolve_date(conn, date)
    column = LAYER_COLUMNS[layer]
    features = [
        {
            "type": "Feature",
            "geometry": polygon(row["h3_index"]),
            "properties": {
                "h3_index": row["h3_index"],
                "value": row[column],
                "priority_score": row["priority_score"],
                "priority_class": row["priority_class"],
                "province": row["province"],
                "regency": row["regency"],
            },
        }
        for row in fetch_cells(conn, day, province, regency=regency)
    ]
    return {"type": "FeatureCollection", "date": day, "layer": layer, "features": features}


@router.get("/cells/{h3_index}")
def cell_detail(conn: Conn, h3_index: str, date: date | None = None) -> dict:
    if not h3.is_valid_cell(h3_index):
        raise HTTPException(422, "h3_index tidak valid")
    day = resolve_date(conn, date)
    rows = fetch_cells(conn, day, None, " AND p.h3_index = :cell", cell=h3_index)
    if not rows:
        raise HTTPException(404, f"Sel {h3_index} tidak aktif di {day}")
    detail = rows[0]
    detail["lat"], detail["lon"] = h3.cell_to_latlng(h3_index)
    detail["history"] = [
        dict(row)
        for row in conn.execute(
            text(
                "SELECT d.date, d.n_hotspots, d.frp_sum, p.priority_score FROM cell_daily d "
                "LEFT JOIN predictions p ON p.h3_index = d.h3_index AND p.date = d.date "
                "AND p.model_version = :version "
                "WHERE d.h3_index = :cell AND d.date > :start AND d.date <= :date ORDER BY d.date"
            ),
            {"version": MODEL_VERSION, "cell": h3_index, "start": day - timedelta(7), "date": day},
        ).mappings()
    ]
    return detail
