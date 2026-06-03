from datetime import datetime, timedelta

from flask import current_app, has_app_context
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash


db = SQLAlchemy()
PASSWORD_HASH_PREFIXES = ("scrypt:", "pbkdf2:", "argon2:", "sha256$", "sha512$")
LEGACY_PLAINTEXT_PASSWORD_MAX_LENGTH = 59
_SCHEMA_HELPER_SKIP_WARNED = set()


def is_sqlite_schema_fallback():
    return db.engine.dialect.name == "sqlite"


def skip_non_sqlite_schema_helper(helper_name):
    if is_sqlite_schema_fallback():
        return False
    if helper_name not in _SCHEMA_HELPER_SKIP_WARNED:
        _SCHEMA_HELPER_SKIP_WARNED.add(helper_name)
        if has_app_context():
            current_app.logger.warning(
                "%s skipped for %s; production schema changes must use "
                "Flask-Migrate/Alembic migrations and `flask db upgrade`.",
                helper_name,
                db.engine.dialect.name,
            )
    return True


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    nickname = db.Column(db.String(80), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    email_verified_at = db.Column(db.DateTime)
    password_hash = db.Column("password", db.String(255), nullable=False)
    avatar = db.Column(db.String(255))
    bio = db.Column(db.Text)
    interests = db.Column(db.Text)
    city = db.Column(db.String(80))
    nearby_enabled = db.Column(db.Boolean, default=False, nullable=False)
    detected_city = db.Column(db.String(80))
    detected_region = db.Column(db.String(80))
    last_location_detected_at = db.Column(db.DateTime)
    last_ip = db.Column(db.String(45))
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
    following = db.relationship(
        "UserFollow",
        foreign_keys="UserFollow.follower_id",
        back_populates="follower",
        cascade="all, delete-orphan",
    )
    followers = db.relationship(
        "UserFollow",
        foreign_keys="UserFollow.followed_id",
        back_populates="followed",
        cascade="all, delete-orphan",
    )
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

    @property
    def password(self):
        return self.password_hash

    @password.setter
    def password(self, value):
        self.password_hash = value


def ensure_user_account_schema():
    # Legacy SQLite fallback only; production PostgreSQL schema is managed by migrations.
    if skip_non_sqlite_schema_helper("ensure_user_account_schema"):
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
    if rows and "nearby_enabled" not in existing_columns:
        statements.append(
            'ALTER TABLE "user" ADD COLUMN nearby_enabled BOOLEAN NOT NULL DEFAULT 0'
        )
    if rows and "detected_city" not in existing_columns:
        statements.append('ALTER TABLE "user" ADD COLUMN detected_city VARCHAR(80)')
    if rows and "detected_region" not in existing_columns:
        statements.append('ALTER TABLE "user" ADD COLUMN detected_region VARCHAR(80)')
    if rows and "last_location_detected_at" not in existing_columns:
        statements.append('ALTER TABLE "user" ADD COLUMN last_location_detected_at DATETIME')
    if rows and "last_ip" not in existing_columns:
        statements.append('ALTER TABLE "user" ADD COLUMN last_ip VARCHAR(45)')
    if rows and "email_verified_at" not in existing_columns:
        statements.append('ALTER TABLE "user" ADD COLUMN email_verified_at DATETIME')

    for statement in statements:
        db.session.execute(text(statement))
    migrated_passwords = 0
    if rows and "password" in existing_columns:
        password_rows = db.session.execute(
            text('SELECT id, password FROM "user" WHERE password IS NOT NULL')
        ).fetchall()
        for user_id, stored_password in password_rows:
            if (
                stored_password
                and not stored_password.startswith(PASSWORD_HASH_PREFIXES)
                and len(stored_password) <= LEGACY_PLAINTEXT_PASSWORD_MAX_LENGTH
            ):
                db.session.execute(
                    text('UPDATE "user" SET password = :password WHERE id = :user_id'),
                    {
                        "password": generate_password_hash(stored_password),
                        "user_id": user_id,
                    },
                )
                migrated_passwords += 1
    if statements or migrated_passwords:
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
    end_time = db.Column(db.DateTime)
    timezone = db.Column(db.String(80), default="Asia/Shanghai", nullable=False)
    max_participants = db.Column(db.Integer)
    initial_participants = db.Column(db.Integer, default=0, nullable=False)
    image = db.Column(db.String(255))
    fee = db.Column(db.Float, default=0, nullable=False)
    tags = db.Column(db.Text)
    circle_id = db.Column(db.Integer, db.ForeignKey("circle.id"), nullable=True)
    status = db.Column(db.String(20), default="open", nullable=False)
    cancel_reason = db.Column(db.Text)
    cancelled_at = db.Column(db.DateTime)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    is_official = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    organizer_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    preparation = db.Column(db.Text)  # 活动准备事项

    organizer = db.relationship("User", back_populates="activities")
    circle = db.relationship("Circle", back_populates="activities")
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
    # Legacy SQLite fallback only; production PostgreSQL schema is managed by migrations.
    if skip_non_sqlite_schema_helper("ensure_activity_schema"):
        return

    rows = db.session.execute(text("PRAGMA table_info(activity)")).fetchall()
    existing_columns = {row[1] for row in rows}
    statements = []
    if rows and "detail" not in existing_columns:
        statements.append("ALTER TABLE activity ADD COLUMN detail TEXT")
    if rows and "city" not in existing_columns:
        statements.append("ALTER TABLE activity ADD COLUMN city VARCHAR(80)")
    if rows and "end_time" not in existing_columns:
        statements.append("ALTER TABLE activity ADD COLUMN end_time DATETIME")
    if rows and "timezone" not in existing_columns:
        statements.append(
            "ALTER TABLE activity ADD COLUMN timezone VARCHAR(80) "
            "NOT NULL DEFAULT 'Asia/Shanghai'"
        )
    if rows and "initial_participants" not in existing_columns:
        statements.append(
            "ALTER TABLE activity ADD COLUMN initial_participants INTEGER NOT NULL DEFAULT 0"
        )
    if rows and "tags" not in existing_columns:
        statements.append("ALTER TABLE activity ADD COLUMN tags TEXT")
    if rows and "circle_id" not in existing_columns:
        statements.append("ALTER TABLE activity ADD COLUMN circle_id INTEGER")
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
    if rows and "is_official" not in existing_columns:
        statements.append(
            "ALTER TABLE activity ADD COLUMN is_official BOOLEAN NOT NULL DEFAULT 0"
        )

    for statement in statements:
        db.session.execute(text(statement))
    if rows:
        db.session.execute(
            text(
                "UPDATE activity "
                "SET end_time = datetime(start_time, '+2 hours') "
                "WHERE end_time IS NULL AND start_time IS NOT NULL"
            )
        )
        db.session.execute(
            text(
                "UPDATE activity SET is_official = 1 "
                "WHERE organizer_id IN ("
                "SELECT id FROM user WHERE role = 'admin' OR username = 'gatherly_demo'"
                ")"
            )
        )
    if statements or rows:
        db.session.commit()


class Registration(db.Model):
    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "activity_id",
            name="uq_registration_user_activity",
        ),
    )

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
    # Legacy SQLite fallback only; production PostgreSQL schema is managed by migrations.
    if skip_non_sqlite_schema_helper("ensure_registration_schema"):
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
    if rows:
        db.session.execute(
            text(
                "INSERT INTO registration "
                "(user_id, activity_id, status, register_time) "
                "SELECT activity.organizer_id, activity.id, 'registered', "
                "COALESCE(activity.created_at, CURRENT_TIMESTAMP) "
                "FROM activity "
                "WHERE activity.organizer_id IS NOT NULL "
                "AND NOT EXISTS ("
                "SELECT 1 FROM registration "
                "WHERE registration.user_id = activity.organizer_id "
                "AND registration.activity_id = activity.id"
                ")"
            )
        )
    if statements or rows:
        db.session.commit()


class EmailVerificationCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    email = db.Column(db.String(120), nullable=False, index=True)
    code = db.Column(db.String(128), nullable=False)
    purpose = db.Column(db.String(30), default="register", nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User", back_populates="email_verification_codes")


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text)
    related_type = db.Column(db.String(50))
    related_id = db.Column(db.Integer)
    read_at = db.Column(db.DateTime, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    recipient = db.relationship("User", back_populates="notifications")


NOTIFICATION_RETENTION_DAYS = 90


def create_notification(
    recipient_id,
    notification_type,
    title,
    content=None,
    related_type=None,
    related_id=None,
    retention_days=NOTIFICATION_RETENTION_DAYS,
):
    notification = Notification(
        recipient_id=recipient_id,
        type=notification_type,
        title=title,
        content=content,
        related_type=related_type,
        related_id=related_id,
        expires_at=datetime.utcnow() + timedelta(days=retention_days),
    )
    db.session.add(notification)
    return notification


def cleanup_expired_notifications(now=None):
    return Notification.query.filter(
        Notification.expires_at <= (now or datetime.utcnow())
    ).delete(synchronize_session=False)


def ensure_notification_schema():
    # Legacy SQLite fallback only; production PostgreSQL schema is managed by migrations.
    if skip_non_sqlite_schema_helper("ensure_notification_schema"):
        return

    Notification.__table__.create(db.engine, checkfirst=True)

    rows = db.session.execute(text("PRAGMA table_info(notification)")).fetchall()
    existing_columns = {row[1] for row in rows}
    if rows and "expires_at" not in existing_columns:
        db.session.execute(text("ALTER TABLE notification ADD COLUMN expires_at DATETIME"))
        db.session.execute(
            text(
                "UPDATE notification SET expires_at = "
                "datetime(COALESCE(created_at, CURRENT_TIMESTAMP), '+90 days') "
                "WHERE expires_at IS NULL"
            )
        )
    db.session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_notification_recipient_id "
            "ON notification (recipient_id)"
        )
    )
    db.session.execute(
        text("CREATE INDEX IF NOT EXISTS ix_notification_read_at ON notification (read_at)")
    )
    db.session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_notification_expires_at "
            "ON notification (expires_at)"
        )
    )
    db.session.commit()


class DirectMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    content = db.Column(db.Text)
    message_type = db.Column(db.String(20), default="text", nullable=False)
    image_url = db.Column(db.String(255))
    read_at = db.Column(db.DateTime, index=True)
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
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


class DirectMessageConversationState(db.Model):
    __tablename__ = "direct_message_conversation_state"
    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "other_user_id",
            name="uq_direct_message_conversation_state_pair",
        ),
        db.CheckConstraint(
            "user_id != other_user_id",
            name="ck_direct_message_conversation_state_not_self",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    other_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    is_hidden = db.Column(db.Boolean, default=False, nullable=False)
    hidden_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    cleared_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = db.relationship("User", foreign_keys=[user_id])
    other_user = db.relationship("User", foreign_keys=[other_user_id])


DIRECT_MESSAGE_RETENTION_DAYS = 180


class UserFollow(db.Model):
    __table_args__ = (
        db.UniqueConstraint("follower_id", "followed_id", name="uq_user_follow_pair"),
        db.CheckConstraint("follower_id != followed_id", name="ck_user_follow_not_self"),
    )

    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    followed_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    follower = db.relationship(
        "User",
        foreign_keys=[follower_id],
        back_populates="following",
    )
    followed = db.relationship(
        "User",
        foreign_keys=[followed_id],
        back_populates="followers",
    )


def users_are_mutual_followers(user_a_id, user_b_id):
    if user_a_id == user_b_id:
        return True
    return (
        UserFollow.query.filter_by(follower_id=user_a_id, followed_id=user_b_id).first()
        is not None
        and UserFollow.query.filter_by(follower_id=user_b_id, followed_id=user_a_id).first()
        is not None
    )


def cleanup_expired_direct_messages(now=None):
    return DirectMessage.query.filter(
        DirectMessage.expires_at <= (now or datetime.utcnow())
    ).delete(synchronize_session=False)


def ensure_direct_message_schema():
    # Legacy SQLite fallback only; production PostgreSQL schema is managed by migrations.
    if skip_non_sqlite_schema_helper("ensure_direct_message_schema"):
        return

    DirectMessage.__table__.create(db.engine, checkfirst=True)
    DirectMessageConversationState.__table__.create(db.engine, checkfirst=True)
    UserFollow.__table__.create(db.engine, checkfirst=True)

    rows = db.session.execute(text("PRAGMA table_info(direct_message)")).fetchall()
    existing_columns = {row[1] for row in rows}
    if rows and "message_type" not in existing_columns:
        db.session.execute(
            text(
                "ALTER TABLE direct_message ADD COLUMN message_type "
                "VARCHAR(20) NOT NULL DEFAULT 'text'"
            )
        )
    if rows and "image_url" not in existing_columns:
        if "image_path" in existing_columns:
            db.session.execute(
                text("ALTER TABLE direct_message RENAME COLUMN image_path TO image_url")
            )
        else:
            db.session.execute(text("ALTER TABLE direct_message ADD COLUMN image_url VARCHAR(255)"))
    if rows and "expires_at" not in existing_columns:
        db.session.execute(text("ALTER TABLE direct_message ADD COLUMN expires_at DATETIME"))
        db.session.execute(
            text(
                "UPDATE direct_message SET expires_at = "
                "datetime(COALESCE(created_at, CURRENT_TIMESTAMP), '+180 days') "
                "WHERE expires_at IS NULL"
            )
        )
    state_rows = db.session.execute(
        text("PRAGMA table_info(direct_message_conversation_state)")
    ).fetchall()
    state_columns = {row[1] for row in state_rows}
    if state_rows and "cleared_at" not in state_columns:
        db.session.execute(
            text("ALTER TABLE direct_message_conversation_state ADD COLUMN cleared_at DATETIME")
        )
    db.session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_direct_message_sender_id "
            "ON direct_message (sender_id)"
        )
    )
    db.session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_direct_message_recipient_id "
            "ON direct_message (recipient_id)"
        )
    )
    db.session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_direct_message_read_at "
            "ON direct_message (read_at)"
        )
    )
    db.session.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_direct_message_expires_at "
            "ON direct_message (expires_at)"
        )
    )
    db.session.commit()


class MerchantVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    business_name = db.Column(db.String(120), nullable=False)
    license_number = db.Column(db.String(120))
    document_url = db.Column(db.String(255))
    reason = db.Column(db.Text)
    contact = db.Column(db.String(160))
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


def ensure_merchant_verification_schema():
    # Legacy SQLite fallback only; production PostgreSQL schema is managed by migrations.
    if skip_non_sqlite_schema_helper("ensure_merchant_verification_schema"):
        return

    MerchantVerification.__table__.create(db.engine, checkfirst=True)

    rows = db.session.execute(text("PRAGMA table_info(merchant_verification)")).fetchall()
    existing_columns = {row[1] for row in rows}
    statements = []
    if rows and "document_url" not in existing_columns:
        if "document_path" in existing_columns:
            statements.append(
                "ALTER TABLE merchant_verification RENAME COLUMN document_path TO document_url"
            )
        else:
            statements.append("ALTER TABLE merchant_verification ADD COLUMN document_url VARCHAR(255)")
    if rows and "reason" not in existing_columns:
        statements.append("ALTER TABLE merchant_verification ADD COLUMN reason TEXT")
    if rows and "contact" not in existing_columns:
        statements.append("ALTER TABLE merchant_verification ADD COLUMN contact VARCHAR(160)")

    for statement in statements:
        db.session.execute(text(statement))
    if statements:
        db.session.commit()


def is_verified_merchant(user):
    if not user:
        return False
    return any(verification.status == "approved" for verification in user.merchant_verifications)


def ensure_task_foundation_schema():
    # Legacy SQLite fallback only; production PostgreSQL schema is managed by migrations.
    if skip_non_sqlite_schema_helper("ensure_task_foundation_schema"):
        return

    ensure_user_account_schema()
    ensure_activity_schema()
    ensure_registration_schema()
    for model in (EmailVerificationCode,):
        model.__table__.create(db.engine, checkfirst=True)
    ensure_direct_message_schema()
    ensure_merchant_verification_schema()
    ensure_notification_schema()


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
    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", name="fk_circle_owner_id_user"),
    )
    pinned_post_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "post.id",
            use_alter=True,
            name="fk_circle_pinned_post_id_post",
        ),
    )
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
    activities = db.relationship("Activity", back_populates="circle")
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
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id", name="fk_post_user_id_user"),
        nullable=False,
    )
    circle_id = db.Column(
        db.Integer,
        db.ForeignKey("circle.id", name="fk_post_circle_id_circle"),
        nullable=False,
    )

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
    image_url = db.Column(db.String(255), nullable=False)
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
    image_url = db.Column(db.String(255), nullable=False)
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
