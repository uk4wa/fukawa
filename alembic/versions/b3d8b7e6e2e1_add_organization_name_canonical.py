"""add organization name_canonical

Revision ID: b3d8b7e6e2e1
Revises: 6de5d1104d20
Create Date: 2026-03-23 14:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3d8b7e6e2e1"
down_revision: str | Sequence[str] | None = "6de5d1104d20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "organizations",
        sa.Column("name_canonical", sa.Text(), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE organizations
            SET name_canonical = normalize(
                casefold(normalize(name, NFC) COLLATE "pg_unicode_fast"),
                NFC
            )
            WHERE name_canonical IS NULL
            """
        )
    )

    op.alter_column(
        "organizations",
        "name_canonical",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.drop_constraint(
        op.f("uq_organizations_name"),
        "organizations",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_organizations_name_canonical"),
        "organizations",
        ["name_canonical"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("uq_organizations_name_canonical"),
        "organizations",
        type_="unique",
    )
    op.create_unique_constraint(
        op.f("uq_organizations_name"),
        "organizations",
        ["name"],
    )
    op.drop_column("organizations", "name_canonical")
