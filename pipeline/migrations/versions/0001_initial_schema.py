"""Lima tabel inti dari PRD bagian 8.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _doubles(*names: str) -> list[sa.Column]:
    return [sa.Column(name, sa.Double) for name in names]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # h3_index disimpan sebagai text dari h3-py, jadi skema tidak bergantung pada h3-pg.
    op.create_table(
        "hotspots",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("satellite", sa.Text, nullable=False),
        sa.Column("instrument", sa.Text, nullable=False),
        sa.Column("lat", sa.Double, nullable=False),
        sa.Column("lon", sa.Double, nullable=False),
        sa.Column("acq_datetime", sa.DateTime(timezone=True), nullable=False),
        sa.Column("frp", sa.Double),
        sa.Column("confidence", sa.Text),
        sa.Column("h3_index", sa.Text, nullable=False),
        sa.UniqueConstraint(
            "satellite", "lat", "lon", "acq_datetime", name="uq_hotspots_detection"
        ),
        sa.CheckConstraint(
            "confidence IN ('low', 'nominal', 'high')", name="ck_hotspots_confidence"
        ),
    )
    # Kolom generated supaya geom tidak mungkin berbeda dari lat dan lon.
    op.execute(
        "ALTER TABLE hotspots ADD COLUMN geom geometry(Point, 4326) "
        "GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(lon, lat), 4326)) STORED"
    )
    op.create_index("ix_hotspots_h3_index", "hotspots", ["h3_index"])
    op.create_index("ix_hotspots_acq_datetime", "hotspots", ["acq_datetime"])
    op.create_index("ix_hotspots_geom", "hotspots", ["geom"], postgresql_using="gist")

    op.create_table(
        "cell_static",
        sa.Column("h3_index", sa.Text, primary_key=True),
        *_doubles("peat_pct", "peat_depth_cm"),
        sa.Column("landcover_class", sa.Text),
        *_doubles("pop_density", "dist_road_km", "dist_plantation_km"),
        sa.Column("province", sa.Text),
        sa.Column("regency", sa.Text),
    )

    # Primary key (h3_index, date) sekaligus unique constraint dan index untuk h3_index.
    op.create_table(
        "cell_daily",
        sa.Column("h3_index", sa.Text, primary_key=True),
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("n_hotspots", sa.Integer),
        *_doubles("frp_sum", "frp_max", "conf_mean"),
        sa.Column("persistence_days", sa.Integer),
        sa.Column("growth_24h", sa.Integer),
        *_doubles("wind_speed", "wind_dir", "rain_1d", "rain_7d", "rain_30d"),
        sa.Column("dry_days", sa.Integer),
        *_doubles("temp_max", "rh_min", "soil_moisture", "ffmc", "dmc", "dc", "fwi"),
    )
    op.create_index("ix_cell_daily_date", "cell_daily", ["date"])

    # model_version ikut kunci supaya skor baseline dan LightGBM bisa berdampingan.
    op.create_table(
        "predictions",
        sa.Column("h3_index", sa.Text, primary_key=True),
        sa.Column("date", sa.Date, primary_key=True),
        sa.Column("model_version", sa.Text, primary_key=True),
        *_doubles("p_spread", "impact_score", "fire_score", "priority_score"),
        sa.Column("priority_class", sa.Text),
        sa.Column("confidence_level", sa.Text),
        sa.Column("shap_top", JSONB),
        sa.CheckConstraint(
            "priority_class IN ('merah', 'oranye', 'kuning', 'hijau')",
            name="ck_predictions_priority_class",
        ),
        sa.CheckConstraint(
            "confidence_level IN ('rendah', 'sedang', 'tinggi')",
            name="ck_predictions_confidence_level",
        ),
    )
    op.create_index("ix_predictions_date", "predictions", ["date"])

    op.create_table(
        "ingest_runs",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("rows", sa.Integer),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("error", sa.Text),
    )


def downgrade() -> None:
    # Extension postgis dibiarkan: bisa saja dipakai hal lain di database yang sama.
    for table in ("ingest_runs", "predictions", "cell_daily", "cell_static", "hotspots"):
        op.drop_table(table)
