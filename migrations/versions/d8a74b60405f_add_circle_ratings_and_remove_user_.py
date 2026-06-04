"""add circle ratings and remove user reviews

Revision ID: d8a74b60405f
Revises: d111835184f9
Create Date: 2026-06-05 02:24:31.203858

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8a74b60405f'
down_revision = 'd111835184f9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('circle_rating',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('circle_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint('rating BETWEEN 1 AND 5', name='ck_circle_rating_rating_range'),
    sa.ForeignKeyConstraint(['circle_id'], ['circle.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('circle_id', 'user_id', name='uq_circle_rating_circle_user')
    )
    op.create_index(op.f('ix_circle_rating_circle_id'), 'circle_rating', ['circle_id'], unique=False)
    op.create_index(op.f('ix_circle_rating_user_id'), 'circle_rating', ['user_id'], unique=False)

    op.drop_table('user_review')


def downgrade():
    op.create_table('user_review',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('activity_id', sa.Integer(), nullable=False),
    sa.Column('reviewer_id', sa.Integer(), nullable=False),
    sa.Column('reviewee_id', sa.Integer(), nullable=False),
    sa.Column('punctuality_score', sa.Integer(), nullable=False),
    sa.Column('friendliness_score', sa.Integer(), nullable=False),
    sa.Column('communication_score', sa.Integer(), nullable=False),
    sa.Column('reliability_score', sa.Integer(), nullable=False),
    sa.Column('respect_score', sa.Integer(), nullable=False),
    sa.Column('safety_score', sa.Integer(), nullable=False),
    sa.Column('average_score', sa.Float(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.CheckConstraint('communication_score BETWEEN 1 AND 5', name=op.f('ck_user_review_communication_score_range')),
    sa.CheckConstraint('friendliness_score BETWEEN 1 AND 5', name=op.f('ck_user_review_friendliness_score_range')),
    sa.CheckConstraint('punctuality_score BETWEEN 1 AND 5', name=op.f('ck_user_review_punctuality_score_range')),
    sa.CheckConstraint('reliability_score BETWEEN 1 AND 5', name=op.f('ck_user_review_reliability_score_range')),
    sa.CheckConstraint('respect_score BETWEEN 1 AND 5', name=op.f('ck_user_review_respect_score_range')),
    sa.CheckConstraint('safety_score BETWEEN 1 AND 5', name=op.f('ck_user_review_safety_score_range')),
    sa.ForeignKeyConstraint(['activity_id'], ['activity.id'], ),
    sa.ForeignKeyConstraint(['reviewee_id'], ['user.id'], ),
    sa.ForeignKeyConstraint(['reviewer_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('activity_id', 'reviewer_id', 'reviewee_id', name=op.f('uq_user_review_activity_reviewer_reviewee'))
    )
    op.drop_index(op.f('ix_circle_rating_user_id'), table_name='circle_rating')
    op.drop_index(op.f('ix_circle_rating_circle_id'), table_name='circle_rating')
    op.drop_table('circle_rating')
