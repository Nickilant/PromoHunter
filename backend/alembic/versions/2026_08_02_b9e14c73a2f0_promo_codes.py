"""promo codes

Revision ID: b9e14c73a2f0
Revises: f7c2d94a6b18
Create Date: 2026-08-02 11:18:42.905117

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b9e14c73a2f0'
down_revision: Union[str, None] = 'f7c2d94a6b18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'promo_codes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('brand_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('code_key', sa.String(length=64), nullable=False),
        sa.Column('description', sa.String(length=200), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=True),
        sa.Column('is_global', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('author_awarded', sa.Boolean(), server_default='false', nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['brand_id'], ['brands.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('brand_id', 'code_key', name='uq_promo_codes_brand_code'),
    )
    op.create_index(
        'ix_promo_codes_brand_expires', 'promo_codes', ['brand_id', 'expires_at']
    )
    op.create_table(
        'promo_code_cities',
        sa.Column('promo_code_id', sa.Integer(), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['promo_code_id'], ['promo_codes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('promo_code_id', 'city'),
    )
    op.create_table(
        'promo_code_votes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('promo_code_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('worked', sa.Boolean(), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['promo_code_id'], ['promo_codes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_promo_code_votes_code_user', 'promo_code_votes', ['promo_code_id', 'user_id']
    )


def downgrade() -> None:
    op.drop_index('ix_promo_code_votes_code_user', table_name='promo_code_votes')
    op.drop_table('promo_code_votes')
    op.drop_table('promo_code_cities')
    op.drop_index('ix_promo_codes_brand_expires', table_name='promo_codes')
    op.drop_table('promo_codes')
