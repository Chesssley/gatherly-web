from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text


db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    nickname = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    email_verified_at = db.Column(db.DateTime)
    password = db.Column(db.String(255), nullable=False)
    avatar = db.Column(db.String(255))
    bio = db.Column(db.Text)
    interests = db.Column(db.Text)
    city = db.Column(db.String(80))
    role = db.Column(db.String(20), default="user", nullable=False)
    trust_score = db.Column(db.Integer, default=100, nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False)
    banned_at = db.Column(db.DateTime, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    activities = db.relationship("Activity", back_populates="organizer")
    registrations = db.relationship("Registration", back_populates="user")
    activity_favorites = db.relationship(
        "ActivityFavorite",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    posts = db.relationship("Post", back_populates="user")
    reviews = db.relationship("Review", back_populates="user")
    activity_reviews = db.relationship("ActivityReview", back_populates="reviewer")
    given_user_reviews = db.relationship(
        "UserReview",
        foreign_keys="UserReview.reviewer_id",
        back_populates="reviewer",
    )
    received_user_reviews = db.relationship(
        "UserReview",
        foreign_keys="UserReview.reviewee_id",
        back_populates="reviewee",
    )
    trust_score_logs = db.relationship(
        "TrustScoreLog",
        foreign_keys="TrustScoreLog.user_id",
        back_populates="user",
    )
    circle_memberships = db.relationship("CircleMember", back_populates="user")
    comments = db.relationship("Comment", back_populates="author")
    interactions = db.relationship("Interaction", back_populates="user")
    profile_visibility = db.relationship(
        "ProfileVisibility",
        back_populates="user",
        uselist=False,
    )
    admin_logs = db.relationship(
        "AdminLog",
        foreign_keys="AdminLog.admin_id",
        back_populates="admin",
    )
    email_verification_codes = db.relationship(
        "EmailVerificationCode",
        back_populates="user",
    )
    notifications = db.relationship("Notification", back_populates="recipient")
    sent_messages = db.relationship(
        "DirectMessage",
        foreign_keys="DirectMessage.sender_id",
        back_populates="sender",
    )
    received_messages = db.relationship(
        "DirectMessage",
        foreign_keys="DirectMessage.recipient_id",
        back_populates="recipient",
    )
    merchant_verifications = db.relationship(
        "MerchantVerification",
        foreign_keys="MerchantVerification.user_id",
        back_populates="user",
    )
    reviewed_merchant_verifications = db.relationship(
        "MerchantVerification",
        foreign_keys="MerchantVerification.reviewer_id",
        back_populates="reviewer",
    )


def ensure_user_account_schema():
    if db.engine.dialect.name != "sqlite":
        return

    rows = db.session.execute(text('PRAGMA table_info("user")')).fetchall()
    existing_columns = {row[1] for row in rows}
    statements = []
    if rows and "nickname" not in existing_columns:
        statements.append('ALTER TABLE "user" ADD COLUMN nickname VARCHAR(80)')
    if rows and "deleted_at" not in existing_columns:
        statements.append('ALTER TABLE "user" ADD COLUMN deleted_at DATETIME')
    if rows and "bio" not in existing_columns:
        statements.append('ALTER TABLE "user" ADD COLUMN bio TEXT')
    if rows and "city" not in existing_columns:
        statements.append('ALTER TABLE "user" ADD COLUMN city VARCHAR(80)')
    if rows and "email_verified_at" not in existing_columns:
        statements.append('ALTER TABLE "user" ADD COLUMN email_verified_at DATETIME')

    for statement in statements:
        db.session.execute(text(statement))
    if statements:
        db.session.commit()


def get_user_display_name(user):
    if user.status == "deleted":
        return "已注销用户"
    return user.nickname or user.username


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    detail = db.Column(db.Text)
    city = db.Column(db.String(80))
    location = db.Column(db.String(255))
    start_time = db.Column(db.DateTime)
    max_participants = db.Column(db.Integer)
    initial_participants = db.Column(db.Integer, default=0, nullable=False)
    image = db.Column(db.String(255))
    fee = db.Column(db.Float, default=0, nullable=False)
    tags = db.Column(db.Text)
    status = db.Column(db.String(20), default="open", nullable=False)
    cancel_reason = db.Column(db.Text)
    cancelled_at = db.Column(db.DateTime)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    organizer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    preparation = db.Column(db.Text)  # 活动准备事项

    organizer = db.relationship("User", back_populates="activities")
    registrations = db.relationship("Registration", back_populates="activity")
    favorites = db.relationship(
        "ActivityFavorite",
        back_populates="activity",
        cascade="all, delete-orphan",
    )
    reviews = db.relationship("Review", back_populates="activity")
    activity_reviews = db.relationship("ActivityReview", back_populates="activity")
    user_reviews = db.relationship("UserReview", back_populates="activity")
    comments = db.relationship("Comment", back_populates="activity")


def ensure_activity_schema():
    if db.engine.dialect.name != "sqlite":
        return

    rows = db.session.execute(text("PRAGMA table_info(activity)")).fetchall()
    existing_columns = {row[1] for row in rows}
    statements = []
    if rows and "detail" not in existing_columns:
        statements.append("ALTER TABLE activity ADD COLUMN detail TEXT")
    if rows and "city" not in existing_columns:
        statements.append("ALTER TABLE activity ADD COLUMN city VARCHAR(80)")
    if rows and "initial_participants" not in existing_columns:
        statements.append(
            "ALTER TABLE activity ADD COLUMN initial_participants INTEGER NOT NULL DEFAULT 0"
        )
    if rows and "tags" not in existing_columns:
        statements.append("ALTER TABLE activity ADD COLUMN tags TEXT")
    if rows and "status" not in existing_columns:
        statements.append(
            "ALTER TABLE activity ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'open'"
        )
    if rows and "cancel_reason" not in existing_columns:
        statements.append("ALTER TABLE activity ADD COLUMN cancel_reason TEXT")
    if rows and "cancelled_at" not in existing_columns:
        statements.append("ALTER TABLE activity ADD COLUMN cancelled_at DATETIME")
    if rows and "is_featured" not in existing_columns:
        statements.append(
            "ALTER TABLE activity ADD COLUMN is_featured BOOLEAN NOT NULL DEFAULT 0"
        )

    for statement in statements:
        db.session.execute(text(statement))
    if statements:
        db.session.commit()


class Registration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    status = db.Column(db.String(20), default="registered", nullable=False)
    cancel_reason = db.Column(db.Text)
    cancelled_at = db.Column(db.DateTime)
    register_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="registrations")
    activity = db.relationship("Activity", back_populates="registrations")


def ensure_registration_schema():
    if db.engine.dialect.name != "sqlite":
        return

    rows = db.session.execute(text("PRAGMA table_info(registration)")).fetchall()
    existing_columns = {row[1] for row in rows}
    statements = []
    if rows and "status" not in existing_columns:
        statements.append(
            "ALTER TABLE registration ADD COLUMN status VARCHAR(20) "
            "NOT NULL DEFAULT 'registered'"
        )
    if rows and "cancel_reason" not in existing_columns:
        statements.append("ALTER TABLE registration ADD COLUMN cancel_reason TEXT")
    if rows and "cancelled_at" not in existing_columns:
        statements.append("ALTER TABLE registration ADD COLUMN cancelled_at DATETIME")

    for statement in statements:
        db.session.execute(text(statement))
    if statements:
        db.session.commit()


class EmailVerificationCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    email = db.Column(db.String(120), nullable=False, index=True)
    code = db.Column(db.String(20), nullable=False)
    purpose = db.Column(db.String(30), default="register", nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="email_verification_codes")


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text)
    related_type = db.Column(db.String(50))
    related_id = db.Column(db.Integer)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    recipient = db.relationship("User", back_populates="notifications")


class DirectMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    sender = db.relationship(
        "User",
        foreign_keys=[sender_id],
        back_populates="sent_messages",
    )
    recipient = db.relationship(
        "User",
        foreign_keys=[recipient_id],
        back_populates="received_messages",
    )


class MerchantVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    business_name = db.Column(db.String(120), nullable=False)
    license_number = db.Column(db.String(120))
    document_path = db.Column(db.String(255))
    status = db.Column(db.String(20), default="pending", nullable=False)
    reject_reason = db.Column(db.Text)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    reviewed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="merchant_verifications",
    )
    reviewer = db.relationship(
        "User",
        foreign_keys=[reviewer_id],
        back_populates="reviewed_merchant_verifications",
    )


def ensure_task_foundation_schema():
    ensure_user_account_schema()
    ensure_activity_schema()
    ensure_registration_schema()
    for model in (
        EmailVerificationCode,
        Notification,
        DirectMessage,
        MerchantVerification,
    ):
        model.__table__.create(db.engine, checkfirst=True)


class ActivityFavorite(db.Model):
    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "activity_id",
            name="uq_activity_favorite_user_activity",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="activity_favorites")
    activity = db.relationship("Activity", back_populates="favorites")


class Circle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    tag = db.Column(db.String(50))
    cover_image = db.Column(db.String(255))
    description = db.Column(db.Text)
    announcement = db.Column(db.Text)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    pinned_post_id = db.Column(db.Integer, db.ForeignKey("post.id"))
    is_pinned = db.Column(db.Boolean, default=False, nullable=False)
    pinned_at = db.Column(db.DateTime)
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    initial_member_count = db.Column(db.Integer, default=0, nullable=False)
    member_count = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    posts = db.relationship("Post", back_populates="circle", foreign_keys="Post.circle_id")
    members = db.relationship("CircleMember", back_populates="circle")
    owner = db.relationship("User", foreign_keys=[owner_id])
    pinned_post = db.relationship("Post", foreign_keys=[pinned_post_id], post_update=True)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default="share", nullable=False)
    status = db.Column(db.String(20), default="published", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    circle_id = db.Column(db.Integer, db.ForeignKey("circle.id"), nullable=False)

    user = db.relationship("User", back_populates="posts")
    circle = db.relationship("Circle", back_populates="posts", foreign_keys=[circle_id])
    comments = db.relationship("Comment", back_populates="post")
    images = db.relationship(
        "PostImage",
        back_populates="post",
        cascade="all, delete-orphan",
    )


class PostImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    post = db.relationship("Post", back_populates="images")


class ActivityReview(db.Model):
    __table_args__ = (
        db.UniqueConstraint(
            "activity_id",
            "reviewer_id",
            name="uq_activity_review_activity_reviewer",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    organization_score = db.Column(db.Integer, nullable=False)
    venue_score = db.Column(db.Integer, nullable=False)
    content_score = db.Column(db.Integer, nullable=False)
    value_score = db.Column(db.Integer, nullable=False)
    experience_score = db.Column(db.Integer, nullable=False)
    average_score = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text)
    status = db.Column(db.String(20), default="published", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    activity = db.relationship("Activity", back_populates="activity_reviews")
    reviewer = db.relationship("User", back_populates="activity_reviews")


class UserReview(db.Model):
    __table_args__ = (
        db.UniqueConstraint(
            "activity_id",
            "reviewer_id",
            "reviewee_id",
            name="uq_user_review_activity_reviewer_reviewee",
        ),
        db.CheckConstraint(
            "punctuality_score BETWEEN 1 AND 5",
            name="ck_user_review_punctuality_score_range",
        ),
        db.CheckConstraint(
            "friendliness_score BETWEEN 1 AND 5",
            name="ck_user_review_friendliness_score_range",
        ),
        db.CheckConstraint(
            "communication_score BETWEEN 1 AND 5",
            name="ck_user_review_communication_score_range",
        ),
        db.CheckConstraint(
            "reliability_score BETWEEN 1 AND 5",
            name="ck_user_review_reliability_score_range",
        ),
        db.CheckConstraint(
            "respect_score BETWEEN 1 AND 5",
            name="ck_user_review_respect_score_range",
        ),
        db.CheckConstraint(
            "safety_score BETWEEN 1 AND 5",
            name="ck_user_review_safety_score_range",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    punctuality_score = db.Column(db.Integer, nullable=False)
    friendliness_score = db.Column(db.Integer, nullable=False)
    communication_score = db.Column(db.Integer, nullable=False)
    reliability_score = db.Column(db.Integer, nullable=False)
    respect_score = db.Column(db.Integer, nullable=False)
    safety_score = db.Column(db.Integer, nullable=False)
    average_score = db.Column(db.Float, nullable=False)
    comment = db.Column(db.Text)
    status = db.Column(db.String(20), default="published", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    activity = db.relationship("Activity", back_populates="user_reviews")
    reviewer = db.relationship(
        "User",
        foreign_keys=[reviewer_id],
        back_populates="given_user_reviews",
    )
    reviewee = db.relationship(
        "User",
        foreign_keys=[reviewee_id],
        back_populates="received_user_reviews",
    )


class TrustScoreLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    changed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    change_type = db.Column(db.String(50), nullable=False)
    delta = db.Column(db.Integer, nullable=False)
    score_before = db.Column(db.Integer, nullable=False)
    score_after = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.Text)
    related_type = db.Column(db.String(50))
    related_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship(
        "User",
        foreign_keys=[user_id],
        back_populates="trust_score_logs",
    )
    changed_by = db.relationship("User", foreign_keys=[changed_by_id])


class CircleMember(db.Model):
    __table_args__ = (
        db.UniqueConstraint("circle_id", "user_id", name="uq_circle_member_circle_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    circle_id = db.Column(db.Integer, db.ForeignKey("circle.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    role = db.Column(db.String(20), default="member", nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    circle = db.relationship("Circle", back_populates="members")
    user = db.relationship("User", back_populates="circle_memberships")


class Comment(db.Model):
    __table_args__ = (
        db.CheckConstraint(
            "(activity_id IS NOT NULL AND post_id IS NULL) OR "
            "(activity_id IS NULL AND post_id IS NOT NULL)",
            name="ck_comment_single_target",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"))
    post_id = db.Column(db.Integer, db.ForeignKey("post.id"))
    parent_id = db.Column(db.Integer, db.ForeignKey("comment.id"))
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="published", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    author = db.relationship("User", back_populates="comments")
    activity = db.relationship("Activity", back_populates="comments")
    post = db.relationship("Post", back_populates="comments")
    parent = db.relationship("Comment", remote_side=[id], backref="replies")
    images = db.relationship(
        "CommentImage",
        back_populates="comment",
        cascade="all, delete-orphan",
    )


class CommentImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey("comment.id"), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    comment = db.relationship("Comment", back_populates="images")


class Interaction(db.Model):
    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "target_type",
            "target_id",
            "action_type",
            name="uq_interaction_user_target_action",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    target_type = db.Column(db.String(30), nullable=False)
    target_id = db.Column(db.Integer, nullable=False)
    action_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="interactions")


class ProfileVisibility(db.Model):
    __table_args__ = (
        db.UniqueConstraint("user_id", name="uq_profile_visibility_user"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    profile_scope = db.Column(db.String(20), default="public", nullable=False)
    activity_scope = db.Column(db.String(20), default="public", nullable=False)
    circle_scope = db.Column(db.String(20), default="public", nullable=False)
    review_scope = db.Column(db.String(20), default="members", nullable=False)
    trust_score_scope = db.Column(db.String(20), default="private", nullable=False)
    show_interests = db.Column(db.Boolean, default=True, nullable=False)
    show_interactions = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = db.relationship("User", back_populates="profile_visibility")


class AdminLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    action = db.Column(db.String(80), nullable=False)
    target_type = db.Column(db.String(50), nullable=False)
    target_id = db.Column(db.Integer)
    detail = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    admin = db.relationship(
        "User",
        foreign_keys=[admin_id],
        back_populates="admin_logs",
    )


# Compatibility model: current activity routes still use Review in older flows.
# Keep it until route and template code migrate to ActivityReview/UserReview.
class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    activity = db.relationship("Activity", back_populates="reviews")
    user = db.relationship("User", back_populates="reviews")


circles = [
    {
        "id": 1,
        "name": "示例圈子名称",
        "tag": "示例标签",
        "summary": "待补充圈子简介",
        "members": 0,
    }
]
