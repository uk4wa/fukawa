"""add org check constraint

Revision ID: 6de5d1104d20
Revises: 44e85e0f2ce8
Create Date: 2026-03-16 20:16:11.719152

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6de5d1104d20"
down_revision: str | Sequence[str] | None = "44e85e0f2ce8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "organizations",
        "name",
        existing_type=sa.VARCHAR(length=320),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
    op.create_check_constraint(
        op.f("ck_organizations_name_min_len"),
        "organizations",
        "char_length(trim(name)) >= 3",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("ck_organizations_name_min_len"),
        "organizations",
        type_="check",
    )
    op.alter_column(
        "organizations",
        "name",
        existing_type=sa.String(length=64),
        type_=sa.VARCHAR(length=320),
        existing_nullable=False,
    )
