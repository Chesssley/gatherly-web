import os
import calendar
from collections import defaultdict

from flask import Blueprint, abort, current_app, jsonify, render_template, request, session, redirect, url_for, flash
from functools import wraps
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from app.models import (
    db,
    Activity,
    ActivityFavorite,
    ActivityReview,
    Circle,
    CircleMember,
    CircleRating,
    Comment,
    CommentImage,
    Interaction,
    ProfileVisibility,
    Registration,
    User,
    get_user_display_name,
    is_verified_merchant,
)
from app.services.storage import storage_url
from app.utils.upload_limits import upload_limit
from app.utils.upload_utils import delete_saved_images, save_image_files, validate_upload_files
from app.utils.location_utils import locations_match, normalize_city

def login_required(f):
    """登录态检查装饰器，未登录重定向到登录页"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("请先登录后再报名活动", "error")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


activity_bp = Blueprint("activity", __name__)


RATING_ELIGIBLE_STATUSES = {"registered", "attended", "completed"}
SEARCH_QUERY_MAX_LENGTH = 50
SEARCH_SUGGESTION_LIMIT = 5
SEARCH_RESULT_ACTIVITY_LIMIT = 60
SEARCH_RESULT_LIST_LIMIT = 12
RECENT_CIRCLE_ACTIVITY_LIMIT = 20
NEW_CIRCLE_ACTIVITY_TAG = "新同好圈"
MY_CIRCLE_ACTIVITY_TAG = "来自我的同好圈"
SPECIAL_ACTIVITY_FILTER_TAGS = {NEW_CIRCLE_ACTIVITY_TAG, MY_CIRCLE_ACTIVITY_TAG}
ACTIVITY_CREATE_EXCLUDED_TAGS = SPECIAL_ACTIVITY_FILTER_TAGS
CANCEL_REASON_LABELS = {
    "time_conflict": "时间冲突",
    "venue_issue": "场地问题",
    "insufficient_participants": "人数不足",
    "weather": "天气原因",
    "organizer": "主办方原因",
    "other": "其他",
}
TRUST_SCORE_THRESHOLD = 60
ACTIVITY_IMAGE_LIMIT = upload_limit("activity_cover")
ACTIVITY_IMAGE_UPLOAD_SUBDIR = "activities"
ACTIVITY_CARD_AVATAR_LIMIT = 4
ACTIVITY_ATTENDEE_DISPLAY_LIMIT = 7
COMMENT_IMAGE_LIMIT = upload_limit("comment_images")
COMMENT_UPLOAD_SUBDIR = "comments"
DEFAULT_ACTIVITY_TIMEZONE = "Asia/Shanghai"
CHINESE_WEEKDAYS = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
SHORT_CHINESE_WEEKDAYS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
DISCOVERY_TIME_FILTERS = {"any", "today", "tomorrow", "week", "weekend", "month"}
HOME_GROUP_FEED_FILTERS = ("today", "tomorrow", "week", "future")
HOME_GROUP_FEED_FILTER_LABELS = {
    "today": "今天",
    "tomorrow": "明天",
    "week": "本周",
    "future": "未来",
}
HOME_GROUP_ACTIVITY_LIMIT = 40

OFFICIAL_INTEREST_CATEGORIES = [
    {"icon": "👥", "tag": "新同好圈", "aliases": []},
    {"icon": "🎁", "tag": "来自我的同好圈", "aliases": []},
    {"icon": "🎉", "tag": "社交活动", "aliases": ["咖啡茶饮", "美食烘焙"]},
    {"icon": "🎨", "tag": "兴趣爱好", "aliases": ["影像摄影", "摄影影像", "手作艺术", "咖啡茶饮", "美食烘焙"]},
    {"icon": "⚽", "tag": "运动健身", "aliases": ["运动户外"]},
    {"icon": "🌲", "tag": "旅行与户外", "aliases": ["运动户外", "城市探索"]},
    {"icon": "💼", "tag": "职业与商业", "aliases": []},
    {"icon": "💻", "tag": "科技", "aliases": ["科技数码"]},
    {"icon": "🏙️", "tag": "社区与环境", "aliases": ["城市探索", "公益志愿"]},
    {"icon": "🌐", "tag": "身份与语言", "aliases": []},
    {"icon": "🎮", "tag": "游戏", "aliases": ["游戏桌游"]},
    {"icon": "🎶", "tag": "舞蹈", "aliases": []},
    {"icon": "💗", "tag": "支持与辅导", "aliases": []},
    {"icon": "🎵", "tag": "音乐", "aliases": ["音乐演出"]},
    {"icon": "💜", "tag": "健康与身心", "aliases": []},
    {"icon": "🎭", "tag": "艺术与文化", "aliases": ["影像摄影", "摄影影像", "手作艺术", "观影戏剧", "阅读出版"]},
    {"icon": "🔬", "tag": "科学与教育", "aliases": []},
    {"icon": "🐱", "tag": "宠物与动物", "aliases": []},
    {"icon": "🙏", "tag": "宗教与修养", "aliases": []},
    {"icon": "✍️", "tag": "写作", "aliases": ["阅读出版"]},
    {"icon": "👨‍👩‍👧", "tag": "父母与家庭", "aliases": []},
    {"icon": "🏛️", "tag": "社会运动与政治", "aliases": []},
]
OFFICIAL_INTEREST_TAGS = [category["tag"] for category in OFFICIAL_INTEREST_CATEGORIES]
ACTIVITY_CREATE_INTEREST_CATEGORIES = [
    category
    for category in OFFICIAL_INTEREST_CATEGORIES
    if category["tag"] not in ACTIVITY_CREATE_EXCLUDED_TAGS
]
ACTIVITY_CREATE_INTEREST_TAGS = [
    category["tag"] for category in ACTIVITY_CREATE_INTEREST_CATEGORIES
]
INTEREST_CATEGORY_ALIASES = {
    category["tag"]: [category["tag"], *category.get("aliases", [])]
    for category in OFFICIAL_INTEREST_CATEGORIES
}
LEGACY_INTEREST_TAG_MAP = {
    alias: category["tag"]
    for category in OFFICIAL_INTEREST_CATEGORIES
    for alias in category.get("aliases", [])
}

DEFAULT_ACTIVITY_TAG = "兴趣爱好"


def _canonical_interest_tag(tag):
    if tag in OFFICIAL_INTEREST_TAGS:
        return tag
    return LEGACY_INTEREST_TAG_MAP.get(tag, tag)


def _interest_filter_tags(tag):
    return INTEREST_CATEGORY_ALIASES.get(tag, [tag])


def _available_activity_circles():
    return (
        Circle.query.filter_by(status="active")
        .order_by(Circle.is_system.desc(), Circle.is_pinned.desc(), Circle.name.asc())
        .all()
    )


def _circle_cover_url(circle):
    if not circle:
        return ""
    cover_image = getattr(circle, "cover_image", None)
    if (
        cover_image
        and str(cover_image).startswith(
            (
                "http://",
                "https://",
                "/static/",
                "static/",
                "app/static/",
                "images/circles/",
                "images/circle_covers/",
                "images/placeholders/",
            )
        )
    ):
        return storage_url(cover_image)
    return storage_url("images/placeholders/circle-placeholder.svg")


def _validated_circle_id(raw_circle_id):
    if not raw_circle_id:
        return None
    try:
        circle_id = int(raw_circle_id)
    except (TypeError, ValueError):
        return None
    circle = Circle.query.filter_by(id=circle_id, status="active").first()
    return circle.id if circle else None


def _recent_circle_ids(limit=RECENT_CIRCLE_ACTIVITY_LIMIT):
    order_by = (
        (Circle.created_at.desc(), Circle.id.desc())
        if hasattr(Circle, "created_at")
        else (Circle.id.desc(),)
    )
    return [
        circle.id
        for circle in (
            Circle.query.filter_by(status="active")
            .order_by(*order_by)
            .limit(limit)
            .all()
        )
    ]


def _joined_circle_ids(user_id):
    if not user_id:
        return []
    return [
        row.circle_id
        for row in CircleMember.query.filter_by(user_id=user_id, status="active").all()
    ]


def _empty_activity_query(query):
    return query.filter(Activity.id.is_(None))


def _apply_activity_category_filter(query, selected_category, joined_circle_ids=None):
    if not selected_category:
        return query

    if selected_category == NEW_CIRCLE_ACTIVITY_TAG:
        recent_circle_ids = _recent_circle_ids()
        return (
            query.filter(Activity.circle_id.in_(recent_circle_ids))
            if recent_circle_ids
            else _empty_activity_query(query)
        )

    if selected_category == MY_CIRCLE_ACTIVITY_TAG:
        joined_circle_ids = joined_circle_ids or []
        return (
            query.filter(Activity.circle_id.in_(joined_circle_ids))
            if joined_circle_ids
            else _empty_activity_query(query)
        )

    category_filters = [
        Activity.tags.ilike(f"%{tag}%")
        for tag in _interest_filter_tags(selected_category)
    ]
    return query.filter(or_(*category_filters))


def _activity_empty_message(selected_category):
    if selected_category == NEW_CIRCLE_ACTIVITY_TAG:
        return "最近创建的同好圈暂时还没有关联活动。"
    return None


def _selected_activity_tags():
    primary_tag = _canonical_interest_tag(request.form.get("primary_tag", "").strip())
    selected_tags = []
    if primary_tag in OFFICIAL_INTEREST_TAGS:
        selected_tags.append(primary_tag)
    for tag in request.form.getlist("tags"):
        tag = _canonical_interest_tag(tag)
        if tag in OFFICIAL_INTEREST_TAGS and tag not in selected_tags:
            selected_tags.append(tag)
    return selected_tags


def _selected_create_activity_tags():
    primary_tag = _canonical_interest_tag(request.form.get("primary_tag", "").strip())
    selected_tags = []
    if primary_tag in ACTIVITY_CREATE_INTEREST_TAGS:
        selected_tags.append(primary_tag)
    for tag in request.form.getlist("tags"):
        tag = _canonical_interest_tag(tag)
        if tag in ACTIVITY_CREATE_INTEREST_TAGS and tag not in selected_tags:
            selected_tags.append(tag)
    return selected_tags

def _activity_timezone(activity):
    timezone_name = activity.timezone if activity and activity.timezone else DEFAULT_ACTIVITY_TIMEZONE
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_ACTIVITY_TIMEZONE)


def _activity_now(activity):
    return datetime.now(_activity_timezone(activity)).replace(tzinfo=None)


def _activity_phase(activity, now=None):
    now = now or _activity_now(activity)
    if not activity:
        return "ended"
    if activity.status == "cancelled":
        return "cancelled"
    if activity.status == "closed" or (activity.end_time and now >= activity.end_time):
        return "ended"
    if activity.start_time and now >= activity.start_time:
        return "ongoing"
    return "upcoming"


def _activity_has_ended(activity):
    return _activity_phase(activity) == "ended"


def _format_time_without_leading_zero(value):
    return value.strftime("%I:%M %p").lstrip("0")


def _gmt_offset_label(activity):
    timezone = _activity_timezone(activity)
    offset = activity.start_time.replace(tzinfo=timezone).utcoffset()
    offset_minutes = int(offset.total_seconds() / 60) if offset else 0
    offset_sign = "+" if offset_minutes >= 0 else "-"
    offset_hours, offset_remainder = divmod(abs(offset_minutes), 60)
    gmt_offset = f"GMT{offset_sign}{offset_hours}"
    if offset_remainder:
        gmt_offset += f":{offset_remainder:02d}"
    return gmt_offset


def _format_activity_date_label(value):
    return f"{CHINESE_WEEKDAYS[value.weekday()]}, {value.month}月 {value.day}"


def _format_home_feed_date_label(value):
    if not value:
        return "时间待定"
    today = datetime.now().date()
    activity_date = value.date()
    if activity_date == today:
        return "今天"
    if activity_date == today + timedelta(days=1):
        return "明天"
    return f"{SHORT_CHINESE_WEEKDAYS[value.weekday()]} {value.month}月{value.day}日"


def _normalize_home_group_filter(value):
    return value if value in HOME_GROUP_FEED_FILTERS else "today"


def _home_group_filter_label(value):
    return HOME_GROUP_FEED_FILTER_LABELS.get(
        _normalize_home_group_filter(value),
        HOME_GROUP_FEED_FILTER_LABELS["today"],
    )


def _summary_start_date(activity):
    start_time = activity.get("start_datetime")
    return start_time.date() if start_time else None


def _matches_home_group_filter(activity, selected_filter, today=None):
    today = today or datetime.now().date()
    start_date = _summary_start_date(activity)
    if not start_date:
        return False
    if selected_filter == "today":
        return start_date == today
    if selected_filter == "tomorrow":
        return start_date == today + timedelta(days=1)
    if selected_filter == "week":
        week_end = today + timedelta(days=6 - today.weekday())
        return today <= start_date <= week_end
    if selected_filter == "future":
        return start_date >= today
    return False


def _is_later_home_group_activity(activity, selected_filter, today=None):
    today = today or datetime.now().date()
    start_date = _summary_start_date(activity)
    if not start_date:
        return False
    if selected_filter == "today":
        return start_date > today
    if selected_filter == "tomorrow":
        return start_date > today + timedelta(days=1)
    if selected_filter == "week":
        week_end = today + timedelta(days=6 - today.weekday())
        return start_date > week_end
    if selected_filter == "future":
        return False
    return start_date >= today


def _build_home_group_feed_sections(activities, selected_filter):
    selected_filter = _normalize_home_group_filter(selected_filter)
    today = datetime.now().date()
    ordered_activities = sorted(
        activities,
        key=lambda activity: (
            activity.get("start_datetime") or datetime.max,
            activity.get("id") or 0,
        ),
    )
    selected_activities = [
        activity
        for activity in ordered_activities
        if _matches_home_group_filter(activity, selected_filter, today)
    ]
    sections = [
        {
            "key": selected_filter,
            "label": _home_group_filter_label(selected_filter),
            "is_selected": True,
            "activities": selected_activities,
            "empty_title": f"{_home_group_filter_label(selected_filter)}暂无圈内活动",
            "empty_text": "下方仍会显示你加入的同好圈后续活动。",
        }
    ]
    later_activities = [
        activity
        for activity in ordered_activities
        if activity["id"] not in {item["id"] for item in selected_activities}
        and _is_later_home_group_activity(activity, selected_filter, today)
    ]
    if later_activities:
        sections.append(
            {
                "key": "upcoming",
                "label": "接下来的活动",
                "is_selected": False,
                "activities": later_activities,
                "empty_title": "",
                "empty_text": "",
            }
        )
    return sections


def _home_calendar_payload(today=None):
    today = today or datetime.now().date()
    month_days = calendar.Calendar(firstweekday=6).monthdatescalendar(today.year, today.month)
    tomorrow = today + timedelta(days=1)
    return {
        "label": f"{calendar.month_name[today.month]} {today.year}",
        "year": today.year,
        "month": today.month,
        "selected_date": today.isoformat(),
        "today": today.day,
        "today_date": today.isoformat(),
        "weekdays": ("Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"),
        "weeks": [
            [
                {
                    "day": day.day,
                    "date": day.isoformat(),
                    "is_current_month": day.month == today.month,
                    "is_today": day == today,
                    "is_past": day < today,
                    "display_label": (
                        "今天"
                        if day == today
                        else "明天"
                        if day == tomorrow
                        else f"From {calendar.month_abbr[day.month]} {day.day}"
                    ),
                }
                for day in week
            ]
            for week in month_days
        ],
    }


def _format_activity_sidebar_time(activity):
    if not activity.start_time:
        return "时间待确认"

    gmt_offset = _gmt_offset_label(activity)
    start_label = (
        f"{_format_activity_date_label(activity.start_time)}"
        f" · {_format_time_without_leading_zero(activity.start_time)}"
    )
    if not activity.end_time:
        return f"{start_label} {gmt_offset}"

    end_label = _format_time_without_leading_zero(activity.end_time)
    if activity.end_time.date() != activity.start_time.date():
        end_label = (
            f"{_format_activity_date_label(activity.end_time)}"
            f" · {end_label}"
        )
    return f"{start_label} to {end_label} {gmt_offset}"


def _can_manage_activity(user, activity):
    return bool(
        user
        and activity
        and (user.role == "admin" or activity.organizer_id == user.id)
    )


def _active_registrations_query():
    return Registration.query.filter(Registration.status != "cancelled")


def sync_activity_statuses():
    activities = Activity.query.filter(
        Activity.status.in_({"open", "hidden"}),
        Activity.end_time.isnot(None),
    ).all()
    updated = False
    for activity in activities:
        if _activity_phase(activity) == "ended":
            activity.status = "closed"
            updated = True
    if updated:
        db.session.commit()


@activity_bp.before_app_request
def sync_ended_activities():
    if request.endpoint == "static":
        return
    try:
        sync_activity_statuses()
    except OperationalError:
        db.session.rollback()
        current_app.logger.exception("Activity status sync skipped after database error")


def _is_activity_participant(user_id, activity_id):
    return (
        Registration.query.filter(
            Registration.user_id == user_id,
            Registration.activity_id == activity_id,
            Registration.status.in_(RATING_ELIGIBLE_STATUSES),
        ).first()
        is not None
    )


def _split_tags(tags):
    return [tag.strip() for tag in (tags or "").split(",") if tag.strip()]


def _activity_time_filter(start_time):
    if not start_time:
        return "any"

    today = datetime.now().date()
    activity_date = start_time.date()
    if activity_date == today:
        return "today"
    if activity_date == today + timedelta(days=1):
        return "tomorrow"
    if activity_date.year == today.year and activity_date.month == today.month:
        week_end = today + timedelta(days=6 - today.weekday())
        if today <= activity_date <= week_end:
            return "weekend" if activity_date.weekday() >= 5 else "week"
        return "month"
    return "any"


def _activity_heat_score(activity, registration_count=0, favorite_count=0):
    current_people = (activity.initial_participants or 0) + registration_count
    score = current_people * 3 + favorite_count * 2
    if activity.start_time:
        days_until_start = (activity.start_time.date() - datetime.now().date()).days
        if 0 <= days_until_start <= 7:
            score += 6
        elif days_until_start <= 14 and days_until_start >= 0:
            score += 3
    return score


def _get_activity_attendee_previews(activity_ids):
    previews_by_activity = defaultdict(list)
    if not activity_ids:
        return previews_by_activity

    rows = (
        db.session.query(Registration.activity_id, User)
        .join(User, User.id == Registration.user_id)
        .filter(
            Registration.activity_id.in_(activity_ids),
            Registration.status != "cancelled",
        )
        .order_by(Registration.activity_id.asc(), Registration.register_time.asc())
        .all()
    )
    for activity_id, user in rows:
        previews = previews_by_activity[activity_id]
        if len(previews) >= ACTIVITY_CARD_AVATAR_LIMIT:
            continue
        display_name = get_user_display_name(user).strip() or user.username
        previews.append(
            {
                "avatar": user.avatar,
                "display_name": display_name,
                "initial": display_name[:1].upper(),
            }
        )
    return previews_by_activity


def _get_circle_rating_stats(circle_ids):
    circle_ids = {circle_id for circle_id in circle_ids if circle_id}
    if not circle_ids:
        return {}

    stats = {
        circle_id: {"rating_average": None, "rating_count": 0}
        for circle_id in circle_ids
    }
    rows = (
        db.session.query(
            CircleRating.circle_id,
            func.avg(CircleRating.rating),
            func.count(CircleRating.id),
        )
        .filter(CircleRating.circle_id.in_(circle_ids))
        .group_by(CircleRating.circle_id)
        .all()
    )
    for circle_id, rating_average, rating_count in rows:
        stats[circle_id] = {
            "rating_average": round(float(rating_average), 1) if rating_average is not None else None,
            "rating_count": rating_count,
        }
    return stats


def _get_activity_attendees(activity):
    attendees = []
    if activity.organizer:
        organizer_name = (
            "Gatherly官方"
            if activity.is_official or activity.organizer.role == "admin"
            else get_user_display_name(activity.organizer)
        )
        attendees.append(
            {
                "user": activity.organizer,
                "display_name": organizer_name,
                "role_label": "举办者",
                "is_organizer": True,
            }
        )
    participants = (
        db.session.query(User)
        .join(Registration, Registration.user_id == User.id)
        .filter(
            Registration.activity_id == activity.id,
            Registration.status != "cancelled",
            User.id != activity.organizer_id,
        )
        .order_by(Registration.register_time.asc())
        .all()
    )
    attendees.extend(
        {
            "user": participant,
            "display_name": get_user_display_name(participant),
            "role_label": "参与者",
            "is_organizer": False,
        }
        for participant in participants
    )
    return attendees


def _get_activity_comments(activity_id):
    return (
        Comment.query.filter_by(activity_id=activity_id)
        .order_by(Comment.created_at.asc(), Comment.id.asc())
        .all()
    )


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


def _can_manage_activity_comment(user, activity, author_id):
    return bool(
        user
        and activity
        and (
            user.role == "admin"
            or activity.organizer_id == user.id
            or author_id == user.id
        )
    )


def _build_activity_comment_item(
    comment,
    current_user,
    activity,
    replies_by_parent,
    depth=0,
    include_hidden=False,
):
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
            and _can_manage_activity_comment(current_user, activity, comment.author_id)
        ),
        "replies": [
            _build_activity_comment_item(
                reply,
                current_user,
                activity,
                replies_by_parent,
                depth + 1,
                include_hidden=include_hidden,
            )
            for reply in replies_by_parent.get(comment.id, [])
            if reply.status == "published" or (include_hidden and reply.status == "hidden")
        ],
    }


def _build_activity_comment_threads(comments, current_user, activity, include_hidden=False):
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
                _build_activity_comment_item(
                    comment,
                    current_user,
                    activity,
                    replies_by_parent,
                    include_hidden=include_hidden,
                )
            )

    return root_comments


def _activity_to_summary(
    activity,
    registration_count=0,
    favorite_count=0,
    attendee_previews=None,
    rating_stats=None,
    circle_rating_stats=None,
):
    raw_tags = _split_tags(activity.tags)
    category = _canonical_interest_tag(raw_tags[0]) if raw_tags else DEFAULT_ACTIVITY_TAG
    tags = []
    for tag in raw_tags or [category]:
        for item in (tag, _canonical_interest_tag(tag)):
            if item and item not in tags:
                tags.append(item)
    heat_score = _activity_heat_score(activity, registration_count, favorite_count)
    current_people = (activity.initial_participants or 0) + registration_count
    attendee_previews = attendee_previews or []
    rating_stats = rating_stats or {}
    rating_average = rating_stats.get("rating_average")
    circle_rating_stats = circle_rating_stats or {}
    circle_rating = circle_rating_stats.get(activity.circle_id, {}) if activity.circle_id else {}
    organizer_is_verified = is_verified_merchant(activity.organizer)
    is_gatherly_official = bool(
        activity.is_official or (activity.organizer and activity.organizer.role == "admin")
    )
    return {
        "id": activity.id,
        "title": activity.title,
        "description": activity.description,
        "detail": activity.detail,
        "city": activity.city,
        "location": activity.location,
        "start_datetime": activity.start_time,
        "time": activity.start_time.strftime("%Y-%m-%d %H:%M") if activity.start_time else "时间待定",
        "home_date_label": _format_home_feed_date_label(activity.start_time),
        "end_time": activity.end_time.strftime("%Y-%m-%d %H:%M") if activity.end_time else None,
        "timezone": activity.timezone or DEFAULT_ACTIVITY_TIMEZONE,
        "gmt_offset": _gmt_offset_label(activity) if activity.start_time else "",
        "sidebar_time": _format_activity_sidebar_time(activity),
        "time_filter": _activity_time_filter(activity.start_time),
        "category": category,
        "tags": tags or [category],
        "circle_id": activity.circle_id,
        "circle_name": activity.circle.name if activity.circle else "",
        "circle_cover_url": _circle_cover_url(activity.circle),
        "image_url": activity.image,
        "organizer": (
            "Gatherly官方"
            if is_gatherly_official
            else activity.organizer.nickname or activity.organizer.username
            if activity.organizer
            else "Gatherly官方"
        ),
        "current_people": current_people,
        "attendee_previews": attendee_previews,
        "attendee_remaining_count": max(0, current_people - len(attendee_previews)),
        "favorite_count": favorite_count,
        "rating_average": round(float(rating_average), 1) if rating_average is not None else None,
        "rating_count": rating_stats.get("rating_count", 0),
        "circle_rating_average": circle_rating.get("rating_average"),
        "circle_rating_count": circle_rating.get("rating_count", 0),
        "heat_score": heat_score,
        "is_featured": activity.is_featured,
        "is_official": is_gatherly_official,
        "organizer_is_verified": organizer_is_verified,
        "is_upcoming": _activity_phase(activity) == "upcoming",
        "is_ended": _activity_has_ended(activity),
        "phase": _activity_phase(activity),
        "is_cancelled": activity.status == "cancelled",
        "cancel_reason": activity.cancel_reason,
        "fee": activity.fee,
        "status": activity.status,
        "demo": activity.id <= 7,
        "detail_url": url_for("activity.activity_detail", activity_id=activity.id),
    }


def _sort_same_city_first(activities, user_city):
    normalized_user_city = normalize_city(user_city)
    if not normalized_user_city:
        return activities

    return sorted(
        activities,
        key=lambda activity: (
            0 if locations_match(activity.get("city"), normalized_user_city) else 1,
        ),
    )


def _normalized_search_query(raw_query=None):
    return (raw_query if raw_query is not None else request.args.get("q", "")).strip()[
        :SEARCH_QUERY_MAX_LENGTH
    ]


def _search_pattern(query):
    return f"%{query}%"


def _truncate_text(value, max_length=80):
    value = (value or "").strip()
    if len(value) <= max_length:
        return value
    return f"{value[: max_length - 1]}…"


def _join_subtitle_parts(*parts):
    return " / ".join(str(part).strip() for part in parts if part and str(part).strip())


def _activity_search_query(query_text):
    pattern = _search_pattern(query_text)
    return Activity.query.filter(
        Activity.status == "open",
        or_(
            Activity.title.ilike(pattern),
            Activity.description.ilike(pattern),
            Activity.detail.ilike(pattern),
            Activity.location.ilike(pattern),
            Activity.city.ilike(pattern),
            Activity.tags.ilike(pattern),
        ),
    )


def _circle_search_query(query_text):
    pattern = _search_pattern(query_text)
    return Circle.query.filter(
        Circle.status == "active",
        or_(
            Circle.name.ilike(pattern),
            Circle.description.ilike(pattern),
            Circle.tag.ilike(pattern),
        ),
    )


def _public_user_search_query(query_text):
    pattern = _search_pattern(query_text)
    return (
        User.query.outerjoin(ProfileVisibility, ProfileVisibility.user_id == User.id)
        .filter(
            User.status == "active",
            or_(ProfileVisibility.id.is_(None), ProfileVisibility.profile_scope == "public"),
            or_(
                User.nickname.ilike(pattern),
                User.username.ilike(pattern),
                User.bio.ilike(pattern),
                User.city.ilike(pattern),
            ),
        )
    )


def _safe_search_rows(query, limit):
    try:
        return query.limit(limit).all()
    except SQLAlchemyError:
        db.session.rollback()
        return []


def _activity_suggestion_item(activity):
    time_label = activity.start_time.strftime("%Y-%m-%d %H:%M") if activity.start_time else ""
    place_label = _join_subtitle_parts(activity.city, activity.location)
    tag_label = ", ".join(_split_tags(activity.tags)[:2])
    subtitle = _join_subtitle_parts(time_label, place_label, tag_label)
    return {
        "id": activity.id,
        "title": activity.title,
        "subtitle": subtitle or _truncate_text(activity.description, 64),
        "url": url_for("activity.activity_detail", activity_id=activity.id),
    }


def _circle_suggestion_item(circle):
    subtitle = _join_subtitle_parts(circle.tag, _truncate_text(circle.description, 64))
    return {
        "id": circle.id,
        "title": circle.name,
        "subtitle": subtitle,
        "url": url_for("circle.circle_detail", circle_id=circle.id),
    }


def _user_suggestion_item(user):
    display_name = get_user_display_name(user).strip() or user.username
    subtitle = _join_subtitle_parts(user.city, _truncate_text(user.bio, 64))
    return {
        "id": user.id,
        "title": display_name,
        "subtitle": subtitle or user.username,
        "avatar": user.avatar,
        "url": url_for("profile.view_profile", user_id=user.id),
    }


def _circle_result_item(circle):
    item = _circle_suggestion_item(circle)
    item["member_count"] = circle.member_count
    return item


@activity_bp.route("/search/suggestions")
def search_suggestions():
    query_text = _normalized_search_query()
    empty_payload = {"activities": [], "circles": [], "users": []}
    if not query_text:
        return jsonify(empty_payload)

    activities = _safe_search_rows(
        _activity_search_query(query_text).order_by(Activity.start_time.asc(), Activity.id.desc()),
        SEARCH_SUGGESTION_LIMIT,
    )
    circles = _safe_search_rows(
        _circle_search_query(query_text).order_by(Circle.is_pinned.desc(), Circle.updated_at.desc()),
        SEARCH_SUGGESTION_LIMIT,
    )
    users = _safe_search_rows(
        _public_user_search_query(query_text).order_by(User.created_at.desc(), User.id.desc()),
        SEARCH_SUGGESTION_LIMIT,
    )

    return jsonify(
        {
            "activities": [_activity_suggestion_item(activity) for activity in activities],
            "circles": [_circle_suggestion_item(circle) for circle in circles],
            "users": [_user_suggestion_item(user) for user in users],
        }
    )


@activity_bp.route("/search")
def search():
    query_text = _normalized_search_query()
    city_query = request.args.get("city", "").strip()[:SEARCH_QUERY_MAX_LENGTH]
    browse_all_mode = request.args.get("scope") == "activities"
    selected_category = _canonical_interest_tag(request.args.get("category", "").strip())
    if selected_category not in OFFICIAL_INTEREST_TAGS:
        selected_category = ""
    selected_time = request.args.get("time", "any").strip() or "any"
    if selected_time not in {"any", "today", "tomorrow", "week", "weekend", "month"}:
        selected_time = "any"
    if not query_text and not city_query and not browse_all_mode:
        return redirect(url_for("activity.index"))

    if not query_text:
        activity_query = Activity.query.filter(Activity.status == "open")
    else:
        activity_query = _activity_search_query(query_text)
    if city_query:
        city_pattern = _search_pattern(city_query)
        activity_query = activity_query.filter(
            or_(Activity.city.ilike(city_pattern), Activity.location.ilike(city_pattern))
        )
    activity_query = _apply_activity_category_filter(
        activity_query,
        selected_category,
        _joined_circle_ids(session.get("user_id")),
    )
    db_activities = _safe_search_rows(
        activity_query.order_by(Activity.start_time.asc(), Activity.id.desc()),
        SEARCH_RESULT_ACTIVITY_LIMIT,
    )

    reg_counts = dict(
        db.session.query(Registration.activity_id, func.count(Registration.id))
        .filter(Registration.status != "cancelled")
        .group_by(Registration.activity_id)
        .all()
    )
    favorite_counts = dict(
        db.session.query(ActivityFavorite.activity_id, func.count(ActivityFavorite.id))
        .group_by(ActivityFavorite.activity_id)
        .all()
    )
    attendee_previews = _get_activity_attendee_previews([activity.id for activity in db_activities])
    circle_ratings = _get_circle_rating_stats(activity.circle_id for activity in db_activities)
    activities = [
        _activity_to_summary(
            activity,
            reg_counts.get(activity.id, 0),
            favorite_counts.get(activity.id, 0),
            attendee_previews.get(activity.id, []),
            circle_rating_stats=circle_ratings,
        )
        for activity in db_activities
    ]
    if selected_time != "any":
        activities = [
            activity
            for activity in activities
            if (
                activity["time_filter"] == selected_time
                or (
                    selected_time == "week"
                    and activity["time_filter"] in {"today", "tomorrow", "week", "weekend"}
                )
            )
        ]

    circles = []
    users = []
    if query_text:
        circles = [
            _circle_result_item(circle)
            for circle in _safe_search_rows(
                _circle_search_query(query_text).order_by(Circle.is_pinned.desc(), Circle.updated_at.desc()),
                SEARCH_RESULT_LIST_LIMIT,
            )
        ]
        users = [
            _user_suggestion_item(user)
            for user in _safe_search_rows(
                _public_user_search_query(query_text).order_by(User.created_at.desc(), User.id.desc()),
                SEARCH_RESULT_LIST_LIMIT,
            )
        ]

    favorite_activity_ids = set()
    if "user_id" in session:
        favorite_activity_ids = {
            favorite.activity_id
            for favorite in ActivityFavorite.query.filter_by(user_id=session["user_id"]).all()
        }

    return render_template(
        "index.html",
        search_results_mode=True,
        browse_all_mode=browse_all_mode,
        search_query=query_text,
        search_city=city_query,
        activities=activities,
        circles=circles,
        users=users,
        featured_activities=[],
        categories=OFFICIAL_INTEREST_TAGS,
        expand_tags_by_default=False,
        interest_categories=OFFICIAL_INTEREST_CATEGORIES,
        interest_tags=OFFICIAL_INTEREST_TAGS,
        selected_tag="",
        selected_category=selected_category,
        selected_time=selected_time,
        activity_empty_message=_activity_empty_message(selected_category),
        special_activity_filter_tags=SPECIAL_ACTIVITY_FILTER_TAGS,
        visible_tag_count=len(OFFICIAL_INTEREST_TAGS),
        favorite_activity_ids=favorite_activity_ids,
    )


@activity_bp.route("/")
def index():
    try:
        return _index_impl()
    except OperationalError:
        db.session.rollback()
        current_app.logger.exception("Homepage query failed after database error")
        return _render_homepage_fallback()


def _render_homepage_fallback():
    selected_category = _canonical_interest_tag(
        request.args.get("category", "").strip()
        or request.args.get("tag", "").strip()
    )
    if selected_category not in OFFICIAL_INTEREST_TAGS:
        selected_category = ""
    selected_time = request.args.get("time", "any").strip() or "any"
    if selected_time not in DISCOVERY_TIME_FILTERS:
        selected_time = "any"
    home_group_selected_time = _normalize_home_group_filter(request.args.get("time", "").strip())
    return render_template(
        "index.html",
        activities=[],
        featured_activities=[],
        group_activities=[],
        home_group_feed_sections=[],
        home_group_selected_time=home_group_selected_time,
        home_group_filter_label=_home_group_filter_label(home_group_selected_time),
        home_group_time_filters=[
            {"value": value, "label": _home_group_filter_label(value)}
            for value in HOME_GROUP_FEED_FILTERS
        ],
        home_circles=[],
        home_user_card={
            "display_name": "访客",
            "location": "选择城市 / 地区",
            "avatar": "",
            "initial": "访",
        },
        home_calendar=_home_calendar_payload(),
        sidebar_going_activity=None,
        sidebar_saved_activity=None,
        categories=OFFICIAL_INTEREST_TAGS,
        expand_tags_by_default=False,
        interest_categories=OFFICIAL_INTEREST_CATEGORIES,
        interest_tags=OFFICIAL_INTEREST_TAGS,
        selected_tag=selected_category,
        selected_category=selected_category,
        selected_time=selected_time,
        activity_empty_message=_activity_empty_message(selected_category),
        special_activity_filter_tags=SPECIAL_ACTIVITY_FILTER_TAGS,
        visible_tag_count=len(OFFICIAL_INTEREST_TAGS),
        favorite_activity_ids=set(),
        registered_activity_ids=set(),
    )


def _index_impl():
    selected_category = (
        request.args.get("category", "").strip()
        or request.args.get("tag", "").strip()
    )
    requested_time = request.args.get("time", "any").strip() or "any"
    selected_time = requested_time
    home_group_selected_time = _normalize_home_group_filter(requested_time)
    selected_category = _canonical_interest_tag(selected_category)
    if selected_category not in OFFICIAL_INTEREST_TAGS:
        selected_category = ""
    if selected_time not in DISCOVERY_TIME_FILTERS:
        selected_time = "any"
    interest_tags = OFFICIAL_INTEREST_TAGS
    categories = interest_tags
    visible_tag_count = len(interest_tags)
    featured_db_activities = Activity.query.filter(Activity.status == "open").all()
    current_user = None
    joined_circle_ids = []
    if "user_id" in session:
        current_user = User.query.get(session["user_id"])
        joined_circle_ids = _joined_circle_ids(session["user_id"])
    query = Activity.query
    query = _apply_activity_category_filter(query, selected_category, joined_circle_ids)
    db_activities = query.all()
    reg_counts = dict(
        db.session.query(Registration.activity_id, func.count(Registration.id))
        .filter(Registration.status != "cancelled")
        .group_by(Registration.activity_id)
        .all()
    )
    favorite_counts = dict(
        db.session.query(ActivityFavorite.activity_id, func.count(ActivityFavorite.id))
        .group_by(ActivityFavorite.activity_id)
        .all()
    )
    activity_ratings = {
        activity_id: {
            "rating_average": rating_average,
            "rating_count": rating_count,
        }
        for activity_id, rating_average, rating_count in (
            db.session.query(
                ActivityReview.activity_id,
                func.avg(ActivityReview.average_score),
                func.count(ActivityReview.id),
            )
            .filter(ActivityReview.status == "published")
            .group_by(ActivityReview.activity_id)
            .all()
        )
    }
    activity_circle_ratings = _get_circle_rating_stats(
        activity.circle_id
        for activity in [*featured_db_activities, *db_activities]
        if activity.circle_id
    )
    featured_reg_counts = reg_counts
    featured_favorite_counts = favorite_counts
    featured_attendee_previews = _get_activity_attendee_previews(
        [activity.id for activity in featured_db_activities]
    )
    featured_normalized_activities = [
        _activity_to_summary(
            activity,
            featured_reg_counts.get(activity.id, 0),
            featured_favorite_counts.get(activity.id, 0),
            featured_attendee_previews.get(activity.id, []),
            activity_ratings.get(activity.id),
            activity_circle_ratings,
        )
        for activity in featured_db_activities
    ]
    featured_normalized_activities.sort(
        key=lambda activity: (
            -activity["heat_score"],
            -activity["current_people"],
            activity["time"],
            activity["id"],
        )
    )
    attendee_previews = _get_activity_attendee_previews([activity.id for activity in db_activities])
    normalized_activities = [
        _activity_to_summary(
            activity,
            reg_counts.get(activity.id, 0),
            favorite_counts.get(activity.id, 0),
            attendee_previews.get(activity.id, []),
            activity_ratings.get(activity.id),
            activity_circle_ratings,
        )
        for activity in db_activities
    ]
    normalized_activities.sort(
        key=lambda activity: (
            -activity["heat_score"],
            -activity["current_people"],
            activity["time"],
            activity["id"],
        )
    )
    current_user_city = None
    if current_user:
        current_user_city = current_user.city if current_user else None
    normalized_activities = _sort_same_city_first(normalized_activities, current_user_city)
    hot_activity_ids = {
        activity["id"]
        for activity in normalized_activities[:3]
        if activity["heat_score"] > 0
    }
    for activity in normalized_activities:
        activity["is_hot"] = activity["id"] in hot_activity_ids
    featured_activities = [
        activity
        for activity in featured_normalized_activities
        if activity["status"] == "open" and activity["phase"] in {"upcoming", "ongoing"}
    ]
    featured_activities.sort(
        key=lambda activity: (
            0 if activity["is_featured"] else 1,
            0 if activity["is_official"] or activity["organizer_is_verified"] else 1,
            activity["time"],
            -activity["current_people"],
            -activity["favorite_count"],
            activity["id"],
        )
    )
    featured_activities = featured_activities[:12]

    filtered_activities = [
        activity for activity in normalized_activities if activity["status"] == "open"
    ]
    if selected_time != "any":
        filtered_activities = [
            activity
            for activity in filtered_activities
            if (
                activity["time_filter"] == selected_time
                or (
                    selected_time == "week"
                    and activity["time_filter"] in {"today", "tomorrow", "week", "weekend"}
                )
            )
        ]

    expand_tags_by_default = (
        bool(selected_category)
        and interest_tags.index(selected_category) >= visible_tag_count
    )

    favorite_activity_ids = set()
    registered_activity_ids = set()
    favorite_rows = []
    registered_rows = []
    if "user_id" in session:
        user_id = session["user_id"]
        favorite_rows = (
            ActivityFavorite.query.filter_by(user_id=user_id)
            .order_by(ActivityFavorite.created_at.desc())
            .all()
        )
        registered_rows = (
            Registration.query.filter(
                Registration.user_id == user_id,
                Registration.status != "cancelled",
            )
            .order_by(Registration.register_time.desc())
            .all()
        )

        favorite_activity_ids = {favorite.activity_id for favorite in favorite_rows}
        registered_activity_ids = {registration.activity_id for registration in registered_rows}

    circle_activity_counts = dict(
        db.session.query(Activity.circle_id, func.count(Activity.id))
        .filter(Activity.status == "open", Activity.circle_id.isnot(None))
        .group_by(Activity.circle_id)
        .all()
    )
    has_joined_circles = bool(joined_circle_ids)
    circle_query = Circle.query.filter_by(status="active")
    if joined_circle_ids:
        joined_circles = (
            circle_query.filter(Circle.id.in_(joined_circle_ids))
            .order_by(Circle.is_pinned.desc(), Circle.updated_at.desc(), Circle.id.desc())
            .limit(4)
            .all()
        )
    else:
        joined_circles = []
    home_circles = [
        {
            "id": circle.id,
            "name": circle.name,
            "tag": circle.tag,
            "description": _truncate_text(circle.description, 54),
            "cover_url": storage_url(
                circle.cover_image
                if circle.cover_image
                and circle.cover_image.startswith(
                    (
                        "http://",
                        "https://",
                        "/static/uploads/circles/",
                        "images/circles/",
                        "images/circle_covers/",
                        "images/placeholders/",
                    )
                )
                else "images/placeholders/circle-placeholder.svg"
            ),
            "member_count": circle.member_count,
            "activity_count": circle_activity_counts.get(circle.id, 0),
            "is_joined": circle.id in joined_circle_ids,
            "url": url_for("circle.circle_detail", circle_id=circle.id),
        }
        for circle in joined_circles
    ]

    group_db_activities = []
    if joined_circle_ids:
        group_db_activities = (
            Activity.query.filter(
                Activity.status == "open",
                Activity.circle_id.in_(joined_circle_ids),
                Activity.start_time.isnot(None),
            )
            .order_by(Activity.start_time.asc(), Activity.id.desc())
            .limit(HOME_GROUP_ACTIVITY_LIMIT)
            .all()
        )
    normalized_by_id = {activity["id"]: activity for activity in featured_normalized_activities}
    group_activities = [
        normalized_by_id[activity.id]
        for activity in group_db_activities
        if activity.id in normalized_by_id
        and normalized_by_id[activity.id]["phase"] in {"upcoming", "ongoing"}
    ]
    group_activities.sort(
        key=lambda activity: (
            activity.get("start_datetime") or datetime.max,
            activity.get("id") or 0,
        )
    )
    home_group_feed_sections = _build_home_group_feed_sections(
        group_activities,
        home_group_selected_time,
    )
    sidebar_going_activity = None
    sidebar_saved_activity = None
    if current_user:
        now = datetime.now()
        inactive_statuses = ("cancelled", "closed", "ended", "completed", "expired", "deleted")
        sidebar_going_db_activity = (
            Activity.query.join(Registration, Registration.activity_id == Activity.id)
            .filter(
                Registration.user_id == current_user.id,
                Registration.status == "registered",
                Activity.start_time.isnot(None),
                Activity.start_time > now,
                Activity.status.notin_(inactive_statuses),
            )
            .order_by(Activity.start_time.asc(), Activity.id.desc())
            .first()
        )
        sidebar_saved_db_activity = (
            Activity.query.join(ActivityFavorite, ActivityFavorite.activity_id == Activity.id)
            .filter(
                ActivityFavorite.user_id == current_user.id,
                Activity.status != "deleted",
            )
            .order_by(ActivityFavorite.created_at.desc(), Activity.id.desc())
            .first()
        )
        if sidebar_going_db_activity:
            sidebar_going_activity = _activity_to_summary(
                sidebar_going_db_activity,
                reg_counts.get(sidebar_going_db_activity.id, 0),
                favorite_counts.get(sidebar_going_db_activity.id, 0),
                featured_attendee_previews.get(sidebar_going_db_activity.id, []),
                activity_ratings.get(sidebar_going_db_activity.id),
                activity_circle_ratings,
            )
        if sidebar_saved_db_activity:
            sidebar_saved_activity = _activity_to_summary(
                sidebar_saved_db_activity,
                reg_counts.get(sidebar_saved_db_activity.id, 0),
                favorite_counts.get(sidebar_saved_db_activity.id, 0),
                featured_attendee_previews.get(sidebar_saved_db_activity.id, []),
                activity_ratings.get(sidebar_saved_db_activity.id),
                activity_circle_ratings,
            )
    user_display_name = get_user_display_name(current_user).strip() if current_user else "访客"
    home_user_card = {
        "display_name": user_display_name or (current_user.username if current_user else "访客"),
        "location": current_user.city if current_user and current_user.city else "选择城市 / 地区",
        "avatar": current_user.avatar if current_user else "",
        "initial": (user_display_name or "访")[:1].upper(),
    }

    return render_template(
        "index.html",
        activities=filtered_activities,
        featured_activities=featured_activities,
        group_activities=group_activities,
        home_group_feed_sections=home_group_feed_sections,
        home_group_selected_time=home_group_selected_time,
        home_group_filter_label=_home_group_filter_label(home_group_selected_time),
        home_group_time_filters=[
            {"value": value, "label": _home_group_filter_label(value)}
            for value in HOME_GROUP_FEED_FILTERS
        ],
        home_circles=home_circles,
        has_joined_circles=has_joined_circles,
        home_user_card=home_user_card,
        home_calendar=_home_calendar_payload(),
        sidebar_going_activity=sidebar_going_activity,
        sidebar_saved_activity=sidebar_saved_activity,
        categories=categories,
        expand_tags_by_default=expand_tags_by_default,
        interest_categories=OFFICIAL_INTEREST_CATEGORIES,
        interest_tags=interest_tags,
        selected_tag=selected_category,
        selected_category=selected_category,
        selected_time=selected_time,
        activity_empty_message=_activity_empty_message(selected_category),
        special_activity_filter_tags=SPECIAL_ACTIVITY_FILTER_TAGS,
        visible_tag_count=visible_tag_count,
        favorite_activity_ids=favorite_activity_ids,
        registered_activity_ids=registered_activity_ids,
    )


@activity_bp.route("/my-events")
@login_required
def my_events():
    user_id = session["user_id"]
    active_tab = request.args.get("tab", "joined")
    tab_labels = {
        "created": "我创建的活动",
        "joined": "我报名的活动",
        "saved": "我收藏的活动",
    }
    if active_tab not in tab_labels:
        active_tab = "joined"

    active_status = request.args.get("status", "all")
    status_labels = {
        "all": "全部",
        "upcoming": "即将开始",
        "ended": "已结束",
    }
    if active_status not in status_labels:
        active_status = "all"

    search_query = request.args.get("q", "").strip()

    if active_tab == "created":
        current_user = User.query.get(user_id)
        query = Activity.query.filter(
            or_(
                Activity.organizer_id == user_id,
                and_(current_user.role == "admin", Activity.is_official.is_(True)),
            )
        )
    elif active_tab == "saved":
        query = (
            Activity.query.join(
                ActivityFavorite,
                ActivityFavorite.activity_id == Activity.id,
            )
            .filter(ActivityFavorite.user_id == user_id)
        )
    else:
        query = (
            Activity.query.join(
                Registration,
                Registration.activity_id == Activity.id,
            )
            .filter(Registration.user_id == user_id)
            .filter(Registration.status != "cancelled")
            .distinct()
        )

    now = datetime.now()
    inactive_statuses = ("closed", "cancelled", "ended", "completed", "expired")
    ended_filter = or_(
        Activity.status.in_(inactive_statuses),
        and_(Activity.end_time.isnot(None), Activity.end_time <= now),
        and_(
            Activity.end_time.is_(None),
            Activity.start_time.isnot(None),
            Activity.start_time <= now,
        ),
    )
    if active_status == "upcoming":
        query = query.filter(
            Activity.status.notin_(inactive_statuses),
            Activity.start_time.isnot(None),
            Activity.start_time > now,
        )
        ordering = (Activity.start_time.asc(), Activity.id.desc())
    elif active_status == "ended":
        query = query.filter(ended_filter)
        ordering = (Activity.start_time.desc(), Activity.id.desc())
    else:
        ordering = (Activity.start_time.desc(), Activity.id.desc())

    if search_query:
        query = query.filter(Activity.title.ilike(f"%{search_query}%"))

    db_activities = query.order_by(*ordering).all()
    activity_ids = [activity.id for activity in db_activities]
    reg_counts = {}
    if activity_ids:
        reg_counts = dict(
            db.session.query(Registration.activity_id, func.count(Registration.id))
            .filter(Registration.activity_id.in_(activity_ids))
            .filter(Registration.status != "cancelled")
            .group_by(Registration.activity_id)
            .all()
        )

    circle_ratings = _get_circle_rating_stats(activity.circle_id for activity in db_activities)
    activities = [
        _activity_to_summary(
            activity,
            reg_counts.get(activity.id, 0),
            circle_rating_stats=circle_ratings,
        )
        for activity in db_activities
    ]
    return render_template(
        "my_events.html",
        active_tab=active_tab,
        active_status=active_status,
        search_query=search_query,
        activities=activities,
        tab_labels=tab_labels,
        status_labels=status_labels,
    )


@activity_bp.route("/activity/<int:activity_id>")
def activity_detail(activity_id):
    db_activity = Activity.query.get_or_404(activity_id)
    registration_rows_count = _active_registrations_query().filter_by(activity_id=activity_id).count()
    registration_count = (db_activity.initial_participants or 0) + registration_rows_count
    circle_ratings = _get_circle_rating_stats([db_activity.circle_id])
    activity = _activity_to_summary(
        db_activity,
        registration_rows_count,
        circle_rating_stats=circle_ratings,
    )
    if db_activity is None:
        abort(404)
    max_participants = (
        db_activity.max_participants
        if db_activity.max_participants and db_activity.max_participants > 0
        else None
    )
    preparation = db_activity.preparation
    attendees = _get_activity_attendees(db_activity)
    current_user = User.query.get(session["user_id"]) if "user_id" in session else None
    comments = _get_activity_comments(activity_id)
    include_hidden_comments = bool(current_user and current_user.role == "admin")
    visible_comment_count = sum(
        comment.status == "published"
        or (include_hidden_comments and comment.status == "hidden")
        for comment in comments
    )
    comment_threads = _build_activity_comment_threads(
        comments,
        current_user,
        db_activity,
        include_hidden=include_hidden_comments,
    )

    user_registered = False
    is_favorited = False
    user_attended = False

    if "user_id" in session:
        is_favorited = ActivityFavorite.query.filter_by(
            user_id=session["user_id"], activity_id=activity_id
        ).first() is not None
        registration = Registration.query.filter_by(
            user_id=session["user_id"], activity_id=activity_id
        ).first()
        user_registered = registration is not None and registration.status != "cancelled"
        user_attended = (
            registration is not None
            and registration.status in RATING_ELIGIBLE_STATUSES
        )

    can_manage_activity = _can_manage_activity(current_user, db_activity)
    activity_phase = _activity_phase(db_activity)
    is_cancel_action = activity_phase == "upcoming"
    can_cancel_registration = bool(
        user_registered
        and current_user
        and current_user.id != db_activity.organizer_id
        and db_activity.status == "open"
        and db_activity.start_time
        and _activity_now(db_activity) < db_activity.start_time
    )

    return render_template(
        "activity_detail.html",
        activity=activity,
        registration_count=registration_count,
        max_participants=max_participants,
        preparation=preparation,
        user_registered=user_registered,
        is_favorited=is_favorited,
        can_manage_activity=can_manage_activity,
        is_cancel_action=is_cancel_action,
        can_cancel_registration=can_cancel_registration,
        cancel_reason_labels=CANCEL_REASON_LABELS,
        activity_circles=_available_activity_circles(),
        interest_categories=OFFICIAL_INTEREST_CATEGORIES,
        interest_tags=OFFICIAL_INTEREST_TAGS,
        activity_phase=activity_phase,
        attendees=attendees[:ACTIVITY_ATTENDEE_DISPLAY_LIMIT],
        attendee_overflow_count=max(0, len(attendees) - ACTIVITY_ATTENDEE_DISPLAY_LIMIT),
        comments=comment_threads,
        comment_count=visible_comment_count,
        comment_image_limit=COMMENT_IMAGE_LIMIT,
        current_user=current_user,
    )


@activity_bp.route("/activity/<int:activity_id>/close", methods=["POST"])
@login_required
def close_activity(activity_id):
    db_activity = Activity.query.get_or_404(activity_id)
    current_user = User.query.get(session["user_id"])
    if not _can_manage_activity(current_user, db_activity):
        abort(403)

    if db_activity.status in {"closed", "cancelled"}:
        flash("活动已经结束或取消，无需重复操作。", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    now = _activity_now(db_activity)
    is_cancel_action = bool(db_activity.start_time and now < db_activity.start_time)
    if is_cancel_action:
        cancel_reason = request.form.get("cancel_reason", "").strip()
        custom_reason = request.form.get("custom_reason", "").strip()
        if cancel_reason not in CANCEL_REASON_LABELS:
            flash("请选择取消活动的理由。", "error")
            return redirect(url_for("activity.activity_detail", activity_id=activity_id))
        if cancel_reason == "other" and not custom_reason:
            flash("选择“其他”时，请填写自定义取消理由。", "error")
            return redirect(url_for("activity.activity_detail", activity_id=activity_id))
        if len(custom_reason) > 300:
            flash("自定义取消理由不能超过 300 个字符。", "error")
            return redirect(url_for("activity.activity_detail", activity_id=activity_id))

        reason_label = CANCEL_REASON_LABELS[cancel_reason]
        db_activity.status = "cancelled"
        db_activity.cancel_reason = (
            f"{reason_label}：{custom_reason}" if cancel_reason == "other" else reason_label
        )
        db_activity.cancelled_at = now
        success_message = "活动已取消。"
        redirect_anchor = None
    else:
        db_activity.status = "closed"
        success_message = "活动已结束，可以前往评论区域。"
        redirect_anchor = "activity-comments"

    db.session.commit()
    flash(success_message, "success")
    return redirect(
        url_for(
            "activity.activity_detail",
            activity_id=activity_id,
            _anchor=redirect_anchor,
        )
    )


@activity_bp.route("/activity/<int:activity_id>/favorite", methods=["POST"])
def toggle_activity_favorite(activity_id):
    if "user_id" not in session:
        return jsonify(
            {
                "error": "login_required",
                "login_url": url_for(
                    "activity.index",
                    auth="login",
                    next=url_for("activity.activity_detail", activity_id=activity_id),
                ),
            }
        ), 401

    Activity.query.get_or_404(activity_id)

    favorite = ActivityFavorite.query.filter_by(
        user_id=session["user_id"],
        activity_id=activity_id,
    ).first()
    if favorite is not None:
        db.session.delete(favorite)
        is_favorited = False
    else:
        db.session.add(
            ActivityFavorite(
                user_id=session["user_id"],
                activity_id=activity_id,
            )
        )
        is_favorited = True

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        is_favorited = True

    return jsonify({"is_favorited": is_favorited})


@activity_bp.route("/activities/create", methods=["GET", "POST"])
@login_required  # 登录校验
def create_activity():
    current_user = User.query.get(session["user_id"])
    can_publish_verified_activity = bool(
        current_user
        and (current_user.role == "admin" or is_verified_merchant(current_user))
    )
    if (
        current_user
        and current_user.role != "admin"
        and current_user.trust_score < TRUST_SCORE_THRESHOLD
    ):
        flash("Your trust score is below 60, so you cannot create activities yet.", "error")
        return redirect(url_for("activity.index"))

    if request.method == "GET":
        return render_template(
            "activity_create.html",
            interest_categories=ACTIVITY_CREATE_INTEREST_CATEGORIES,
            interest_tags=ACTIVITY_CREATE_INTEREST_TAGS,
            circles=_available_activity_circles(),
            can_publish_verified_activity=can_publish_verified_activity,
            activity_image_limit=ACTIVITY_IMAGE_LIMIT,
        )

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    detail = request.form.get("detail", "").strip()
    city = request.form.get("city", "").strip()
    location = request.form.get("location", "").strip()
    preparation = request.form.get("preparation", "").strip()
    timezone = request.form.get("timezone", "").strip() or DEFAULT_ACTIVITY_TIMEZONE
    if len(timezone) > 80 or not all(
        character.isalnum() or character in "_-/+" for character in timezone
    ):
        timezone = DEFAULT_ACTIVITY_TIMEZONE
    tags = _selected_create_activity_tags()
    circle_id = _validated_circle_id(request.form.get("circle_id"))
    errors = []
    wants_official = current_user.role == "admin" or request.form.get("is_official") == "1"
    wants_featured = request.form.get("is_featured") == "1"
    if (wants_official or wants_featured) and not can_publish_verified_activity:
        errors.append("只有已通过认证的商家才能发布官方认证或优质活动。")

    try:
        start_time = datetime.fromisoformat(request.form.get("start_time", ""))
        if start_time <= datetime.now():
            errors.append("活动时间必须晚于当前时间。")
    except ValueError:
        start_time = None
        errors.append("请选择有效的活动时间。")

    try:
        end_time = datetime.fromisoformat(request.form.get("end_time", ""))
        if start_time and end_time <= start_time:
            errors.append("活动结束时间必须晚于开始时间。")
    except ValueError:
        end_time = None
        errors.append("请选择有效的活动结束时间。")

    try:
        max_participants = int(request.form.get("max_participants", ""))
        if max_participants < 0:
            raise ValueError
    except ValueError:
        max_participants = None
        errors.append("人数上限必须是大于等于 0 的整数。")

    try:
        fee = float(request.form.get("fee", ""))
        if fee < 0:
            raise ValueError
    except ValueError:
        fee = None
        errors.append("费用必须是大于等于 0 的数字。")

    if not title:
        errors.append("请填写活动标题。")
    if not description:
        errors.append("请填写活动简介。")
    if not detail:
        errors.append("请填写活动详情。")
    if not city:
        errors.append("请填写城市或地区。")
    if not location:
        errors.append("请填写详细地点。")
    if not tags:
        errors.append("请至少选择一个兴趣标签。")
    if not preparation:
        errors.append("请填写准备事项。")

    validated_images = []
    try:
        validated_images = validate_upload_files(
            [request.files.get("image")],
            "activity_cover",
        )
        if not validated_images:
            errors.append("请上传一张活动图片。")
    except ValueError as exc:
        errors.append(str(exc))

    if errors:
        for error in errors:
            flash(error, "error")
        return render_template(
            "activity_create.html",
            interest_categories=ACTIVITY_CREATE_INTEREST_CATEGORIES,
            interest_tags=ACTIVITY_CREATE_INTEREST_TAGS,
            circles=_available_activity_circles(),
            can_publish_verified_activity=can_publish_verified_activity,
            activity_image_limit=ACTIVITY_IMAGE_LIMIT,
        ), 400

    saved_paths = []
    try:
        saved_paths = save_image_files(validated_images, ACTIVITY_IMAGE_UPLOAD_SUBDIR)
        activity = Activity(
            title=title,
            description=description,
            detail=detail,
            city=city,
            location=location,
            start_time=start_time,
            end_time=end_time,
            timezone=timezone,
            max_participants=max_participants,
            initial_participants=0,
            image=saved_paths[0],
            fee=fee,
            tags=",".join(tags),
            circle_id=circle_id,
            preparation=preparation,
            organizer_id=current_user.id,
            is_official=wants_official,
            is_featured=wants_featured,
        )
        db.session.add(activity)
        db.session.flush()
        existing_registration = Registration.query.filter_by(
            user_id=current_user.id,
            activity_id=activity.id,
        ).first()
        if not existing_registration:
            db.session.add(
                Registration(
                    user_id=current_user.id,
                    activity_id=activity.id,
                    register_time=datetime.now(),
                )
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
        delete_saved_images(saved_paths)
        flash("活动发布失败，请稍后重试。", "error")
        return render_template(
            "activity_create.html",
            interest_categories=ACTIVITY_CREATE_INTEREST_CATEGORIES,
            interest_tags=ACTIVITY_CREATE_INTEREST_TAGS,
            circles=_available_activity_circles(),
            can_publish_verified_activity=can_publish_verified_activity,
            activity_image_limit=ACTIVITY_IMAGE_LIMIT,
        ), 500

    flash("活动发布成功。", "success")
    return redirect(url_for("activity.activity_detail", activity_id=activity.id))


@activity_bp.route("/activity/<int:activity_id>/settings", methods=["POST"])
@login_required
def update_activity_settings(activity_id):
    db_activity = Activity.query.get_or_404(activity_id)
    current_user = User.query.get(session["user_id"])
    if not _can_manage_activity(current_user, db_activity):
        abort(403)

    tags = _selected_activity_tags()
    if not tags:
        flash("请选择一个兴趣探索分类。", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    db_activity.tags = ",".join(tags)
    db_activity.circle_id = _validated_circle_id(request.form.get("circle_id"))
    db.session.commit()
    flash("活动关联信息已更新。", "success")
    return redirect(url_for("activity.activity_detail", activity_id=activity_id))
@activity_bp.route("/activity/<int:activity_id>/register", methods=["POST"])
def register_activity(activity_id):
    """活动报名路由"""
    # 检查用户是否登录，未登录则重定向到登录页并带上next参数
    if "user_id" not in session:
        flash("请先登录后再报名活动", "error")
        next_url = url_for("activity.activity_detail", activity_id=activity_id)
        return redirect(url_for("auth.login", next=next_url))

    db_activity = Activity.query.get_or_404(activity_id)

    user_id = session["user_id"]

    if db_activity.status != "open":
        flash("该活动当前不可报名。", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    # ===== US-05-03：重复报名检查 =====
    existing = Registration.query.filter_by(user_id=user_id, activity_id=activity_id).first()
    if existing and existing.status != "cancelled":
        flash("您已报名该活动，无需重复报名", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    # 检查活动是否已过期
    if db_activity.start_time and db_activity.start_time < _activity_now(db_activity):
        flash("该活动已过期，无法报名", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    # 检查是否已满员
    if db_activity.max_participants and db_activity.max_participants > 0:
        current_count = (
            (db_activity.initial_participants or 0)
            + _active_registrations_query().filter_by(activity_id=activity_id).count()
        )
        if current_count >= db_activity.max_participants:
            flash("该活动已满员，无法报名", "error")
            return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    # 创建报名记录
    if existing:
        existing.status = "registered"
        existing.cancel_reason = None
        existing.cancelled_at = None
        existing.register_time = datetime.now()
        new_registration = existing
    else:
        new_registration = Registration(
            user_id=user_id,
            activity_id=activity_id,
            register_time=datetime.now(),
        )

    try:
        db.session.add(new_registration)
        db.session.commit()
        flash("报名成功！", "success")
    except Exception as e:
        db.session.rollback()
        flash("报名失败，请稍后重试", "error")

    return redirect(url_for("activity.activity_detail", activity_id=activity_id))


@activity_bp.route("/activity/<int:activity_id>/comments", methods=["POST"])
def comment_activity(activity_id):
    Activity.query.get_or_404(activity_id)
    if "user_id" not in session:
        return redirect(url_for("auth.login", next=url_for("activity.activity_detail", activity_id=activity_id)))

    content = request.form.get("content", "").strip()
    parent_id = request.form.get("parent_id", type=int)
    parent_comment = None
    if parent_id:
        parent_comment = Comment.query.filter_by(
            id=parent_id,
            activity_id=activity_id,
            status="published",
        ).first()
        if parent_comment is None:
            flash("无法回复不存在或已删除的评论。", "error")
            return redirect(url_for("activity.activity_detail", activity_id=activity_id, _anchor="activity-comments"))

    try:
        validated_images = validate_upload_files(
            request.files.getlist("images"),
            "comment_images",
        )
        image_paths = save_image_files(validated_images, COMMENT_UPLOAD_SUBDIR)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id, _anchor="activity-comments"))

    if not content and not image_paths:
        flash("评论内容不能为空。", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id, _anchor="activity-comments"))

    if len(content) > 1000:
        flash("评论内容不能超过 1000 个字符。", "error")
        delete_saved_images(image_paths)
        return redirect(url_for("activity.activity_detail", activity_id=activity_id, _anchor="activity-comments"))

    comment = Comment(
        author_id=session["user_id"],
        activity_id=activity_id,
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
        return redirect(url_for("activity.activity_detail", activity_id=activity_id, _anchor="activity-comments"))

    flash("回复已发布。" if parent_comment else "评论已发布。", "success")
    return redirect(url_for("activity.activity_detail", activity_id=activity_id, _anchor=f"comment-{comment.id}"))


@activity_bp.route("/activity/comment/<int:comment_id>/delete", methods=["POST"])
def delete_activity_comment(comment_id):
    if "user_id" not in session:
        flash("请先登录后再删除内容。", "error")
        return redirect(url_for("auth.login"))

    comment = Comment.query.get_or_404(comment_id)
    if not comment.activity_id:
        abort(404)
    db_activity = Activity.query.get_or_404(comment.activity_id)
    current_user = User.query.get(session["user_id"])
    if not _can_manage_activity_comment(current_user, db_activity, comment.author_id):
        flash("没有权限删除该内容。", "error")
        return redirect(url_for("activity.activity_detail", activity_id=db_activity.id, _anchor=f"comment-{comment.id}"))

    comment.status = "deleted"
    db.session.commit()
    flash("评论已删除。", "success")
    return redirect(url_for("activity.activity_detail", activity_id=db_activity.id, _anchor="activity-comments"))


@activity_bp.route("/activity/<int:activity_id>/comment/<int:comment_id>/interact/<action>", methods=["POST"])
def interact_activity_comment(activity_id, comment_id, action):
    if action not in {"like", "favorite"}:
        flash("不支持的互动类型。", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))
    if "user_id" not in session:
        return redirect(url_for("auth.login", next=url_for("activity.activity_detail", activity_id=activity_id)))

    Activity.query.get_or_404(activity_id)
    comment = Comment.query.filter_by(
        id=comment_id,
        activity_id=activity_id,
        status="published",
    ).first_or_404()
    _toggle_interaction(session["user_id"], "comment", comment.id, action)
    flash("操作已记录。", "success")
    return redirect(url_for("activity.activity_detail", activity_id=activity_id, _anchor=f"comment-{comment.id}"))


@activity_bp.route("/activity/<int:activity_id>/registration/cancel", methods=["POST"])
@login_required
def cancel_registration(activity_id):
    db_activity = Activity.query.get_or_404(activity_id)
    now = _activity_now(db_activity)
    if db_activity.organizer_id == session["user_id"]:
        flash("活动创建者不能取消自己的报名。", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))
    if not db_activity.start_time or now >= db_activity.start_time:
        flash("活动已开始，不能取消报名。", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    registration = Registration.query.filter_by(
        user_id=session["user_id"],
        activity_id=activity_id,
    ).first()
    if not registration or registration.status == "cancelled":
        flash("当前没有可取消的报名记录。", "error")
        return redirect(url_for("activity.activity_detail", activity_id=activity_id))

    registration.status = "cancelled"
    registration.cancel_reason = "user_cancelled"
    registration.cancelled_at = now
    db.session.commit()
    flash("报名已取消。", "success")
    return redirect(url_for("activity.activity_detail", activity_id=activity_id))
