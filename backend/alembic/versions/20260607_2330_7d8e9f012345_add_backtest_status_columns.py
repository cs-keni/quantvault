"""add backtest status and audit columns

Revision ID: 7d8e9f012345
Revises: 9b1c2d3e4f50
Create Date: 2026-06-07 23:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "7d8e9f012345"
down_revision: str | None = "9b1c2d3e4f50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    sa.Enum("PENDING", "SUCCESS", "FAILURE", name="backtest_status").create(
        op.get_bind(), checkfirst=True
    )
    backtest_status = postgresql.ENUM(
        "PENDING", "SUCCESS", "FAILURE", name="backtest_status", create_type=False
    )

    op.add_column("backtest_results", sa.Column("user_id", sa.UUID(), nullable=True))
    op.add_column("backtest_results", sa.Column("status", backtest_status, nullable=True))
    op.add_column("backtest_results", sa.Column("task_id", sa.String(length=255), nullable=True))
    op.add_column("backtest_results", sa.Column("error", sa.String(length=2000), nullable=True))
    op.add_column(
        "backtest_results",
        sa.Column("tickers", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "backtest_results",
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    op.execute(
        """
        UPDATE backtest_results br
        SET user_id = p.user_id
        FROM portfolios p
        WHERE br.portfolio_id = p.id
        """
    )
    op.execute("UPDATE backtest_results SET status = 'SUCCESS' WHERE status IS NULL")
    op.execute("UPDATE backtest_results SET tickers = '[]'::jsonb WHERE tickers IS NULL")
    op.execute("UPDATE backtest_results SET weights = '[]'::jsonb WHERE weights IS NULL")

    op.alter_column("backtest_results", "user_id", nullable=False)
    op.alter_column("backtest_results", "status", nullable=False)
    op.alter_column("backtest_results", "tickers", nullable=False)
    op.alter_column("backtest_results", "weights", nullable=False)

    op.alter_column("backtest_results", "tearsheet", nullable=True)
    op.alter_column("backtest_results", "daily_returns", nullable=True)
    op.alter_column("backtest_results", "equity_curve", nullable=True)

    op.create_foreign_key(
        op.f("fk_backtest_results_user_id_users"),
        "backtest_results",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        op.f("ix_backtest_results_user_id"), "backtest_results", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_backtest_results_user_id"), table_name="backtest_results")
    op.drop_constraint(
        op.f("fk_backtest_results_user_id_users"), "backtest_results", type_="foreignkey"
    )
    op.alter_column("backtest_results", "equity_curve", nullable=False)
    op.alter_column("backtest_results", "daily_returns", nullable=False)
    op.alter_column("backtest_results", "tearsheet", nullable=False)
    op.drop_column("backtest_results", "weights")
    op.drop_column("backtest_results", "tickers")
    op.drop_column("backtest_results", "error")
    op.drop_column("backtest_results", "task_id")
    op.drop_column("backtest_results", "status")
    op.drop_column("backtest_results", "user_id")
    sa.Enum(name="backtest_status").drop(op.get_bind(), checkfirst=True)
