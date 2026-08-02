"""game mode: factions, receipts, point control

Revision ID: c3a71f5b28de
Revises: 655c65f23748
Create Date: 2026-07-30 09:12:04.118250

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'c3a71f5b28de'
down_revision: Union[str, None] = '655c65f23748'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Тип создаём один раз явно, дальше переиспользуем без повторного CREATE TYPE
faction_enum = sa.Enum('green', 'purple', name='faction')
faction_ref = postgresql.ENUM('green', 'purple', name='faction', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    faction_enum.create(bind, checkfirst=True)

    # --- игровые поля пользователя ---
    op.add_column(
        'users',
        sa.Column('game_mode', sa.Boolean(), server_default='false', nullable=False),
    )
    op.add_column('users', sa.Column('game_asked_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('faction', faction_ref, nullable=True))
    op.add_column(
        'users', sa.Column('faction_joined_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index('ix_users_city_faction', 'users', ['city', 'faction'], unique=False)

    # --- точка: часовой пояс кассы и рабочие часы ---
    op.add_column(
        'restaurants',
        sa.Column('utc_offset_minutes', sa.Integer(), server_default='180', nullable=False),
    )
    op.add_column(
        'restaurants',
        sa.Column('active_hours_mask', sa.Integer(), server_default='0', nullable=False),
    )

    op.add_column(
        'reports',
        sa.Column(
            'is_receipt_verified', sa.Boolean(), server_default='false', nullable=False
        ),
    )

    # --- кассы ---
    op.create_table(
        'fiscal_drives',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('fn', sa.String(length=24), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=True),
        sa.Column('confirmations', sa.Integer(), nullable=False),
        sa.Column('is_bound', sa.Boolean(), nullable=False),
        sa.Column('max_doc_number', sa.Integer(), nullable=False),
        sa.Column('max_doc_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'first_seen_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('bound_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fn'),
    )

    # --- чеки ---
    op.create_table(
        'receipts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('report_id', sa.Integer(), nullable=True),
        sa.Column('fn', sa.String(length=24), nullable=False),
        sa.Column('doc_number', sa.Integer(), nullable=False),
        sa.Column('fp', sa.String(length=24), nullable=False),
        sa.Column('sum_kopeks', sa.Integer(), nullable=False),
        sa.Column('purchased_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('faction', faction_ref, nullable=False),
        sa.Column('strength', sa.Float(), nullable=False),
        sa.Column('raw', sa.String(length=300), nullable=False),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['report_id'], ['reports.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fn', 'doc_number', name='uq_receipt_fn_doc'),
        sa.UniqueConstraint('report_id'),
    )
    op.create_index(
        'ix_receipts_restaurant_created', 'receipts', ['restaurant_id', 'created_at']
    )
    op.create_index('ix_receipts_user_created', 'receipts', ['user_id', 'created_at'])

    # --- состояние борьбы за точку ---
    op.create_table(
        'point_controls',
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('owner_faction', faction_ref, nullable=True),
        sa.Column('green_score', sa.Float(), nullable=False),
        sa.Column('purple_score', sa.Float(), nullable=False),
        sa.Column(
            'score_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('green_progress', sa.Float(), nullable=False),
        sa.Column('purple_progress', sa.Float(), nullable=False),
        sa.Column(
            'progress_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('battle_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('truce_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('captured_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attack_notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('warning_notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('green_receipts', sa.Integer(), nullable=False),
        sa.Column('purple_receipts', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('restaurant_id'),
    )

    # --- журнал исходов ---
    op.create_table(
        'capture_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('faction', faction_ref, nullable=False),
        sa.Column('kind', sa.String(length=8), nullable=False),
        sa.Column('finisher_user_id', sa.Integer(), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(['finisher_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_capture_events_city_created', 'capture_events', ['city', 'created_at']
    )
    op.create_index(
        'ix_capture_events_restaurant_created',
        'capture_events',
        ['restaurant_id', 'created_at'],
    )

    # --- сезонный зачёт ---
    op.create_table(
        'faction_standings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('season', sa.String(length=7), nullable=False),
        sa.Column('faction', faction_ref, nullable=False),
        sa.Column('held_seconds', sa.Float(), nullable=False),
        sa.Column('captures', sa.Integer(), nullable=False),
        sa.Column('defends', sa.Integer(), nullable=False),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('city', 'season', 'faction', name='uq_standing_city_season'),
    )


def downgrade() -> None:
    op.drop_table('faction_standings')
    op.drop_index('ix_capture_events_restaurant_created', table_name='capture_events')
    op.drop_index('ix_capture_events_city_created', table_name='capture_events')
    op.drop_table('capture_events')
    op.drop_table('point_controls')
    op.drop_index('ix_receipts_user_created', table_name='receipts')
    op.drop_index('ix_receipts_restaurant_created', table_name='receipts')
    op.drop_table('receipts')
    op.drop_table('fiscal_drives')
    op.drop_column('reports', 'is_receipt_verified')
    op.drop_column('restaurants', 'active_hours_mask')
    op.drop_column('restaurants', 'utc_offset_minutes')
    op.drop_index('ix_users_city_faction', table_name='users')
    op.drop_column('users', 'faction_joined_at')
    op.drop_column('users', 'faction')
    op.drop_column('users', 'game_asked_at')
    op.drop_column('users', 'game_mode')
    faction_enum.drop(op.get_bind(), checkfirst=True)
