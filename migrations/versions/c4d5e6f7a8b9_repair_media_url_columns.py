"""repair media url columns

Revision ID: c4d5e6f7a8b9
Revises: b2c6f7e8a9d0
Create Date: 2026-06-04 03:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = "c4d5e6f7a8b9"
down_revision = "b2c6f7e8a9d0"
branch_labels = None
depends_on = None


MEDIA_COLUMNS = (
    ("direct_message", "image_path", "image_url", sa.String(length=255), True),
    (
        "merchant_verification",
        "document_path",
        "document_url",
        sa.String(length=255),
        True,
    ),
    ("post_image", "image_path", "image_url", sa.String(length=255), False),
    ("comment_image", "image_path", "image_url", sa.String(length=255), False),
)


def _column_names(table_name):
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def _copy_missing_values(table_name, source_column, target_column):
    op.execute(
        text(
            f'UPDATE "{table_name}" '
            f'SET "{target_column}" = "{source_column}" '
            f'WHERE "{target_column}" IS NULL AND "{source_column}" IS NOT NULL'
        )
    )


def _rename_or_repair_column(table_name, old_column, new_column, column_type, nullable):
    columns = _column_names(table_name)
    if new_column in columns and old_column in columns:
        _copy_missing_values(table_name, old_column, new_column)
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_column(old_column)
        return
    if new_column in columns:
        return
    if old_column in columns:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.alter_column(
                old_column,
                existing_type=column_type,
                new_column_name=new_column,
                existing_nullable=nullable,
            )
        return
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.add_column(sa.Column(new_column, column_type, nullable=True))


def upgrade():
    for table_name, old_column, new_column, column_type, nullable in MEDIA_COLUMNS:
        _rename_or_repair_column(
            table_name, old_column, new_column, column_type, nullable
        )


def downgrade():
    for table_name, old_column, new_column, column_type, nullable in reversed(MEDIA_COLUMNS):
        _rename_or_repair_column(
            table_name, new_column, old_column, column_type, nullable
        )
