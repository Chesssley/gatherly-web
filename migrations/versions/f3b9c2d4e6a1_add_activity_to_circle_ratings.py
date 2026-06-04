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


def upgrade():
    with op.batch_alter_table("circle_rating") as batch_op:
        batch_op.add_column(sa.Column("activity_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_circle_rating_activity_id", ["activity_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_circle_rating_activity_id_activity",
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
    with op.batch_alter_table("circle_rating") as batch_op:
        batch_op.drop_constraint("fk_circle_rating_activity_id_activity", type_="foreignkey")
        batch_op.drop_index("ix_circle_rating_activity_id")
        batch_op.drop_column("activity_id")
