"""make org name_canonical generated

Revision ID: cf9d2b1a7e10
Revises: b3d8b7e6e2e1
Create Date: 2026-03-25 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "cf9d2b1a7e10"
down_revision: str | Sequence[str] | None = "b3d8b7e6e2e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(
        op.f("uq_organizations_name_canonical"),
        "organizations",
        type_="unique",
    )
    op.drop_column("organizations", "name_canonical")
    op.add_column(
        "organizations",
        sa.Column(
            "name_canonical",
            sa.String(length=64),
            sa.Computed("normalize(casefold(normalize(name, NFC)), NFC)", persisted=True),
            nullable=False,
        ),
    )
    op.create_unique_constraint(
        op.f("uq_organizations_name_canonical"),
        "organizations",
        ["name_canonical"],
    )

    op.drop_constraint(
        op.f("ck_organizations_name_min_len"),
        "organizations",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_organizations_name_trimmed"),
        "organizations",
        "name = btrim(name)",
    )
    op.create_check_constraint(
        op.f("ck_organizations_name_nfc_normalized"),
        "organizations",
        "name IS NFC NORMALIZED",
    )
    op.create_check_constraint(
        op.f("ck_organizations_name_min_len"),
        "organizations",
        "char_length(name) >= 3",
    )
    op.create_check_constraint(
        op.f("ck_organizations_name_casefold_max_len"),
        "organizations",
        "char_length(normalize(casefold(normalize(name, NFC)), NFC)) <= 64",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        op.f("ck_organizations_name_casefold_max_len"),
        "organizations",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_organizations_name_nfc_normalized"),
        "organizations",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_organizations_name_trimmed"),
        "organizations",
        type_="check",
    )
    op.drop_constraint(
        op.f("ck_organizations_name_min_len"),
        "organizations",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_organizations_name_min_len"),
        "organizations",
        "char_length(trim(name)) >= 3",
    )

    op.drop_constraint(
        op.f("uq_organizations_name_canonical"),
        "organizations",
        type_="unique",
    )
    op.drop_column("organizations", "name_canonical")
    op.add_column(
        "organizations",
        sa.Column("name_canonical", sa.String(length=64), nullable=False),
    )
    op.execute(
        sa.text(
            """
            UPDATE organizations
            SET name_canonical = normalize(casefold(normalize(name, NFC)), NFC)
            """
        )
    )
    op.create_unique_constraint(
        op.f("uq_organizations_name_canonical"),
        "organizations",
        ["name_canonical"],
    )
