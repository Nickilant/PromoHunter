"""regional moderators and per-city promotion scope

Revision ID: e5d2a9b74c31
Revises: c3a71f5b28de
Create Date: 2026-07-30 12:40:11.336204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e5d2a9b74c31'
down_revision: Union[str, None] = 'c3a71f5b28de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


city_mode_enum = sa.Enum('exclude', 'include', name='promotion_city_mode')
city_mode_ref = postgresql.ENUM(
    'exclude', 'include', name='promotion_city_mode', create_type=False
)


def upgrade() -> None:
    bind = op.get_bind()

    # --- новая роль ---
    # PostgreSQL 12+ разрешает ADD VALUE внутри транзакции, если новое
    # значение не используется в этой же транзакции. Мы его только заводим.
    op.execute("ALTER TYPE user_role ADD VALUE IF NOT EXISTS 'moderator' BEFORE 'admin'")

    op.create_table(
        'moderator_cities',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'city'),
    )

    # --- охват акции по городам ---
    city_mode_enum.create(bind, checkfirst=True)
    op.add_column(
        'promotions',
        sa.Column('city_mode', city_mode_ref, server_default='exclude', nullable=False),
    )
    op.create_table(
        'promotion_cities',
        sa.Column('promotion_id', sa.Integer(), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['promotion_id'], ['promotions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('promotion_id', 'city'),
    )

    # --- маршрутизация и журнал заявок ---
    op.add_column(
        'promotion_suggestions', sa.Column('city', sa.String(length=100), nullable=True)
    )
    op.add_column(
        'promotion_suggestions', sa.Column('reviewed_by_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_promotion_suggestions_reviewed_by',
        'promotion_suggestions',
        'users',
        ['reviewed_by_id'],
        ['id'],
        ondelete='SET NULL',
    )
    op.add_column(
        'restaurant_suggestions',
        sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        'fk_restaurant_suggestions_reviewed_by',
        'restaurant_suggestions',
        'users',
        ['reviewed_by_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # Город старым заявкам: у точки — её город, иначе город автора
    op.execute(
        """
        UPDATE promotion_suggestions AS ps
        SET city = COALESCE(
            (SELECT r.city FROM restaurants r WHERE r.id = ps.restaurant_id),
            (SELECT u.city FROM users u WHERE u.id = ps.user_id)
        )
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_restaurant_suggestions_reviewed_by',
        'restaurant_suggestions',
        type_='foreignkey',
    )
    op.drop_column('restaurant_suggestions', 'reviewed_by_id')
    op.drop_constraint(
        'fk_promotion_suggestions_reviewed_by',
        'promotion_suggestions',
        type_='foreignkey',
    )
    op.drop_column('promotion_suggestions', 'reviewed_by_id')
    op.drop_column('promotion_suggestions', 'city')

    op.drop_table('promotion_cities')
    op.drop_column('promotions', 'city_mode')
    city_mode_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_table('moderator_cities')

    # Значение из enum убрать нельзя — пересоздаём тип, предварительно
    # разжаловав модераторов в обычных пользователей
    op.execute("UPDATE users SET role = 'user' WHERE role = 'moderator'")
    op.execute("ALTER TYPE user_role RENAME TO user_role_old")
    op.execute("CREATE TYPE user_role AS ENUM ('user', 'admin')")
    op.execute(
        "ALTER TABLE users ALTER COLUMN role TYPE user_role "
        "USING role::text::user_role"
    )
    op.execute("DROP TYPE user_role_old")
