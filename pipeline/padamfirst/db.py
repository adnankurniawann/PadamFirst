import os
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from psycopg.types.json import Jsonb
from sqlalchemy import Connection, Engine, column, create_engine, make_url, table
from sqlalchemy.dialects.postgresql import insert


def get_engine() -> Engine:
    # Paksa driver psycopg: URL "postgresql://" polos akan memilih psycopg2 yang tidak terpasang.
    url = make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql+psycopg")
    return create_engine(url)


def upsert(
    conn: Connection,
    table_name: str,
    rows: Sequence[Mapping[str, Any]],
    conflict_columns: Iterable[str],
    batch_size: int = 1000,
) -> int:
    """Insert rows, atau update baris lama kalau conflict_columns sudah ada.

    Semua baris harus punya kolom yang sama. Commit diserahkan ke pemanggil.
    """
    if not rows:
        return 0

    columns = list(rows[0])
    conflict_columns = list(conflict_columns)
    stmt = insert(table(table_name, *(column(name) for name in columns)))
    stmt = stmt.on_conflict_do_update(
        index_elements=conflict_columns,
        set_={name: stmt.excluded[name] for name in columns if name not in conflict_columns},
    )

    # Kolom di atas tanpa tipe, jadi nilai jsonb harus dibungkus agar bisa dikirim psycopg.
    params = [
        {k: Jsonb(v) if isinstance(v, dict | list) else v for k, v in row.items()} for row in rows
    ]
    for start in range(0, len(params), batch_size):
        conn.execute(stmt, params[start : start + batch_size])
    return len(params)
