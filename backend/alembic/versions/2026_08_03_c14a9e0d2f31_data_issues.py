"""data issues

Revision ID: c14a9e0d2f31
Revises: b9e14c73a2f0
Create Date: 2026-08-03
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c14a9e0d2f31"
down_revision: Union[str, None] = "b9e14c73a2f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    issue_status = postgresql.ENUM("pending", "resolved", "rejected", name="issue_status", create_type=False)
    op.execute("DO $$ BEGIN CREATE TYPE issue_status AS ENUM ('pending', 'resolved', 'rejected'); EXCEPTION WHEN duplicate_object THEN NULL; END $$")
    op.create_table(
        "data_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("restaurant_id", sa.Integer(), nullable=False),
        sa.Column("promotion_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("status", issue_status, nullable=False),
        sa.Column("moderator_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["restaurant_id"], ["restaurants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["promotion_id"], ["promotions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_issues_status_created", "data_issues", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_data_issues_status_created", table_name="data_issues")
    op.drop_table("data_issues")
    sa.Enum(name="issue_status").drop(op.get_bind(), checkfirst=True)
