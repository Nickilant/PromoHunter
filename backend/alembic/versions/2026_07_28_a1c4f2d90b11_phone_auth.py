"""phone auth: email -> phone, is_phone_verified

Revision ID: a1c4f2d90b11
Revises: 9b302f68dc73
Create Date: 2026-07-28

Авторизация переведена с email на номер телефона. Старые аккаунты после
этой миграции по номеру не войдут (в колонке останется бывший email,
обрезанный до 20 символов) — для локальной разработки проще `make reset`.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1c4f2d90b11"
down_revision: Union[str, None] = "9b302f68dc73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_phone_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.alter_column("users", "email", new_column_name="phone")
    # left(): чтобы миграция не падала на длинных email в существующих базах
    op.execute("UPDATE users SET phone = left(phone, 20)")
    op.alter_column(
        "users",
        "phone",
        type_=sa.String(20),
        existing_type=sa.String(255),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "users",
        "phone",
        type_=sa.String(255),
        existing_type=sa.String(20),
        existing_nullable=False,
    )
    op.alter_column("users", "phone", new_column_name="email")
    op.drop_column("users", "is_phone_verified")
