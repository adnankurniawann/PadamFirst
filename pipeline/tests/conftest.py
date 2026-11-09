from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

# Sengaja tidak memakai DATABASE_URL: test membuat dan menghapus database, jadi hanya boleh
# menyentuh Postgres compose lokal (docker compose up -d --wait db), bukan data dev atau produksi.
SERVER_URL = "postgresql+psycopg://padamfirst:padamfirst@localhost:5433"
TEST_DB = "padamfirst_test"


@pytest.fixture(scope="session")
def alembic_config():
    root = Path(__file__).parent.parent
    config = Config(root / "alembic.ini")
    config.set_main_option("script_location", str(root / "migrations"))
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", f"{SERVER_URL}/{TEST_DB}")
        yield config


@pytest.fixture(scope="session")
def engine(alembic_config):
    admin = create_engine(f"{SERVER_URL}/postgres", isolation_level="AUTOCOMMIT")
    drop = text(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
    with admin.connect() as conn:
        conn.execute(drop)
        conn.execute(text(f"CREATE DATABASE {TEST_DB}"))

    command.upgrade(alembic_config, "head")
    test_engine = create_engine(f"{SERVER_URL}/{TEST_DB}")
    yield test_engine

    test_engine.dispose()
    with admin.connect() as conn:
        conn.execute(drop)
    admin.dispose()


@pytest.fixture
def conn(engine):
    """Koneksi yang di-rollback setelah tiap test, jadi antar test tidak saling mengotori."""
    with engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()
