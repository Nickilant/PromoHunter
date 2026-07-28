"""city: restaurants.city + users.city

Revision ID: b7e91d3c40a2
Revises: a1c4f2d90b11
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7e91d3c40a2"
down_revision: Union[str, None] = "a1c4f2d90b11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "restaurants",
        sa.Column(
            "city",
            sa.String(100),
            nullable=False,
            server_default="Санкт-Петербург",
        ),
    )
    op.create_index("ix_restaurants_city", "restaurants", ["city"])
    op.add_column("users", sa.Column("city", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "city")
    op.drop_index("ix_restaurants_city", table_name="restaurants")
    op.drop_column("restaurants", "city")
