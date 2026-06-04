from datetime import datetime, timedelta
import os
from types import SimpleNamespace
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.models import (
    Activity,
    Circle,
    CircleMember,
    CircleRating,
    Comment,
    CommentImage,
    Interaction,
    Post,
    PostImage,
    Registration,
    User,
    create_notification,
    db,
    skip_non_sqlite_schema_helper,
)
from app.utils.upload_limits import upload_limit
from app.utils.upload_utils import delete_saved_images, save_image_files, validate_upload_files

circle_bp = Blueprint("circle", __name__)

POST_IMAGE_LIMIT = upload_limit("post_images")
COMMENT_IMAGE_LIMIT = upload_limit("comment_images")
POST_UPLOAD_SUBDIR = "posts"
COMMENT_UPLOAD_SUBDIR = "comments"
CIRCLE_COVER_ASSET_SUBDIR = "images/circle_covers/"
CIRCLE_COVER_UPLOAD_SUBDIR = "circles"
CIRCLE_COVER_UPLOAD_PREFIX = "images/circles/"
PLACEHOLDER_ASSET_SUBDIR = "images/placeholders/"
CIRCLE_COVER_ALLOWED_SUBDIRS = (
    CIRCLE_COVER_ASSET_SUBDIR,
    CIRCLE_COVER_UPLOAD_PREFIX,
    PLACEHOLDER_ASSET_SUBDIR,
)
LEGACY_DEFAULT_CIRCLE_COVER = f"{CIRCLE_COVER_ASSET_SUBDIR}default.webp"
DEFAULT_CIRCLE_COVER = f"{PLACEHOLDER_ASSET_SUBDIR}circle-placeholder.svg"
CIRCLE_COVER_LIMIT = upload_limit("circle_cover")
OFFICIAL_CIRCLE_COVER_MAX_BYTES = 500 * 1024
CIRCLE_COVER_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".svg"}
HOT_CIRCLE_MEMBER_THRESHOLD = 200
HOT_CIRCLE_SCORE_THRESHOLD = 260
HOT_CIRCLE_POST_WEIGHT = 3
HOT_CIRCLE_RECENT_POST_WEIGHT = 5
HOT_CIRCLE_RECENT_DAYS = 30
OFFICIAL_CIRCLE_SUFFIX = "同好圈"
DEFAULT_ACTIVITY_TIMEZONE = "Asia/Shanghai"
CIRCLE_RATING_ACTIVITY_NOT_STARTED_MESSAGE = "该活动尚未开始，活动开始后才可以评分。"
CIRCLE_RATING_NO_ACTIVITY_MESSAGE = "报名并参与该同好圈活动后，可进行评分。"

_CIRCLE_DESCRIPTIONS = {
    "摄影影像": "聚合胶片摄影、相机维护、街头摄影、摄影展和桌面摄影等影像爱好者。",
    "运动户外": "覆盖骑行、徒步、露营、夜跑、飞盘、攀岩等线下运动与轻户外约伴。",
    "咖啡茶饮": "连接手冲咖啡、咖啡拉花、茶会品鉴和咖啡店探访爱好者。",
    "阅读出版": "围绕独立出版、读书会、二手书交换、写作交流和书店探访展开。",
    "手作艺术": "收纳陶艺、插画手账、手帐拼贴、香薰调香和其他手作体验。",
    "音乐演出": "发现 Livehouse、音乐节、黑胶唱片试听和小型音乐现场。",
    "观影戏剧": "组织观影交流、剧本围读、即兴戏剧和展演后的线下讨论。",
    "城市探索": "发起城市漫步、旧物市集、古着穿搭、博物馆看展和本地探访。",
    "游戏桌游": "包含桌游组局、独立游戏试玩、模型手办交流和轻松联机活动。",
    "科技数码": "面向开源技术、数码工具、创客实践和技术主题线下分享。",
    "美食烘焙": "聚合本地美食、烘焙试吃、食谱交流和周末探店计划。",
    "公益志愿": "连接社区服务、公益行动、环保活动和志愿者线下协作。",
}

_ACTIVE_LEVELS = ["高活跃", "稳定活跃", "新兴活跃"]


_OFFICIAL_CIRCLE_COVERS = [
    "photography.webp",
    "outdoor.webp",
    "coffee.webp",
    "reading.webp",
    "crafts.webp",
    "music.webp",
    "film.webp",
    "city.webp",
    "games.webp",
    "tech.webp",
    "food.webp",
    "volunteer.webp",
]

_LEGACY_OFFICIAL_CIRCLE_COVERS = [
    "circle-camera.svg",
    "circle-cycling.svg",
    "circle-coffee.svg",
    "circle-reading.svg",
    "circle-crafts.svg",
    "circle-music.svg",
    "circle-film.svg",
    "circle-city.svg",
    "circle-games.svg",
    "circle-tech.svg",
    "circle-food.svg",
    "circle-volunteer.svg",
    "generated/circle-cover-photo.webp",
    "generated/circle-cover-outdoor.webp",
    "generated/circle-cover-coffee.webp",
    "generated/circle-cover-reading.webp",
    "generated/circle-cover-crafts.webp",
    "generated/circle-cover-music.webp",
    "generated/circle-cover-film.webp",
    "generated/circle-cover-city.webp",
    "generated/circle-cover-games.webp",
    "generated/circle-cover-tech.webp",
    "generated/circle-cover-food.webp",
    "generated/circle-cover-volunteer.webp",
]


def _official_cover_image(index):
    filename = _OFFICIAL_CIRCLE_COVERS[(index - 1) % len(_OFFICIAL_CIRCLE_COVERS)]
    return f"{CIRCLE_COVER_ASSET_SUBDIR}{filename}"


def _official_default_cover_paths():
    current_paths = {
        f"{CIRCLE_COVER_ASSET_SUBDIR}{filename}"
        for filename in _OFFICIAL_CIRCLE_COVERS
    }
    legacy_paths = {
        f"{CIRCLE_COVER_UPLOAD_PREFIX}{filename}"
        for filename in _LEGACY_OFFICIAL_CIRCLE_COVERS
    }
    return current_paths | legacy_paths | {DEFAULT_CIRCLE_COVER, LEGACY_DEFAULT_CIRCLE_COVER}


def _is_official_default_cover(image_path):
    return not image_path or image_path in _official_default_cover_paths()


def _circle_cover_image(circle):
    cover_image = getattr(circle, "cover_image", None)
    if not cover_image:
        return DEFAULT_CIRCLE_COVER
    if cover_image.startswith(("http://", "https://", "/static/uploads/circles/")):
        return cover_image
    if not cover_image.startswith(CIRCLE_COVER_ALLOWED_SUBDIRS):
        return DEFAULT_CIRCLE_COVER
    if os.path.splitext(cover_image)[1].lower() not in CIRCLE_COVER_EXTENSIONS:
        return DEFAULT_CIRCLE_COVER
    cover_path = os.path.abspath(os.path.join(current_app.static_folder, cover_image))
    is_allowed = False
    for cover_subdir in CIRCLE_COVER_ALLOWED_SUBDIRS:
        if not cover_image.startswith(cover_subdir):
            continue
        cover_dir = os.path.abspath(os.path.join(current_app.static_folder, cover_subdir))
        if os.path.commonpath([cover_dir, cover_path]) == cover_dir:
            is_allowed = True
            break
    if not is_allowed:
        return DEFAULT_CIRCLE_COVER
    if not os.path.isfile(cover_path):
        return DEFAULT_CIRCLE_COVER
    max_bytes = (
        OFFICIAL_CIRCLE_COVER_MAX_BYTES
        if cover_image.startswith(CIRCLE_COVER_ASSET_SUBDIR)
        else CIRCLE_COVER_LIMIT["max_file_size"]
    )
    if os.path.getsize(cover_path) >= max_bytes:
        return DEFAULT_CIRCLE_COVER
    return cover_image


def _save_circle_cover(file):
    if not file or not file.filename:
        return None
    validated_images = validate_upload_files(
        [file],
        "circle_cover",
    )
    image_paths = save_image_files(validated_images, CIRCLE_COVER_UPLOAD_SUBDIR)
    return image_paths[0] if image_paths else None


def _is_uploaded_circle_cover(image_path):
    return bool(
        image_path
        and (
            image_path.startswith(CIRCLE_COVER_UPLOAD_PREFIX)
            or image_path.startswith("/static/uploads/circles/")
            or image_path.startswith(("http://", "https://"))
        )
        and image_path not in _official_default_cover_paths()
        and os.path.splitext(image_path)[1].lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )


def _delete_uploaded_circle_cover(image_path):
    if not _is_uploaded_circle_cover(image_path):
        return
    delete_saved_images([image_path])


def _can_edit_circle_cover(user, circle):
    return bool(user and (user.role == "admin" or circle.owner_id == user.id))


def _upload_limit_context():
    return {
        "post_image_limit": POST_IMAGE_LIMIT,
        "comment_image_limit": COMMENT_IMAGE_LIMIT,
        "circle_cover_limit": CIRCLE_COVER_LIMIT,
    }


def _official_description(tag):
    return _CIRCLE_DESCRIPTIONS.get(tag, f"{tag}爱好者的官方同好圈。")


def _official_member_count(index):
    return 96 + index * 17 + (index % 5) * 23


def _official_post_count(index):
    return 12 + index * 3 + (index % 4) * 5


def _official_circle_name(tag):
    return tag


def _legacy_official_circle_name(tag):
    return f"{tag}{OFFICIAL_CIRCLE_SUFFIX}"


def _strip_official_suffix(name):
    if name and name.endswith(OFFICIAL_CIRCLE_SUFFIX):
        return name[: -len(OFFICIAL_CIRCLE_SUFFIX)]
    return name


CIRCLE_OFFICIAL_TOPIC_TAGS = [
    "影像摄影",
    "运动户外",
    "咖啡茶饮",
    "阅读出版",
    "手作艺术",
    "音乐演出",
    "观影戏剧",
    "城市探索",
    "游戏桌游",
    "科技数码",
    "美食烘焙",
    "公益志愿",
]

CIRCLE_CREATE_INTEREST_CATEGORIES = [
    {"icon": "🎉", "tag": "社交活动"},
    {"icon": "🎨", "tag": "兴趣爱好"},
    {"icon": "⚽", "tag": "运动健身"},
    {"icon": "🌲", "tag": "旅行与户外"},
    {"icon": "💼", "tag": "职业与商业"},
    {"icon": "💻", "tag": "科技"},
    {"icon": "🏙️", "tag": "社区与环境"},
    {"icon": "🌐", "tag": "身份与语言"},
    {"icon": "🎮", "tag": "游戏"},
    {"icon": "🎶", "tag": "舞蹈"},
    {"icon": "💗", "tag": "支持与辅导"},
    {"icon": "🎵", "tag": "音乐"},
    {"icon": "💜", "tag": "健康与身心"},
    {"icon": "🎭", "tag": "艺术与文化"},
    {"icon": "🔬", "tag": "科学与教育"},
    {"icon": "🐱", "tag": "宠物与动物"},
    {"icon": "🙏", "tag": "宗教与修养"},
    {"icon": "✍️", "tag": "写作"},
    {"icon": "👨‍👩‍👧", "tag": "父母与家庭"},
    {"icon": "🏛️", "tag": "社会运动与政治"},
]


def _circle_interest_tags():
    return list(CIRCLE_OFFICIAL_TOPIC_TAGS)


def _create_circle_template_context(is_admin):
    return {
        "circles": [],
        "create_mode": True,
        "is_admin": is_admin,
        "interest_categories": CIRCLE_CREATE_INTEREST_CATEGORIES,
        **_upload_limit_context(),
    }


def _selected_create_circle_tags():
    available_tags = {category["tag"] for category in CIRCLE_CREATE_INTEREST_CATEGORIES}
    raw_tags = request.form.getlist("tags")
    legacy_tag = request.form.get("tag", "").strip()
    if legacy_tag and not raw_tags:
        raw_tags = legacy_tag.split(",")

    selected_tags = []
    for tag in raw_tags:
        tag = tag.strip()
        if tag in available_tags and tag not in selected_tags:
            selected_tags.append(tag)
    return selected_tags


def _compose_circle_description(short_description, detailed_description, suitable_for):
    parts = [short_description]
    if detailed_description and detailed_description != short_description:
        parts.append(f"详细介绍：{detailed_description}")
    if suitable_for:
        parts.append(f"适合谁加入：{suitable_for}")
    return "\n\n".join(parts)


def _compose_circle_announcement(announcement):
    rule_notice = "基础规则：不发硬广、不骚扰、不发布虚假活动。"
    if announcement:
        return f"{announcement}\n\n{rule_notice}"
    return rule_notice


def _is_admin(user):
    return bool(user and user.role == "admin")


def _ensure_circle_columns():
    # Legacy SQLite fallback only; production PostgreSQL schema is managed by migrations.
    if skip_non_sqlite_schema_helper("_ensure_circle_columns"):
        return

    rows = db.session.execute(text("PRAGMA table_info(circle)")).fetchall()
    existing_columns = {row[1] for row in rows}
    statements = []
    if "owner_id" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN owner_id INTEGER")
    if "announcement" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN announcement TEXT")
    if "cover_image" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN cover_image VARCHAR(255)")
    if "pinned_post_id" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN pinned_post_id INTEGER")
    if "is_pinned" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0")
    if "pinned_at" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN pinned_at DATETIME")
    if "is_system" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN is_system BOOLEAN NOT NULL DEFAULT 0")
    if "member_count" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN member_count INTEGER NOT NULL DEFAULT 0")
    if "initial_member_count" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN initial_member_count INTEGER NOT NULL DEFAULT 0")
    if "updated_at" not in existing_columns:
        statements.append("ALTER TABLE circle ADD COLUMN updated_at DATETIME")

    for statement in statements:
        db.session.execute(text(statement))
    member_rows = db.session.execute(text("PRAGMA table_info(circle_member)")).fetchall()
    member_columns = {row[1] for row in member_rows}
    if member_rows and "role" not in member_columns:
        db.session.execute(
            text("ALTER TABLE circle_member ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'member'")
        )
        statements.append("ALTER TABLE circle_member ADD COLUMN role")
    normalized_roles = 0
    legacy_role_count = 0
    if member_rows:
        legacy_role_count = db.session.execute(
            text("SELECT COUNT(*) FROM circle_member WHERE role = 'admin'")
        ).scalar()
    if legacy_role_count:
        normalized_roles = db.session.execute(
            text("UPDATE circle_member SET role = 'moderator' WHERE role = 'admin'")
        ).rowcount
    if rows and "initial_member_count" not in existing_columns:
        db.session.execute(
            text(
                """
                UPDATE circle
                SET initial_member_count = MAX(
                    member_count - (
                        SELECT COUNT(*)
                        FROM circle_member
                        WHERE circle_member.circle_id = circle.id
                          AND circle_member.status = 'active'
                    ),
                    0
                )
                """
            )
        )
    if rows and "updated_at" not in existing_columns:
        db.session.execute(text("UPDATE circle SET updated_at = created_at WHERE updated_at IS NULL"))
    if statements or normalized_roles:
        db.session.commit()


def _ensure_circle_rating_columns():
    # Legacy SQLite fallback only; production PostgreSQL schema is managed by migrations.
    if skip_non_sqlite_schema_helper("_ensure_circle_rating_columns"):
        return

    rows = db.session.execute(text("PRAGMA table_info(circle_rating)")).fetchall()
    existing_columns = {row[1] for row in rows}
    if rows and "activity_id" not in existing_columns:
        db.session.execute(text("ALTER TABLE circle_rating ADD COLUMN activity_id INTEGER"))
        db.session.execute(text("CREATE INDEX IF NOT EXISTS ix_circle_rating_activity_id ON circle_rating (activity_id)"))
        db.session.commit()


@circle_bp.before_app_request
def ensure_circle_schema():
    _ensure_circle_columns()
    _ensure_circle_rating_columns()
    _ensure_circle_image_tables()


def _ensure_circle_image_tables():
    # Production schema should be managed by Flask-Migrate / Alembic migrations.
    # This helper only protects local SQLite fallback databases.
    if skip_non_sqlite_schema_helper("_ensure_circle_image_tables"):
        return

    PostImage.__table__.create(db.engine, checkfirst=True)
    CommentImage.__table__.create(db.engine, checkfirst=True)

    statements = []
    for table_name in ("post_image", "comment_image"):
        rows = db.session.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        existing_columns = {row[1] for row in rows}
        if rows and "image_url" not in existing_columns:
            if "image_path" in existing_columns:
                statements.append(
                    f"ALTER TABLE {table_name} RENAME COLUMN image_path TO image_url"
                )
            else:
                statements.append(
                    f"ALTER TABLE {table_name} ADD COLUMN image_url VARCHAR(255)"
                )

    for statement in statements:
        db.session.execute(text(statement))
    if statements:
        db.session.commit()


def _ensure_post_status_column():
    # Legacy SQLite fallback only; production PostgreSQL schema is managed by migrations.
    if skip_non_sqlite_schema_helper("_ensure_post_status_column"):
        return

    rows = db.session.execute(text("PRAGMA table_info(post)")).fetchall()
    existing_columns = {row[1] for row in rows}
    if "status" not in existing_columns:
        db.session.execute(text("ALTER TABLE post ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'published'"))
        db.session.commit()


def _ensure_comment_parent_column():
    # Legacy SQLite fallback only; production PostgreSQL schema is managed by migrations.
    if skip_non_sqlite_schema_helper("_ensure_comment_parent_column"):
        return

    rows = db.session.execute(text("PRAGMA table_info(comment)")).fetchall()
    existing_columns = {row[1] for row in rows}
    if "parent_id" not in existing_columns:
        db.session.execute(text("ALTER TABLE comment ADD COLUMN parent_id INTEGER"))
        db.session.commit()


def _sync_system_circles():
    try:
        _ensure_circle_columns()
        _ensure_circle_image_tables()
        _ensure_post_status_column()
        _ensure_comment_parent_column()
        for circle in Circle.query.filter_by(is_system=True).all():
            circle.name = _strip_official_suffix(circle.name)

        for index, tag in enumerate(_circle_interest_tags(), start=1):
            name = _official_circle_name(tag)
            circle = (
                Circle.query.filter(
                    Circle.is_system.is_(True),
                    Circle.name.in_([name, _legacy_official_circle_name(tag)]),
                ).first()
            )
            if circle is None:
                circle = Circle(name=name, tag=tag, is_system=True)
                db.session.add(circle)
            else:
                circle.name = name

            circle.description = _official_description(tag)
            if _is_official_default_cover(circle.cover_image):
                circle.cover_image = _official_cover_image(index)
            circle.initial_member_count = max(
                circle.initial_member_count or 0,
                _official_member_count(index),
            )
            _refresh_member_count(circle)
        db.session.commit()
    except OperationalError:
        db.session.rollback()


def _build_mock_circles():
    circles = []
    for index, tag in enumerate(_circle_interest_tags(), start=1):
        member_count = _official_member_count(index)
        post_count = _official_post_count(index)
        circles.append(
            {
                "id": index,
                "name": _official_circle_name(tag),
                "tag": tag,
                "description": _official_description(tag),
                "cover_image": _official_cover_image(index),
                "active_level": _ACTIVE_LEVELS[index % len(_ACTIVE_LEVELS)],
                "member_count": member_count,
                "post_count": post_count,
                "members": member_count,
                "activity_count": 2 + index % 7,
                "is_system": True,
            }
        )
    return circles


mock_circles = _build_mock_circles()


def _current_user():
    user_id = session.get("user_id")
    return User.query.get(user_id) if user_id else None


def _is_member(circle_id, user_id=None):
    user_id = user_id or session.get("user_id")
    if not user_id:
        return False
    return (
        CircleMember.query.filter_by(
            circle_id=circle_id,
            user_id=user_id,
            status="active",
        ).first()
        is not None
    )


def _circle_member_role(circle_id, user_id):
    if not user_id:
        return None
    member = CircleMember.query.filter_by(
        circle_id=circle_id,
        user_id=user_id,
        status="active",
    ).first()
    return member.role if member else None


def _can_manage_circle(user, circle):
    if user is None:
        return False
    if user.role == "admin" or circle.owner_id == user.id:
        return True
    return _circle_member_role(circle.id, user.id) in {"owner", "moderator", "admin"}


def _is_circle_owner(user, circle):
    return bool(user and circle.owner_id == user.id)


def _can_manage_circle_content(user, circle, author_id):
    if user is None:
        return False
    if user.role == "admin":
        return True
    if author_id == user.id:
        return True
    return _can_manage_circle(user, circle)


def _can_view_circle(user, circle):
    if circle.status == "deleted":
        return False
    if circle.status == "active":
        return True
    if circle.status == "private":
        return bool(_is_admin(user) or _is_circle_owner(user, circle) or _is_member(circle.id, user.id if user else None))
    return _is_admin(user)


def _can_set_circle_privacy(user, circle):
    return bool(user and (user.role == "admin" or circle.owner_id == user.id))


def _refresh_member_count(circle):
    active_member_count = CircleMember.query.filter_by(
        circle_id=circle.id,
        status="active",
    ).count()
    circle.member_count = max(circle.initial_member_count or 0, 0) + active_member_count


def _circle_post_count(circle):
    return Post.query.filter_by(circle_id=circle.id, status="published").count()


def _circle_recent_post_count(circle):
    recent_since = datetime.utcnow() - timedelta(days=HOT_CIRCLE_RECENT_DAYS)
    return Post.query.filter(
        Post.circle_id == circle.id,
        Post.status == "published",
        Post.created_at >= recent_since,
    ).count()


def _circle_rating_stats(circle_ids):
    circle_ids = {circle_id for circle_id in circle_ids if circle_id}
    if not circle_ids:
        return {}

    stats = {
        circle_id: {
            "average_rating": None,
            "rating_count": 0,
            "rating_distribution": {score: 0 for score in range(1, 6)},
        }
        for circle_id in circle_ids
    }
    summary_rows = (
        db.session.query(
            CircleRating.circle_id,
            func.avg(CircleRating.rating),
            func.count(CircleRating.id),
        )
        .filter(CircleRating.circle_id.in_(circle_ids))
        .group_by(CircleRating.circle_id)
        .all()
    )
    for circle_id, average_rating, rating_count in summary_rows:
        stats[circle_id]["average_rating"] = (
            round(float(average_rating), 1) if average_rating is not None else None
        )
        stats[circle_id]["rating_count"] = rating_count

    distribution_rows = (
        db.session.query(
            CircleRating.circle_id,
            CircleRating.rating,
            func.count(CircleRating.id),
        )
        .filter(CircleRating.circle_id.in_(circle_ids))
        .group_by(CircleRating.circle_id, CircleRating.rating)
        .all()
    )
    for circle_id, rating, count in distribution_rows:
        stats[circle_id]["rating_distribution"][rating] = count

    return stats


def _apply_circle_rating_stats(circle, stats=None):
    stats = stats or _circle_rating_stats([circle.id])
    rating_stats = stats.get(
        circle.id,
        {
            "average_rating": None,
            "rating_count": 0,
            "rating_distribution": {score: 0 for score in range(1, 6)},
        },
    )
    circle.average_rating_value = rating_stats["average_rating"]
    circle.rating_count_value = rating_stats["rating_count"]
    circle.rating_distribution_value = rating_stats["rating_distribution"]
    return circle


def _circle_activity_timezone(activity):
    timezone_name = activity.timezone if activity and activity.timezone else None
    timezone_name = timezone_name or DEFAULT_ACTIVITY_TIMEZONE
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_ACTIVITY_TIMEZONE)


def _circle_activity_now(activity):
    return datetime.now(_circle_activity_timezone(activity)).replace(tzinfo=None)


def _decorate_circle_rating_activity(activity):
    can_rate = bool(activity.start_time and activity.start_time <= _circle_activity_now(activity))
    activity.can_rate = can_rate
    activity.rating_status_label = "可评价" if can_rate else "未开始"
    activity.rating_status_class = "is-rateable" if can_rate else "is-pending"
    activity.rating_time_label = (
        activity.start_time.strftime("%Y-%m-%d %H:%M")
        if activity.start_time
        else "活动时间待补充"
    )
    return activity


def _eligible_circle_rating_activities(user_id, circle_id):
    if not user_id or not circle_id:
        return []
    activities = (
        Activity.query.join(Registration, Registration.activity_id == Activity.id)
        .filter(
            Registration.user_id == user_id,
            Registration.status != "cancelled",
            Activity.circle_id == circle_id,
            Activity.status != "cancelled",
        )
        .order_by(Activity.start_time.desc(), Activity.id.desc())
        .all()
    )
    for activity in activities:
        _decorate_circle_rating_activity(activity)
    activities.sort(
        key=lambda activity: (
            not activity.can_rate,
            -(activity.start_time.timestamp() if activity.start_time else 0),
            -activity.id,
        )
    )
    return activities


def _selected_circle_rating_activity_id(current_rating, eligible_activities):
    if current_rating and current_rating.activity_id:
        if any(activity.id == current_rating.activity_id for activity in eligible_activities):
            return current_rating.activity_id
    rateable_activity = next((activity for activity in eligible_activities if activity.can_rate), None)
    if rateable_activity:
        return rateable_activity.id
    if eligible_activities:
        return eligible_activities[0].id
    return None


def _format_circle_rating_activity_date(activity):
    if not activity or not activity.start_time:
        return "活动时间待补充"
    return f"{activity.start_time.year}年{activity.start_time.month}月{activity.start_time.day}日"


def _circle_rating_activity_label(activity):
    if not activity:
        return "关联活动待补充"
    return f"{_format_circle_rating_activity_date(activity)} · {activity.title}"


def _decorate_circle_rating_review(review):
    review.activity_detail_id = None
    review.activity_title = None
    review.activity_label = ""
    review.activity_date_label = ""

    if review.activity:
        review.activity_detail_id = review.activity.id
        review.activity_title = review.activity.title
        review.activity_label = _circle_rating_activity_label(review.activity)
        review.activity_date_label = _format_circle_rating_activity_date(review.activity)
    elif review.activity_id:
        review.activity_label = "关联活动已不存在"


def _circle_rating_context(circle, current_user):
    stats = _circle_rating_stats([circle.id]).get(
        circle.id,
        {
            "average_rating": None,
            "rating_count": 0,
            "rating_distribution": {score: 0 for score in range(1, 6)},
        },
    )
    review_query = (
        CircleRating.query.filter_by(circle_id=circle.id)
        .filter(CircleRating.comment.isnot(None))
    )
    if current_user:
        review_query = review_query.filter(CircleRating.user_id != current_user.id)
    recent_reviews = (
        review_query
        .order_by(
            func.coalesce(CircleRating.updated_at, CircleRating.created_at).desc(),
            CircleRating.id.desc(),
        )
        .all()
    )
    current_rating = None
    eligible_activities = []
    can_rate = False
    selected_activity_id = None
    notice = CIRCLE_RATING_NO_ACTIVITY_MESSAGE
    if current_user:
        current_rating = CircleRating.query.filter_by(
            circle_id=circle.id,
            user_id=current_user.id,
        ).first()
        eligible_activities = _eligible_circle_rating_activities(current_user.id, circle.id)
        can_rate = bool(eligible_activities)
        selected_activity_id = _selected_circle_rating_activity_id(
            current_rating,
            eligible_activities,
        )
        notice = "" if can_rate else CIRCLE_RATING_NO_ACTIVITY_MESSAGE

    for review in recent_reviews:
        _decorate_circle_rating_review(review)

    return {
        "average_rating": stats["average_rating"],
        "rating_count": stats["rating_count"],
        "rating_distribution": stats["rating_distribution"],
        "recent_reviews": recent_reviews,
        "current_user_rating": current_rating,
        "can_rate_circle": can_rate,
        "circle_rating_notice": notice,
        "eligible_rating_activities": eligible_activities,
        "selected_rating_activity_id": selected_activity_id,
    }


def _decorate_circle(circle):
    circle.cover_image_url = _circle_cover_image(circle)
    circle.active_level = "官方圈子" if circle.is_system else "自定义圈子"
    circle.post_count = _circle_post_count(circle)
    circle.recent_post_count = _circle_recent_post_count(circle)
    circle.heat_score = (
        circle.member_count
        + circle.post_count * HOT_CIRCLE_POST_WEIGHT
        + circle.recent_post_count * HOT_CIRCLE_RECENT_POST_WEIGHT
    )
    circle.is_hot = (
        circle.member_count >= HOT_CIRCLE_MEMBER_THRESHOLD
        or circle.heat_score >= HOT_CIRCLE_SCORE_THRESHOLD
    )
    circle.can_post = _is_member(circle.id)
    _apply_circle_rating_stats(circle)
    return circle


def _activity_category(activity):
    tags = [tag.strip() for tag in (activity.tags or "").split(",") if tag.strip()]
    return tags[0] if tags else "圈内活动"


def _activity_time_label(activity):
    return activity.start_time.strftime("%m月%d日 %H:%M") if activity.start_time else "时间待定"


def _activity_place_label(activity):
    return activity.location or activity.city or "地点待确认"


def _build_circle_activity_summaries(circle_ids, per_circle_limit=3):
    if not circle_ids:
        return {}, {}

    now = datetime.utcnow()
    activity_rows = (
        Activity.query.filter(
            Activity.status == "open",
            Activity.circle_id.in_(circle_ids),
            (Activity.start_time.is_(None)) | (Activity.start_time >= now),
        )
        .order_by(Activity.start_time.asc(), Activity.id.desc())
        .all()
    )
    activity_ids = [activity.id for activity in activity_rows]
    registration_counts = {}
    if activity_ids:
        registration_counts = dict(
            db.session.query(Registration.activity_id, func.count(Registration.id))
            .filter(
                Registration.activity_id.in_(activity_ids),
                Registration.status != "cancelled",
            )
            .group_by(Registration.activity_id)
            .all()
        )

    summaries_by_circle = {circle_id: [] for circle_id in circle_ids}
    counts_by_circle = {circle_id: 0 for circle_id in circle_ids}
    for activity in activity_rows:
        counts_by_circle[activity.circle_id] = counts_by_circle.get(activity.circle_id, 0) + 1
        if len(summaries_by_circle.setdefault(activity.circle_id, [])) >= per_circle_limit:
            continue
        current_people = (activity.initial_participants or 0) + registration_counts.get(activity.id, 0)
        summaries_by_circle[activity.circle_id].append(
            {
                "id": activity.id,
                "title": activity.title,
                "time": _activity_time_label(activity),
                "location": _activity_place_label(activity),
                "category": _activity_category(activity),
                "current_people": current_people,
                "max_participants": activity.max_participants,
            }
        )

    return summaries_by_circle, counts_by_circle


def _get_circle(circle_id):
    _sync_system_circles()
    circle = Circle.query.get(circle_id)
    if circle is not None:
        return circle

    mock_circle = next((item for item in mock_circles if item["id"] == circle_id), None)
    if mock_circle is None:
        return None
    return SimpleNamespace(**mock_circle)


def _interaction_counts(target_type, target_id):
    rows = (
        db.session.query(Interaction.action_type, func.count(Interaction.id))
        .filter(Interaction.target_type == target_type, Interaction.target_id == target_id)
        .group_by(Interaction.action_type)
        .all()
    )
    counts = {"like": 0, "favorite": 0, "share": 0}
    counts.update({action: count for action, count in rows})
    return counts


def _user_interaction_states(user_id, target_type, target_id):
    if not user_id:
        return {"like": False, "favorite": False}

    rows = Interaction.query.filter(
        Interaction.user_id == user_id,
        Interaction.target_type == target_type,
        Interaction.target_id == target_id,
        Interaction.action_type.in_(["like", "favorite"]),
    ).all()
    actions = {row.action_type for row in rows}
    return {
        "like": "like" in actions,
        "favorite": "favorite" in actions,
    }


def _toggle_interaction(user_id, target_type, target_id, action):
    existing = Interaction.query.filter_by(
        user_id=user_id,
        target_type=target_type,
        target_id=target_id,
        action_type=action,
    ).first()
    if existing is not None and action in {"like", "favorite"}:
        db.session.delete(existing)
        db.session.commit()
        return "removed"

    if existing is None:
        db.session.add(
            Interaction(
                user_id=user_id,
                target_type=target_type,
                target_id=target_id,
                action_type=action,
            )
        )
        db.session.commit()
        return "added"

    return "unchanged"


def _build_comment_item(comment, current_user, circle, replies_by_parent, depth=0, include_hidden=False):
    is_published = comment.status == "published"
    is_visible = is_published or (include_hidden and comment.status == "hidden")
    return {
        "comment": comment,
        "is_deleted": not is_visible,
        "depth": min(depth, 3),
        "counts": _interaction_counts("comment", comment.id) if is_published else {"like": 0, "favorite": 0},
        "states": (
            _user_interaction_states(
                current_user.id if current_user else None,
                "comment",
                comment.id,
            )
            if is_published
            else {"like": False, "favorite": False}
        ),
        "can_delete": (
            is_published
            and _can_manage_circle_content(current_user, circle, comment.author_id)
        ),
        "replies": [
            _build_comment_item(
                reply,
                current_user,
                circle,
                replies_by_parent,
                depth + 1,
                include_hidden=include_hidden,
            )
            for reply in replies_by_parent.get(comment.id, [])
            if reply.status == "published" or (include_hidden and reply.status == "hidden")
        ],
    }


def _build_comment_threads(comments, current_user, circle, include_hidden=False):
    replies_by_parent = {}
    for comment in comments:
        if comment.parent_id is not None:
            replies_by_parent.setdefault(comment.parent_id, []).append(comment)

    root_comments = []
    for comment in comments:
        if comment.parent_id is not None:
            continue
        has_visible_replies = any(
            reply.status == "published" or (include_hidden and reply.status == "hidden")
            for reply in replies_by_parent.get(comment.id, [])
        )
        if comment.status == "published" or (include_hidden and comment.status == "hidden") or has_visible_replies:
            root_comments.append(
                _build_comment_item(
                    comment,
                    current_user,
                    circle,
                    replies_by_parent,
                    include_hidden=include_hidden,
                )
            )

    return root_comments


@circle_bp.route("/circles")
def circles():
    _sync_system_circles()
    selected_circle_category = request.args.get("category", "").strip()
    circle_query = Circle.query.filter(Circle.status.in_(["active", "private"]))
    if selected_circle_category == "官方":
        circle_query = circle_query.filter(Circle.is_system.is_(True))
    if selected_circle_category == "新同好圈":
        circle_query = circle_query.order_by(Circle.created_at.desc(), Circle.id.desc())
    circle_rows = circle_query.all()
    decorated = [_decorate_circle(circle) for circle in circle_rows]
    if selected_circle_category == "热门":
        decorated = [circle for circle in decorated if circle.is_hot]
    circle_ids = [circle.id for circle in decorated]
    activities_by_circle, activity_counts_by_circle = _build_circle_activity_summaries(circle_ids)
    for circle in decorated:
        circle.recent_activities = activities_by_circle.get(circle.id, [])
        circle.recent_activity_count = activity_counts_by_circle.get(circle.id, 0)
    if selected_circle_category == "新同好圈":
        decorated.sort(
            key=lambda circle: (
                circle.created_at or datetime.min,
                circle.id,
            ),
            reverse=True,
        )
    else:
        decorated.sort(
            key=lambda circle: (
                circle.is_pinned,
                circle.pinned_at or datetime.min,
                circle.recent_activity_count,
                circle.heat_score,
                circle.member_count,
                circle.post_count,
                circle.updated_at or circle.created_at,
                circle.created_at,
            ),
            reverse=True,
        )
    return render_template(
        "circle.html",
        circles=decorated,
        selected_circle_category=selected_circle_category,
        **_upload_limit_context(),
    )


@circle_bp.route("/circle")
def circle_list():
    return circles()


@circle_bp.route("/my-groups")
def my_groups():
    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login", next=request.url))

    search_query = request.args.get("q", "").strip()
    memberships = (
        CircleMember.query.filter(
            CircleMember.user_id == user.id,
            CircleMember.status.in_(["active", "pending"]),
        )
        .join(Circle, CircleMember.circle_id == Circle.id)
        .filter(Circle.status != "deleted")
    )
    if search_query:
        memberships = memberships.filter(
            or_(
                Circle.name.ilike(f"%{search_query}%"),
                Circle.description.ilike(f"%{search_query}%"),
                Circle.tag.ilike(f"%{search_query}%"),
            )
        )
    memberships = memberships.order_by(CircleMember.joined_at.desc()).all()
    active_groups = [membership for membership in memberships if membership.status == "active"]
    pending_groups = [membership for membership in memberships if membership.status == "pending"]
    for membership in memberships:
        _decorate_circle(membership.circle)

    return render_template(
        "my_groups.html",
        active_groups=active_groups,
        pending_groups=pending_groups,
        search_query=search_query,
    )


@circle_bp.route("/circle/create", methods=["GET", "POST"])
def create_circle():
    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login", next=request.url))

    is_admin = _is_admin(user)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        selected_tags = _selected_create_circle_tags()
        tag = ",".join(selected_tags)
        city = request.form.get("city", "").strip()
        short_description = request.form.get("short_description", "").strip()
        detailed_description = request.form.get("detailed_description", "").strip()
        suitable_for = request.form.get("suitable_for", "").strip()
        announcement = request.form.get("announcement", "").strip()
        legacy_description = request.form.get("description", "").strip()
        if legacy_description and not short_description:
            short_description = legacy_description
        if legacy_description and not detailed_description:
            detailed_description = legacy_description
        description = _compose_circle_description(short_description, detailed_description, suitable_for)
        requested_type = request.form.get("circle_type", "custom").strip()
        wants_system_circle = requested_type in {"official", "system"}
        context = _create_circle_template_context(is_admin)

        required_fields = [
            (name, "请填写圈子名称。"),
            (selected_tags, "请选择至少一个兴趣标签。"),
            (city, "请填写所在城市或地区。"),
            (short_description, "请填写简短介绍。"),
            (detailed_description, "请填写详细简介。"),
            (announcement, "请填写公告或规则说明。"),
            (suitable_for, "请填写适合谁加入。"),
        ]
        missing_messages = [message for value, message in required_fields if not value]
        if missing_messages:
            for message in missing_messages:
                flash(message, "error")
            return render_template("circle.html", **context), 400
        if len(name) > 120:
            flash("圈子名称不能超过 120 个字符。", "error")
            return render_template("circle.html", **context), 400
        if len(tag) > 50:
            flash("兴趣标签不能超过 50 个字符。", "error")
            return render_template("circle.html", **context), 400
        if wants_system_circle and not is_admin:
            flash("只有管理员可以创建官方圈子。", "error")
            return render_template("circle.html", **context), 403

        is_system = wants_system_circle and is_admin
        try:
            cover_image = _save_circle_cover(request.files.get("cover_image"))
        except ValueError as exc:
            flash(str(exc), "error")
            return render_template("circle.html", **context), 400

        circle = Circle(
            name=_strip_official_suffix(name) if is_system else name,
            tag=tag or ("官方" if is_system else "自定义"),
            description=description,
            announcement=_compose_circle_announcement(announcement),
            owner_id=user.id,
            is_system=is_system,
            initial_member_count=0,
            member_count=1,
            cover_image=cover_image,
        )
        try:
            db.session.add(circle)
            db.session.flush()
            db.session.add(CircleMember(circle_id=circle.id, user_id=user.id, role="owner"))
            db.session.commit()
            flash("同好圈创建成功，你已成为圈主。", "success")
            return redirect(url_for("circle.circle_detail", circle_id=circle.id))
        except IntegrityError:
            db.session.rollback()
            delete_saved_images([cover_image] if cover_image else [])
            flash("创建失败，请换一个圈子名称后重试。", "error")
        except Exception:
            db.session.rollback()
            delete_saved_images([cover_image] if cover_image else [])
            flash("创建失败，请稍后重试。", "error")

    return render_template("circle.html", **_create_circle_template_context(is_admin))


@circle_bp.route("/circle/<int:circle_id>")
def circle_detail(circle_id):
    circle = _get_circle(circle_id)
    if circle is None:
        flash("圈子不存在或已被删除。", "error")
        return redirect(url_for("circle.circles"))

    if not isinstance(circle, Circle):
        flash("该圈子还未完成初始化，请刷新后重试。", "error")
        return redirect(url_for("circle.circles"))

    current_user = _current_user()
    rating_context = _circle_rating_context(circle, current_user)
    if not _can_view_circle(current_user, circle):
        if circle.status == "private":
            pending_request = None
            if current_user:
                pending_request = CircleMember.query.filter_by(
                    circle_id=circle.id,
                    user_id=current_user.id,
                    status="pending",
                ).first()
            return render_template(
                "circle_detail.html",
                circle=_decorate_circle(circle),
                private_request_mode=True,
                pending_request=pending_request,
                posts=[],
                related_activities=[],
                upcoming_activities=[],
                past_activities=[],
                related_activity_count=0,
                photo_items=[],
                owner_membership=None,
                moderator_memberships=[],
                featured_member_memberships=[],
                current_user=current_user,
                is_member=False,
                can_manage_circle=False,
                is_circle_owner=False,
                circle_members=[],
                pending_members=[],
                **rating_context,
                **_upload_limit_context(),
            )
        flash("同好圈不存在或暂不可见。", "error")
        return redirect(url_for("circle.circles"))

    _ensure_comment_parent_column()
    post_query = Post.query.filter_by(circle_id=circle.id)
    if _is_admin(current_user):
        post_query = post_query.filter(Post.status.in_(["published", "hidden"]))
    else:
        post_query = post_query.filter_by(status="published")
    posts = post_query.order_by(
        (Post.id == circle.pinned_post_id).desc(),
        Post.created_at.desc(),
    ).all()
    post_items = []
    photo_items = []
    for post in posts:
        comments = (
            Comment.query.filter_by(post_id=post.id)
            .order_by(Comment.created_at.asc())
            .all()
        )
        visible_comment_count = sum(
            comment.status == "published"
            or (_is_admin(current_user) and comment.status == "hidden")
            for comment in comments
        )
        can_delete_post = _can_manage_circle_content(current_user, circle, post.user_id)
        post_items.append(
            {
                "post": post,
                "is_pinned": post.id == circle.pinned_post_id,
                "comment_count": visible_comment_count,
                "counts": _interaction_counts("post", post.id),
                "states": _user_interaction_states(
                    current_user.id if current_user else None,
                    "post",
                    post.id,
                ),
                "can_delete": can_delete_post,
                "comments": _build_comment_threads(
                    comments,
                    current_user,
                    circle,
                    include_hidden=_is_admin(current_user),
                ),
            }
        )
        for image in post.images:
            photo_items.append(
                {
                    "image": image,
                    "post": post,
                    "can_delete": can_delete_post,
                }
            )
    active_members = (
        CircleMember.query.filter_by(circle_id=circle.id, status="active")
        .join(User, CircleMember.user_id == User.id)
        .order_by(User.nickname.asc(), User.username.asc())
        .all()
    )
    related_activity_count = Activity.query.filter_by(circle_id=circle.id).count()
    now = datetime.utcnow()
    upcoming_activity_rows = (
        Activity.query.filter_by(circle_id=circle.id)
        .filter(Activity.status != "cancelled")
        .filter(or_(Activity.start_time.is_(None), Activity.start_time >= now))
        .order_by(Activity.start_time.asc(), Activity.id.desc())
        .limit(6)
        .all()
    )
    past_activity_rows = (
        Activity.query.filter_by(circle_id=circle.id)
        .filter(Activity.status != "cancelled")
        .filter(Activity.start_time.is_not(None), Activity.start_time < now)
        .order_by(Activity.start_time.desc(), Activity.id.desc())
        .limit(6)
        .all()
    )
    related_activity_rows = upcoming_activity_rows + past_activity_rows
    related_activity_ids = [activity.id for activity in related_activity_rows]
    related_registration_counts = {}
    if related_activity_ids:
        related_registration_counts = dict(
            db.session.query(Registration.activity_id, func.count(Registration.id))
            .filter(
                Registration.activity_id.in_(related_activity_ids),
                Registration.status != "cancelled",
            )
            .group_by(Registration.activity_id)
            .all()
        )
    def _activity_card_item(activity):
        return {
            "id": activity.id,
            "title": activity.title,
            "image": activity.image or _circle_cover_image(circle),
            "time": activity.start_time.strftime("%Y-%m-%d %H:%M") if activity.start_time else "时间待定",
            "location": activity.location or activity.city or "地点待确认",
            "current_people": (activity.initial_participants or 0)
            + related_registration_counts.get(activity.id, 0),
            "max_participants": activity.max_participants,
            "category": (activity.tags or "").split(",")[0].strip() or "未分类",
            "circle_rating_average": rating_context["average_rating"],
            "circle_rating_count": rating_context["rating_count"],
        }

    upcoming_activities = [_activity_card_item(activity) for activity in upcoming_activity_rows]
    past_activities = [_activity_card_item(activity) for activity in past_activity_rows]
    owner_membership = next(
        (
            membership
            for membership in active_members
            if membership.user_id == circle.owner_id or membership.role == "owner"
        ),
        None,
    )
    moderator_memberships = [
        membership
        for membership in active_members
        if membership.user_id != circle.owner_id and membership.role in ["moderator", "admin"]
    ]
    featured_member_memberships = [
        membership
        for membership in active_members
        if membership.user_id != circle.owner_id and membership.role not in ["moderator", "admin", "owner"]
    ][:8]
    pending_members = (
        CircleMember.query.filter_by(circle_id=circle.id, status="pending")
        .join(User, CircleMember.user_id == User.id)
        .order_by(CircleMember.joined_at.asc())
        .all()
        if _can_set_circle_privacy(current_user, circle)
        else []
    )
    return render_template(
        "circle_detail.html",
        circle=_decorate_circle(circle),
        posts=post_items,
        related_activities=upcoming_activities,
        upcoming_activities=upcoming_activities,
        past_activities=past_activities,
        related_activity_count=related_activity_count,
        photo_items=photo_items,
        owner_membership=owner_membership,
        moderator_memberships=moderator_memberships,
        featured_member_memberships=featured_member_memberships,
        current_user=current_user,
        is_member=_is_member(circle.id),
        can_manage_circle=_can_manage_circle(current_user, circle),
        is_circle_owner=_is_circle_owner(current_user, circle),
        circle_members=active_members,
        pending_members=pending_members,
        private_request_mode=False,
        pending_request=None,
        **rating_context,
        **_upload_limit_context(),
    )


@circle_bp.route("/circle/<int:circle_id>/ratings", methods=["POST"])
def submit_circle_rating(circle_id):
    user = _current_user()
    if user is None:
        flash("请先登录后再评价同好圈。", "error")
        return redirect(url_for("auth.login", next=url_for("circle.circle_detail", circle_id=circle_id)))

    circle = Circle.query.get_or_404(circle_id)
    if not _can_view_circle(user, circle):
        flash("同好圈不存在或暂不可见。", "error")
        return redirect(url_for("circle.circles"))

    registered_activities = _eligible_circle_rating_activities(user.id, circle.id)
    if not registered_activities:
        flash(CIRCLE_RATING_NO_ACTIVITY_MESSAGE, "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor="circle-ratings"))

    selected_activity_id = request.form.get("activity_id", type=int)
    if selected_activity_id is None:
        selected_activity_id = _selected_circle_rating_activity_id(None, registered_activities)
    if selected_activity_id is None:
        flash("请选择本次评价关联活动。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor="circle-ratings"))

    selected_activity = db.session.get(Activity, selected_activity_id)
    if (
        selected_activity is None
        or selected_activity.circle_id != circle.id
        or selected_activity.status == "cancelled"
    ):
        flash("请选择你已报名的圈子关联活动。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor="circle-ratings"))

    registration = Registration.query.filter(
        Registration.user_id == user.id,
        Registration.activity_id == selected_activity.id,
        Registration.status != "cancelled",
    ).first()
    if registration is None:
        flash("请选择你已报名的圈子关联活动。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor="circle-ratings"))

    if not selected_activity.start_time or selected_activity.start_time > _circle_activity_now(selected_activity):
        flash(CIRCLE_RATING_ACTIVITY_NOT_STARTED_MESSAGE, "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor="circle-ratings"))

    try:
        rating_value = int(request.form.get("rating", ""))
    except (TypeError, ValueError):
        flash("评分必须为 1 到 5 的整数。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor="circle-ratings"))

    if rating_value < 1 or rating_value > 5:
        flash("评分必须为 1 到 5 的整数。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor="circle-ratings"))

    comment = request.form.get("comment", "").strip()
    if len(comment) > 1000:
        flash("评价内容不能超过 1000 个字符。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor="circle-ratings"))

    circle_rating = CircleRating.query.filter_by(
        circle_id=circle.id,
        user_id=user.id,
    ).first()
    is_update = circle_rating is not None
    if circle_rating is None:
        circle_rating = CircleRating(circle_id=circle.id, user_id=user.id)

    circle_rating.rating = rating_value
    circle_rating.comment = comment or None
    circle_rating.activity_id = selected_activity_id
    circle_rating.updated_at = datetime.utcnow()

    try:
        db.session.add(circle_rating)
        db.session.commit()
        flash("同好圈评价已更新。" if is_update else "同好圈评价已提交。", "success")
    except IntegrityError:
        db.session.rollback()
        flash("你已经评价过该同好圈，请刷新后更新已有评价。", "error")
    except Exception:
        db.session.rollback()
        flash("同好圈评价保存失败，请稍后重试。", "error")

    return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor="circle-ratings"))


@circle_bp.route("/circle/<int:circle_id>/join", methods=["POST"])
def join_circle(circle_id):
    user = _current_user()
    if user is None:
        flash("请先登录后再加入同好圈。", "error")
        return redirect(url_for("auth.login", next=url_for("circle.circle_detail", circle_id=circle_id)))

    circle = Circle.query.get_or_404(circle_id)
    if circle.status != "active":
        flash("该同好圈暂不可加入。", "error")
        return redirect(url_for("circle.circles"))
    member = CircleMember.query.filter_by(circle_id=circle.id, user_id=user.id).first()
    if member is None:
        db.session.add(CircleMember(circle_id=circle.id, user_id=user.id, role="member"))
    elif member.status != "active":
        member.status = "active"
        member.role = "owner" if circle.owner_id == user.id else "member"
        member.updated_at = datetime.utcnow()
    else:
        flash("您已经加入该同好圈。", "info")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))
    _refresh_member_count(circle)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("您已经加入该同好圈。", "info")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))
    flash("已加入同好圈。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/request-access", methods=["POST"])
def request_circle_access(circle_id):
    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login", next=url_for("circle.circle_detail", circle_id=circle_id)))

    circle = Circle.query.get_or_404(circle_id)
    if circle.status != "private":
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))
    if _can_view_circle(user, circle):
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    reason = request.form.get("reason", "").strip()
    if len(reason) < 5:
        flash("请填写至少 5 个字的申请理由。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))
    if len(reason) > 300:
        flash("申请理由不能超过 300 个字。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    member = CircleMember.query.filter_by(circle_id=circle.id, user_id=user.id).first()
    if member is None:
        member = CircleMember(circle_id=circle.id, user_id=user.id, role="member", status="pending")
        db.session.add(member)
    else:
        member.status = "pending"
        member.role = "member"
        member.updated_at = datetime.utcnow()

    if circle.owner_id:
        create_notification(
            circle.owner_id,
            "circle_access_request",
            f"{user.nickname or user.username} 申请加入私密同好圈",
            f"申请圈子：{circle.name}\n申请理由：{reason}",
            related_type="circle",
            related_id=circle.id,
        )
    db.session.commit()
    flash("申请已提交，等待圈主审核。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/privacy", methods=["POST"])
def update_circle_privacy(circle_id):
    user = _current_user()
    circle = Circle.query.get_or_404(circle_id)
    if not _can_set_circle_privacy(user, circle):
        flash("只有系统管理员或圈主可以设置圈子隐私。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    privacy = request.form.get("privacy", "public")
    circle.status = "private" if privacy == "private" else "active"
    db.session.commit()
    flash("圈子隐私设置已更新。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/member/<int:user_id>/access", methods=["POST"])
def review_circle_access(circle_id, user_id):
    user = _current_user()
    circle = Circle.query.get_or_404(circle_id)
    if not _can_set_circle_privacy(user, circle):
        flash("只有系统管理员或圈主可以审核申请。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    member = CircleMember.query.filter_by(
        circle_id=circle.id,
        user_id=user_id,
        status="pending",
    ).first_or_404()
    decision = request.form.get("decision", "")
    if decision == "approve":
        member.status = "active"
        member.role = "member"
        member.updated_at = datetime.utcnow()
        _refresh_member_count(circle)
        create_notification(
            member.user_id,
            "circle_access_approved",
            "同好圈申请已通过",
            f"你已可以进入「{circle.name}」。",
            related_type="circle",
            related_id=circle.id,
        )
        flash("已通过该成员申请。", "success")
    else:
        member.status = "rejected"
        member.updated_at = datetime.utcnow()
        create_notification(
            member.user_id,
            "circle_access_rejected",
            "同好圈申请未通过",
            f"你申请加入「{circle.name}」暂未通过。",
            related_type="circle",
            related_id=circle.id,
        )
        flash("已拒绝该成员申请。", "info")
    db.session.commit()
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/leave", methods=["POST"])
def leave_circle(circle_id):
    user = _current_user()
    if user is None:
        flash("请先登录后再退出同好圈。", "error")
        return redirect(url_for("auth.login", next=url_for("circle.circle_detail", circle_id=circle_id)))

    circle = Circle.query.get(circle_id)
    if circle is None:
        flash("同好圈不存在或已被移除。", "error")
        return redirect(url_for("circle.circles"))

    member = CircleMember.query.filter_by(
        circle_id=circle.id,
        user_id=user.id,
        status="active",
    ).first()
    if member is None:
        flash("您尚未加入该同好圈。", "info")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    if circle.owner_id == user.id:
        flash("请先将圈主身份转移给其他成员，再退出圈子。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    member.status = "inactive"
    member.role = "member"
    member.updated_at = datetime.utcnow()
    _refresh_member_count(circle)
    db.session.commit()
    flash("已退出同好圈。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/announcement", methods=["POST"])
def update_announcement(circle_id):
    user = _current_user()
    circle = Circle.query.get_or_404(circle_id)
    if not _can_manage_circle(user, circle):
        flash("没有权限编辑圈内公告。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    announcement = request.form.get("announcement", "").strip()
    if len(announcement) > 1000:
        flash("圈内公告不能超过 1000 个字符。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    circle.announcement = announcement or None
    db.session.commit()
    flash("圈内公告已更新。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/cover", methods=["POST"])
def update_circle_cover(circle_id):
    user = _current_user()
    circle = Circle.query.get_or_404(circle_id)
    if not _can_edit_circle_cover(user, circle):
        flash("只有圈主或管理员可以修改圈子封面。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    try:
        cover_image = _save_circle_cover(request.files.get("cover_image"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    if cover_image is None:
        flash("请选择一张圈子封面图片。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    previous_cover = circle.cover_image
    circle.cover_image = cover_image
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        delete_saved_images([cover_image])
        flash("圈子封面更新失败，请稍后重试。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    if _is_uploaded_circle_cover(previous_cover):
        _delete_uploaded_circle_cover(previous_cover)
    flash("圈子封面已更新。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/post/<int:post_id>/pin", methods=["POST"])
def toggle_pin_post(circle_id, post_id):
    user = _current_user()
    circle = Circle.query.get_or_404(circle_id)
    if not _can_manage_circle(user, circle):
        flash("没有权限置顶圈内帖子。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    post = Post.query.filter_by(id=post_id, circle_id=circle.id, status="published").first()
    if post is None:
        flash("只能置顶当前圈子内正常显示的帖子。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    if circle.pinned_post_id == post.id:
        circle.pinned_post_id = None
        message = "已取消置顶帖子。"
    else:
        circle.pinned_post_id = post.id
        message = "帖子已置顶。"
    db.session.commit()
    flash(message, "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor=f"post-{post.id}"))


@circle_bp.route("/circle/<int:circle_id>/member/<int:user_id>/role", methods=["POST"])
def update_circle_member_role(circle_id, user_id):
    user = _current_user()
    circle = Circle.query.get_or_404(circle_id)
    if not _is_circle_owner(user, circle):
        flash("只有圈主可以设置圈子管理员。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    member = CircleMember.query.filter_by(
        circle_id=circle.id,
        user_id=user_id,
        status="active",
    ).first()
    if member is None:
        flash("只能管理当前圈内成员。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))
    if member.user_id == circle.owner_id:
        flash("圈主身份不能通过管理员设置修改。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    role = request.form.get("role", "").strip()
    if role not in {"moderator", "member"}:
        flash("不支持的圈内角色。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    member.role = role
    db.session.commit()
    flash("圈子管理员设置已更新。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/transfer-owner", methods=["POST"])
def transfer_circle_owner(circle_id):
    user = _current_user()
    circle = Circle.query.get_or_404(circle_id)
    if not _is_circle_owner(user, circle):
        flash("只有圈主可以转移圈主身份。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    target_user_id = request.form.get("user_id", type=int)
    target = CircleMember.query.filter_by(
        circle_id=circle.id,
        user_id=target_user_id,
        status="active",
    ).first()
    if target is None or target.user_id == circle.owner_id:
        flash("请选择其他圈内成员接任圈主。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    previous_owner = CircleMember.query.filter_by(
        circle_id=circle.id,
        user_id=circle.owner_id,
        status="active",
    ).first()
    if previous_owner is not None:
        previous_owner.role = "member"
    target.role = "owner"
    circle.owner_id = target.user_id
    db.session.commit()
    flash("圈主身份已转移。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/<int:circle_id>/post", methods=["GET", "POST"])
def create_post(circle_id):
    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login", next=request.url))

    circle = _get_circle(circle_id)
    if circle is None or not isinstance(circle, Circle):
        flash("圈子不存在或已被删除。", "error")
        return redirect(url_for("circle.circles"))

    if not _can_view_circle(user, circle):
        flash("同好圈不存在或暂不可见。", "error")
        return redirect(url_for("circle.circles"))

    if not _is_member(circle.id, user.id) and not _can_manage_circle(user, circle):
        flash("加入同好圈后才能发帖。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))

    if request.method == "GET":
        return render_template("create_post.html", circle=circle, **_upload_limit_context())

    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    post_type = "discussion"

    if not title or not content:
        flash("标题和内容不能为空。", "error")
        return render_template("create_post.html", circle=circle, **_upload_limit_context())
    if len(title) > 100:
        flash("标题长度不能超过 100 个字符。", "error")
        return render_template("create_post.html", circle=circle, **_upload_limit_context())

    try:
        validated_images = validate_upload_files(
            request.files.getlist("images"),
            "post_images",
        )
        image_paths = save_image_files(validated_images, POST_UPLOAD_SUBDIR)
    except ValueError as exc:
        flash(str(exc), "error")
        return render_template("create_post.html", circle=circle, **_upload_limit_context())

    post = Post(title=title, content=content, type=post_type, user_id=user.id, circle_id=circle.id)
    try:
        db.session.add(post)
        db.session.flush()
        for image_url in image_paths:
            db.session.add(PostImage(post_id=post.id, image_url=image_url))
        db.session.commit()
        flash("帖子发布成功。", "success")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id))
    except Exception:
        db.session.rollback()
        delete_saved_images(image_paths)
        flash("发布失败，请稍后重试。", "error")
        return render_template("create_post.html", circle=circle, **_upload_limit_context())


@circle_bp.route("/circle/<int:circle_id>/post/<int:post_id>/comment", methods=["POST"])
def comment_post(circle_id, post_id):
    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login", next=url_for("circle.circle_detail", circle_id=circle_id)))

    _ensure_circle_image_tables()
    _ensure_post_status_column()
    _ensure_comment_parent_column()
    circle = Circle.query.get_or_404(circle_id)
    if not _can_view_circle(user, circle):
        flash("同好圈不存在或暂不可见。", "error")
        return redirect(url_for("circle.circles"))
    post = Post.query.filter_by(id=post_id, circle_id=circle_id, status="published").first_or_404()
    content = request.form.get("content", "").strip()
    parent_id = request.form.get("parent_id", type=int)
    parent_comment = None
    if parent_id:
        parent_comment = Comment.query.filter_by(
            id=parent_id,
            post_id=post.id,
            status="published",
        ).first()
        if parent_comment is None:
            flash("无法回复不存在或已删除的评论。", "error")
            return redirect(url_for("circle.circle_detail", circle_id=post.circle_id, _anchor=f"post-{post.id}"))

    try:
        validated_images = validate_upload_files(
            request.files.getlist("images"),
            "comment_images",
        )
        image_paths = save_image_files(validated_images, COMMENT_UPLOAD_SUBDIR)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("circle.circle_detail", circle_id=post.circle_id))

    if not content and not image_paths:
        flash("评论内容不能为空。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=post.circle_id))

    comment = Comment(
        author_id=user.id,
        post_id=post.id,
        parent_id=parent_comment.id if parent_comment else None,
        content=content or " ",
    )
    try:
        db.session.add(comment)
        db.session.flush()
        for image_url in image_paths:
            db.session.add(CommentImage(comment_id=comment.id, image_url=image_url))
        db.session.commit()
    except Exception:
        db.session.rollback()
        delete_saved_images(image_paths)
        flash("评论发布失败，请稍后重试。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=post.circle_id))
    flash("回复已发布。" if parent_comment else "评论已发布。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=post.circle_id, _anchor=f"comment-{comment.id}"))


@circle_bp.route("/circle/post/<int:post_id>/delete", methods=["POST"])
def delete_post(post_id):
    user = _current_user()
    if user is None:
        flash("请先登录后再删除内容。", "error")
        return redirect(url_for("auth.login"))

    _ensure_post_status_column()
    post = Post.query.get_or_404(post_id)
    circle = Circle.query.get_or_404(post.circle_id)
    if not _can_manage_circle_content(user, circle, post.user_id):
        flash("没有权限删除该内容。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor=f"post-{post.id}"))

    if circle.pinned_post_id == post.id:
        circle.pinned_post_id = None
    post.status = "deleted"
    db.session.commit()
    flash("帖子已删除。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id))


@circle_bp.route("/circle/post-image/<int:image_id>/delete", methods=["POST"])
def delete_post_image(image_id):
    user = _current_user()
    if user is None:
        flash("请先登录后再删除照片。", "error")
        return redirect(url_for("auth.login"))

    image = PostImage.query.get_or_404(image_id)
    post = Post.query.get_or_404(image.post_id)
    circle = Circle.query.get_or_404(post.circle_id)
    if not _can_manage_circle_content(user, circle, post.user_id):
        flash("你没有权限删除这张照片。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor="circle-photos-title"))

    image_url = image.image_url
    db.session.delete(image)
    db.session.commit()
    delete_saved_images([image_url])
    flash("照片已删除。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor="circle-photos-title"))


@circle_bp.route("/circle/comment/<int:comment_id>/delete", methods=["POST"])
def delete_comment(comment_id):
    user = _current_user()
    if user is None:
        flash("请先登录后再删除内容。", "error")
        return redirect(url_for("auth.login"))

    comment = Comment.query.get_or_404(comment_id)
    post = Post.query.get_or_404(comment.post_id)
    circle = Circle.query.get_or_404(post.circle_id)
    if not _can_manage_circle_content(user, circle, comment.author_id):
        flash("没有权限删除该内容。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor=f"comment-{comment.id}"))

    comment.status = "deleted"
    db.session.commit()
    flash("评论已删除。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle.id, _anchor=f"post-{post.id}"))


@circle_bp.route("/circle/<int:circle_id>/post/<int:post_id>/interact/<action>", methods=["POST"])
def interact_post(circle_id, post_id, action):
    if action not in {"like", "favorite", "share"}:
        flash("不支持的互动类型。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle_id))

    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login", next=url_for("circle.circle_detail", circle_id=circle_id)))

    _ensure_post_status_column()
    circle = Circle.query.get_or_404(circle_id)
    if not _can_view_circle(user, circle):
        flash("同好圈不存在或暂不可见。", "error")
        return redirect(url_for("circle.circles"))
    Post.query.filter_by(id=post_id, circle_id=circle_id, status="published").first_or_404()
    _toggle_interaction(user.id, "post", post_id, action)
    flash("操作已记录。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle_id, _anchor=f"post-{post_id}"))


@circle_bp.route("/circle/<int:circle_id>/comment/<int:comment_id>/interact/<action>", methods=["POST"])
def interact_comment(circle_id, comment_id, action):
    if action not in {"like", "favorite"}:
        flash("不支持的互动类型。", "error")
        return redirect(url_for("circle.circle_detail", circle_id=circle_id))

    user = _current_user()
    if user is None:
        return redirect(url_for("auth.login", next=url_for("circle.circle_detail", circle_id=circle_id)))

    circle = Circle.query.get_or_404(circle_id)
    if not _can_view_circle(user, circle):
        flash("同好圈不存在或暂不可见。", "error")
        return redirect(url_for("circle.circles"))

    comment = (
        Comment.query.join(Post, Comment.post_id == Post.id)
        .filter(
            Comment.id == comment_id,
            Comment.status == "published",
            Post.circle_id == circle_id,
            Post.status == "published",
        )
        .first_or_404()
    )
    _toggle_interaction(user.id, "comment", comment.id, action)
    flash("操作已记录。", "success")
    return redirect(url_for("circle.circle_detail", circle_id=circle_id, _anchor=f"comment-{comment.id}"))
