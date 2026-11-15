from fastapi import APIRouter
from sqlalchemy import text

from app.db import Conn

router = APIRouter()


@router.get("/health")
def health(conn: Conn) -> dict:
    """Status run ingest terakhir per sumber."""
    rows = conn.execute(
        text(
            "SELECT DISTINCT ON (source) source, status, started_at, finished_at, rows, error "
            "FROM ingest_runs ORDER BY source, started_at DESC"
        )
    ).mappings()
    return {"status": "ok", "sources": [dict(row) for row in rows]}
