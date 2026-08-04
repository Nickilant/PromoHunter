"""brand visibility

Revision ID: 3e21c8d47a6b
Revises: c14a9e0d2f31
Create Date: 2026-08-04
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "3e21c8d47a6b"
down_revision: Union[str, None] = "c14a9e0d2f31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Существующие бренды остаются опубликованными после выкладки.
    op.add_column(
        "brands",
        sa.Column("is_public", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("brands", "is_public")
