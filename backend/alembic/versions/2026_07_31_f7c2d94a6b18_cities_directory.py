"""cities directory

Revision ID: f7c2d94a6b18
Revises: a8b3c5d71e29
Create Date: 2026-07-31 14:02:51.117204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f7c2d94a6b18'
down_revision: Union[str, None] = 'a8b3c5d71e29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    # Города, уже набранные точками, переезжают в справочник — иначе после
    # выкатки админка показывала бы пустой список при живых ресторанах
    op.execute(
        """
        INSERT INTO cities (name, key)
        SELECT DISTINCT ON (lower(btrim(city))) btrim(city), lower(btrim(city))
        FROM restaurants
        WHERE btrim(city) <> ''
        ORDER BY lower(btrim(city))
        """
    )


def downgrade() -> None:
    op.drop_table('cities')
