"""password change from profile

Revision ID: a8b3c5d71e29
Revises: d41f6a2b9c07
Create Date: 2026-07-31 09:24:17.883014

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a8b3c5d71e29'
down_revision: Union[str, None] = 'd41f6a2b9c07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Пароля может не быть: аккаунт заведён входом через Telegram-контакт
    op.alter_column('users', 'password_hash', existing_type=sa.String(255), nullable=True)
    op.add_column(
        'users',
        sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('users', 'password_changed_at')
    # Аккаунты без пароля обратно не сходятся — им нужен непустой хеш;
    # ставим заведомо невалидный, войти по нему нельзя
    op.execute("UPDATE users SET password_hash = '!' WHERE password_hash IS NULL")
    op.alter_column('users', 'password_hash', existing_type=sa.String(255), nullable=False)
