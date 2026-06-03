"""rename media path fields to url

Revision ID: b2c6f7e8a9d0
Revises: 910bb336a36d
Create Date: 2026-06-04 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c6f7e8a9d0"
down_revision = "910bb336a36d"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("direct_message", schema=None) as batch_op:
        batch_op.alter_column(
            "image_path",
            existing_type=sa.String(length=255),
            new_column_name="image_url",
            existing_nullable=True,
        )

    with op.batch_alter_table("merchant_verification", schema=None) as batch_op:
        batch_op.alter_column(
            "document_path",
            existing_type=sa.String(length=255),
            new_column_name="document_url",
            existing_nullable=True,
        )

    with op.batch_alter_table("post_image", schema=None) as batch_op:
        batch_op.alter_column(
            "image_path",
            existing_type=sa.String(length=255),
            new_column_name="image_url",
            existing_nullable=False,
        )

    with op.batch_alter_table("comment_image", schema=None) as batch_op:
        batch_op.alter_column(
            "image_path",
            existing_type=sa.String(length=255),
            new_column_name="image_url",
            existing_nullable=False,
        )


def downgrade():
    with op.batch_alter_table("comment_image", schema=None) as batch_op:
        batch_op.alter_column(
            "image_url",
            existing_type=sa.String(length=255),
            new_column_name="image_path",
            existing_nullable=False,
        )

    with op.batch_alter_table("post_image", schema=None) as batch_op:
        batch_op.alter_column(
            "image_url",
            existing_type=sa.String(length=255),
            new_column_name="image_path",
            existing_nullable=False,
        )

    with op.batch_alter_table("merchant_verification", schema=None) as batch_op:
        batch_op.alter_column(
            "document_url",
            existing_type=sa.String(length=255),
            new_column_name="document_path",
            existing_nullable=True,
        )

    with op.batch_alter_table("direct_message", schema=None) as batch_op:
        batch_op.alter_column(
            "image_url",
            existing_type=sa.String(length=255),
            new_column_name="image_path",
            existing_nullable=True,
        )
