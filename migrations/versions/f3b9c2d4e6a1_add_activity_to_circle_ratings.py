"""add activity to circle ratings

Revision ID: f3b9c2d4e6a1
Revises: 6117586956bc
Create Date: 2026-06-05 06:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f3b9c2d4e6a1"
down_revision = "6117586956bc"
branch_labels = None
depends_on = None


def _has_column(table_name, column_name):
    inspector = sa.inspect(op.get_bind())
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def _has_index(table_name, index_name):
    inspector = sa.inspect(op.get_bind())
    return index_name in {index["name"] for index in inspector.get_indexes(table_name)}


def _has_foreign_key(table_name, foreign_key_name):
    inspector = sa.inspect(op.get_bind())
    return foreign_key_name in {
        foreign_key["name"] for foreign_key in inspector.get_foreign_keys(table_name)
    }


def upgrade():
    bind = op.get_bind()
    has_activity_id = _has_column("circle_rating", "activity_id")
    has_activity_index = _has_index("circle_rating", "ix_circle_rating_activity_id")
    has_activity_foreign_key = _has_foreign_key(
        "circle_rating",
        "fk_circle_rating_activity_id_activity",
    )

    if not has_activity_id:
        with op.batch_alter_table("circle_rating") as batch_op:
            batch_op.add_column(sa.Column("activity_id", sa.Integer(), nullable=True))
            if not has_activity_index:
                batch_op.create_index("ix_circle_rating_activity_id", ["activity_id"], unique=False)
            if not has_activity_foreign_key:
                batch_op.create_foreign_key(
                    "fk_circle_rating_activity_id_activity",
                    "activity",
                    ["activity_id"],
                    ["id"],
                )
    else:
        if not has_activity_index:
            op.create_index("ix_circle_rating_activity_id", "circle_rating", ["activity_id"])
        if bind.dialect.name != "sqlite" and not has_activity_foreign_key:
            op.create_foreign_key(
                "fk_circle_rating_activity_id_activity",
                "circle_rating",
                "activity",
                ["activity_id"],
                ["id"],
            )

    op.execute(
        """
        UPDATE circle_rating
        SET activity_id = (
            SELECT activity.id
            FROM registration
            JOIN activity ON activity.id = registration.activity_id
            WHERE registration.user_id = circle_rating.user_id
              AND registration.status != 'cancelled'
              AND activity.circle_id = circle_rating.circle_id
              AND activity.status != 'cancelled'
              AND activity.start_time IS NOT NULL
              AND activity.start_time <= circle_rating.updated_at
            ORDER BY activity.start_time DESC, activity.id DESC
            LIMIT 1
        )
        WHERE activity_id IS NULL
        """
    )


def downgrade():
    has_activity_id = _has_column("circle_rating", "activity_id")
    has_activity_index = _has_index("circle_rating", "ix_circle_rating_activity_id")
    has_activity_foreign_key = _has_foreign_key(
        "circle_rating",
        "fk_circle_rating_activity_id_activity",
    )

    if has_activity_id:
        with op.batch_alter_table("circle_rating") as batch_op:
            if has_activity_foreign_key:
                batch_op.drop_constraint("fk_circle_rating_activity_id_activity", type_="foreignkey")
            if has_activity_index:
                batch_op.drop_index("ix_circle_rating_activity_id")
            batch_op.drop_column("activity_id")
