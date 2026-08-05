"""osm import staging

Revision ID: 7c4e1f8a2d90
Revises: 3e21c8d47a6b
Create Date: 2026-08-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "7c4e1f8a2d90"
down_revision: Union[str, None] = "3e21c8d47a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "osm_import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("query", sa.String(120), nullable=False),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_osm_import_batches_city_created", "osm_import_batches", ["city", "created_at"])
    op.create_table(
        "osm_import_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("osm_import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("osm_type", sa.String(12), nullable=False),
        sa.Column("osm_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(200)),
        sa.Column("address", sa.String(300), nullable=False),
        sa.Column("lat", sa.Float(), nullable=False),
        sa.Column("lng", sa.Float(), nullable=False),
        sa.Column("duplicate_restaurant_id", sa.Integer(), sa.ForeignKey("restaurants.id", ondelete="SET NULL")),
        sa.Column("imported_restaurant_id", sa.Integer(), sa.ForeignKey("restaurants.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("batch_id", "osm_type", "osm_id", name="uq_osm_import_point_source"),
    )
    op.create_index("ix_osm_import_points_batch", "osm_import_points", ["batch_id"])


def downgrade() -> None:
    op.drop_table("osm_import_points")
    op.drop_table("osm_import_batches")
