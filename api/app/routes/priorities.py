import csv
import io
from datetime import date

import h3
from fastapi import APIRouter, Query, Response

from app.db import Conn, fetch_cells, resolve_date

router = APIRouter()

COLUMNS = [
    "rank", "h3_index", "lat", "lon", "province", "regency", "priority_score", "priority_class",
    "n_hotspots", "frp_sum", "persistence_days",
]  # fmt: skip


def ranked(conn: Conn, day: date, province: str | None, limit: int | None) -> list[dict]:
    rows = fetch_cells(
        conn, day, province, " ORDER BY p.priority_score DESC, p.h3_index LIMIT :limit", limit=limit
    )
    items = []
    for rank, row in enumerate(rows, start=1):
        row["rank"] = rank
        row["lat"], row["lon"] = (round(v, 5) for v in h3.cell_to_latlng(row["h3_index"]))
        items.append({name: row[name] for name in COLUMNS})
    return items


@router.get("/priorities")
def priorities(
    conn: Conn,
    date: date | None = None,
    province: str | None = None,
    limit: int = Query(50, ge=1, le=1000),
) -> dict:
    day = resolve_date(conn, date)
    summary = {name: 0 for name in ("merah", "oranye", "kuning", "hijau")}
    for row in fetch_cells(conn, day, province):
        summary[row["priority_class"]] += 1
    return {"date": day, "summary": summary, "items": ranked(conn, day, province, limit)}


@router.get("/export.csv")
def export_csv(conn: Conn, date: date | None = None, province: str | None = None) -> Response:
    day = resolve_date(conn, date)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(ranked(conn, day, province, None))
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="prioritas_{day}.csv"'},
    )
