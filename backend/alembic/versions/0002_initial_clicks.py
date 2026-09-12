"""clicks table

Revision ID: 0002_initial_clicks
Revises: 0001_initial_urls
Create Date: 2026-09-12

"""
import sqlalchemy as sa
from alembic import op

revision = "0002_initial_clicks"
down_revision = "0001_initial_urls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "clicks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "url_id",
            sa.BigInteger(),
            sa.ForeignKey("urls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("referrer", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("browser", sa.String(length=64), nullable=True),
        sa.Column("os", sa.String(length=64), nullable=True),
        sa.Column("device", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "clicks_url_id_clicked_at_idx",
        "clicks",
        ["url_id", "clicked_at"],
    )


def downgrade() -> None:
    op.drop_index("clicks_url_id_clicked_at_idx", table_name="clicks")
    op.drop_table("clicks")