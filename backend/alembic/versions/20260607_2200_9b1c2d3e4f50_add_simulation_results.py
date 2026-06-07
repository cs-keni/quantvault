"""add simulation_results table

Revision ID: 9b1c2d3e4f50
Revises: 30594d39da38
Create Date: 2026-06-07 22:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "9b1c2d3e4f50"
down_revision: str | None = "30594d39da38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    sa.Enum("PENDING", "SUCCESS", "FAILURE", name="simulation_status").create(
        op.get_bind(), checkfirst=True
    )
    simulation_status = postgresql.ENUM(
        "PENDING", "SUCCESS", "FAILURE", name="simulation_status", create_type=False
    )

    op.create_table(
        "simulation_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("portfolio_id", sa.UUID(), nullable=True),
        sa.Column("status", simulation_status, nullable=False),
        sa.Column("tickers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False),
        sa.Column("initial_investment", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("years", sa.Integer(), nullable=False),
        sa.Column("n_simulations", sa.Integer(), nullable=False),
        sa.Column("annual_contribution", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.Column("task_id", sa.String(length=255), nullable=True),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error", sa.String(length=2000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_simulation_results_portfolio_id"),
        "simulation_results",
        ["portfolio_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_simulation_results_user_id"),
        "simulation_results",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_simulation_results_user_id"), table_name="simulation_results")
    op.drop_index(op.f("ix_simulation_results_portfolio_id"), table_name="simulation_results")
    op.drop_table("simulation_results")
    sa.Enum(name="simulation_status").drop(op.get_bind(), checkfirst=True)
