"""add circle ratings and remove user ratings

Revision ID: 6117586956bc
Revises: d8a74b60405f
Create Date: 2026-06-05 02:29:35.973615

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '6117586956bc'
down_revision = 'd8a74b60405f'
branch_labels = None
depends_on = None


def upgrade():
    # Circle rating changes were applied in d8a74b60405f.
    # This revision intentionally keeps the chain intact without touching
    # unrelated message indexes.
    pass


def downgrade():
    pass
