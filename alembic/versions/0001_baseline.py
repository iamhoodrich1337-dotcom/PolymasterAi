"""baseline: schema already created by the application (Base.metadata.create_all)

Revision ID: 0001
Revises:
Create Date: 2026-11-27
"""
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing tables are left untouched. All future schema changes go into new revisions after this one.
    pass


def downgrade() -> None:
    pass
