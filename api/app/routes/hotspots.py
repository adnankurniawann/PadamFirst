from datetime import date

import h3
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.db import Conn, resolve_date

router = APIRouter()

MAX_HOTSPOTS = 20000
# Sama dengan titik cuaca pipeline: satu nilai angin per sel resolusi 5.
WIND_RESOLUTION = 5


def parse_bbox(bbox: str) -> tuple[float, float, float, float]:
    try:
        west, south, east, north = (float(part) for part in bbox.split(","))
    except ValueError:
        raise HTTPException(422, "bbox harus west,south,east,north") from None
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise HTTPException(422, "bbox di luar rentang atau terbalik")
    return west, south, east, north


@router.get("/hotspots")
def hotspots(conn: Conn, bbox: str, date: date | None = None) -> dict:
    west, south, east, north = parse_bbox(bbox)
    day = resolve_date(conn, date)
    rows = conn.execute(
        text(
            "SELECT lat, lon, satellite, acq_datetime, frp, confidence, h3_index FROM hotspots "
            "WHERE geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326) "
            # Tanggal waktu matahari setempat, sama dengan features/cells.py di pipeline.
            "AND ((acq_datetime AT TIME ZONE 'UTC') + make_interval(secs => lon * 240))::date "
            "= :date LIMIT :limit"
        ),
        {
            "west": west,
            "south": south,
            "east": east,
            "north": north,
            "date": day,
            "limit": MAX_HOTSPOTS,
        },  # fmt: skip
    ).mappings()
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row["lon"], row["lat"]]},
            "properties": {k: v for k, v in row.items() if k not in ("lat", "lon")},
        }
        for row in rows
    ]
    return {"type": "FeatureCollection", "date": day, "features": features}


@router.get("/wind")
def wind(conn: Conn, date: date | None = None, bbox: str | None = None) -> dict:
    day = resolve_date(conn, date)
    box = parse_bbox(bbox) if bbox else (-180, -90, 180, 90)
    rows = conn.execute(
        text("SELECT h3_index, wind_speed, wind_dir FROM cell_daily WHERE date = :date"),
        {"date": day},
    )
    points = {}
    for cell, speed, direction in rows:
        parent = h3.cell_to_parent(cell, WIND_RESOLUTION)
        lat, lon = h3.cell_to_latlng(parent)
        if parent not in points and box[0] <= lon <= box[2] and box[1] <= lat <= box[3]:
            points[parent] = {
                "lat": round(lat, 4),
                "lon": round(lon, 4),
                "wind_speed": speed,
                "wind_dir": direction,
            }
    return {"date": day, "vectors": list(points.values())}
