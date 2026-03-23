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
        sa.Column("name_canonical", sa.String(length=64), nullable=True),
    )

    organizations = sa.table(
        "organizations",
        sa.column("id", sa.BigInteger()),
        sa.column("name", sa.String(length=64)),
        sa.column("name_canonical", sa.String(length=64)),
    )

    bind = op.get_bind()
    rows = bind.execute(sa.select(organizations.c.id, organizations.c.name)).mappings()

    for row in rows:
        bind.execute(
            organizations.update()
            .where(organizations.c.id == row["id"])
            .values(name_canonical=row["name"].casefold())
        )

    op.alter_column(
        "organizations",
        "name_canonical",
        existing_type=sa.String(length=64),
        nullable=False,
    )
    op.drop_constraint(op.f("uq_organizations_name"), "organizations", type_="unique")
    op.create_unique_constraint(
        "uq_organizations_name_canonical",
        "organizations",
        ["name_canonical"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_organizations_name_canonical", "organizations", type_="unique")
    op.create_unique_constraint(
        op.f("uq_organizations_name"),
        "organizations",
        ["name"],
    )
    op.drop_column("organizations", "name_canonical")
