import logging

from alembic import context

from padamfirst.db import get_engine

logging.basicConfig(level=logging.INFO, format="%(message)s")

with get_engine().connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
