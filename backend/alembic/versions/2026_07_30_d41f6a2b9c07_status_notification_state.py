"""status notification state

Revision ID: d41f6a2b9c07
Revises: e5d2a9b74c31
Create Date: 2026-07-30 12:10:44.512038

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd41f6a2b9c07'
down_revision: Union[str, None] = 'e5d2a9b74c31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'item_status_states', sa.Column('notified', sa.String(length=16), nullable=True)
    )
    op.add_column(
        'item_status_states',
        sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
    )
    # Уже показанный устойчивый статус считаем сообщённым: иначе после
    # выкатки каждая живая пара «точка × товар» разошлёт уведомление заново.
    op.execute(
        "UPDATE item_status_states "
        "SET notified = stable, notified_at = updated_at "
        "WHERE stable IN ('available', 'unavailable')"
    )


def downgrade() -> None:
    op.drop_column('item_status_states', 'notified_at')
    op.drop_column('item_status_states', 'notified')
