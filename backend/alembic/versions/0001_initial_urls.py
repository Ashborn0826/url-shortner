"""initial urls table

Revision ID: 0001_initial_urls
Revises:
Create Date: 2026-09-12

"""
import sqlalchemy as sa
from alembic import op

revision = "0001_initial_urls"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "urls",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("short_code", sa.String(length=32), nullable=False, unique=True),
        sa.Column("long_url", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "is_custom",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_index(
        "urls_short_code_idx", "urls", ["short_code"], unique=True
    )


def downgrade() -> None:
    op.drop_index("urls_short_code_idx", table_name="urls")
    op.drop_table("urls")