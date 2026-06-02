from functools import wraps
import os
from urllib.parse import urlencode
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import and_, or_, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.models import (
    Activity,
    ActivityFavorite,
    Circle,
    CircleMember,
    Comment,
    Interaction,
    MerchantVerification,
    Post,
    ProfileVisibility,
    Registration,
    User,
    UserFollow,
    UserReview,
    db,
    get_user_display_name,
)
from app.utils.location_utils import locations_match, update_user_detected_location

profile_bp = Blueprint("profile", __name__, url_prefix="/profile")

PUBLIC_SCOPE = "public"
PRIVATE_SCOPE = "private"
SORT_OPTIONS = {"newest", "oldest"}
BIO_MAX_LENGTH = 300
INTERESTS_MAX_LENGTH = 500
AVATAR_UPLOAD_SUBDIR = os.path.join("uploads", "avatars")
AVATAR_MAX_BYTES = 700 * 1024
AVATAR_ALLOWED_TYPES = {
    "image/jpeg": ("jpg", b"\xff\xd8\xff"),
    "image/webp": ("webp", b"RIFF"),
}
UNKNOWN_LOCATION_LABELS = {"未知地区"}


def _section_filters(prefix):
    return {
        "q": request.args.get(f"{prefix}_q", "").strip(),
        "status": request.args.get(f"{prefix}_status", "").strip(),
        "type": request.args.get(f"{prefix}_type", "").strip(),
        "sort": request.args.get(f"{prefix}_sort", "newest").strip()
        if request.args.get(f"{prefix}_sort", "newest").strip() in SORT_OPTIONS
        else "newest",
    }


def _section_reset_url(prefix, anchor):
    filtered_args = [
        (key, value)
        for key, value in request.args.items(multi=True)
        if not key.startswith(f"{prefix}_")
    ]
    query_string = urlencode(filtered_args)
    anchor_suffix = f"#{anchor}" if anchor else ""
    return f"{request.path}{f'?{query_string}' if query_string else ''}{anchor_suffix}"


def _ordered_items(items, sort):
    return sorted(
        items,
        key=lambda item: item.get("time") or item.get("created_at"),
        reverse=sort != "oldest",
    )


def _empty_filters():
    return {"q": "", "status": "", "type": "", "sort": "newest"}


def _preview_items(items, limit=3):
    return items[:limit]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login", next=request.url))
        return view(*args, **kwargs)

    return wrapped


def _ensure_visibility_columns():
    if db.engine.dialect.name != "sqlite":
        return

    rows = db.session.execute(text("PRAGMA table_info(profile_visibility)")).fetchall()
    existing_columns = {row[1] for row in rows}
    statements = []
    if "show_interests" not in existing_columns:
        statements.append("ALTER TABLE profile_visibility ADD COLUMN show_interests BOOLEAN NOT NULL DEFAULT 1")
    if "show_interactions" not in existing_columns:
        statements.append("ALTER TABLE profile_visibility ADD COLUMN show_interactions BOOLEAN NOT NULL DEFAULT 1")

    for statement in statements:
        db.session.execute(text(statement))
    if statements:
        db.session.commit()


def _get_or_create_visibility(user):
    try:
        _ensure_visibility_columns()
        visibility = user.profile_visibility
    except OperationalError:
        db.session.rollback()
        visibility = None

    if visibility is None:
        visibility = ProfileVisibility(user_id=user.id)
        db.session.add(visibility)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            visibility = ProfileVisibility.query.filter_by(user_id=user.id).first()
    return visibility


def _scope_is_visible(scope, is_owner):
    return is_owner or scope == PUBLIC_SCOPE


def _split_interests(interests):
    if not interests:
        return []
    normalized = interests.replace("，", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _normalize_interests(interests):
    return ", ".join(dict.fromkeys(_split_interests(interests)))


def _avatar_upload_dir():
    upload_dir = os.path.join(current_app.static_folder, AVATAR_UPLOAD_SUBDIR)
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def _save_avatar(file):
    if not file or not file.filename:
        return None

    expected = AVATAR_ALLOWED_TYPES.get(file.mimetype)
    if expected is None:
        raise ValueError("头像只支持 JPEG 或 WebP 格式。")

    content = file.stream.read(AVATAR_MAX_BYTES + 1)
    if not content:
        raise ValueError("头像文件不能为空。")
    if len(content) > AVATAR_MAX_BYTES:
        raise ValueError("裁剪后的头像不能超过 700KB。")

    extension, signature = expected
    if not content.startswith(signature):
        raise ValueError("头像文件内容与格式不匹配。")
    if extension == "webp" and (len(content) < 12 or content[8:12] != b"WEBP"):
        raise ValueError("头像文件内容与格式不匹配。")

    filename = f"{uuid4().hex}.{extension}"
    with open(os.path.join(_avatar_upload_dir(), filename), "wb") as avatar_file:
        avatar_file.write(content)
    return f"/static/{AVATAR_UPLOAD_SUBDIR.replace(os.sep, '/')}/{filename}"


def _delete_managed_avatar(avatar_url):
    prefix = f"/static/{AVATAR_UPLOAD_SUBDIR.replace(os.sep, '/')}/"
    if not avatar_url or not avatar_url.startswith(prefix):
        return

    avatar_path = os.path.join(_avatar_upload_dir(), os.path.basename(avatar_url))
    if os.path.isfile(avatar_path):
        os.remove(avatar_path)


def _safe_all(query):
    try:
        return query.all()
    except OperationalError:
        db.session.rollback()
        return []


def _refresh_detected_location(user):
    try:
        update_user_detected_location(user)
        db.session.commit()
    except Exception:
        db.session.rollback()


def _activity_label(activity_id):
    activity = Activity.query.get(activity_id)
    if activity:
        return activity.title
    return f"活动 #{activity_id}"


def _circle_label(circle_id):
    circle = Circle.query.get(circle_id)
    if circle:
        return circle.name

    from app.routes.circle import mock_circles

    mock_circle = next((item for item in mock_circles if item.get("id") == circle_id), None)
    return mock_circle["name"] if mock_circle else f"同好圈 #{circle_id}"


def _matches_text(query, *values):
    if not query:
        return True
    needle = query.casefold()
    return any(needle in str(value).casefold() for value in values if value)


def _registration_matches(activity_id, query):
    activity = Activity.query.get(activity_id)
    if activity:
        return _matches_text(
            query,
            activity.title,
            activity.description,
            activity.location,
            activity.preparation,
            activity.organizer.username if activity.organizer else None,
        )

    return False


def _membership_matches(circle_id, query):
    circle = Circle.query.get(circle_id)
    if circle:
        return _matches_text(query, circle.name, circle.tag, circle.description)

    from app.routes.circle import mock_circles

    mock_circle = next((item for item in mock_circles if item.get("id") == circle_id), {})
    return _matches_text(
        query,
        mock_circle.get("name"),
        mock_circle.get("tag"),
        mock_circle.get("summary"),
    )


def _interaction_type_options(user, target_type, review_type=None):
    action_types = [
        row[0]
        for row in db.session.query(Interaction.action_type)
        .filter_by(user_id=user.id, target_type=target_type)
        .distinct()
        .order_by(Interaction.action_type)
        .all()
        if row[0]
    ]
    return action_types + ([review_type] if review_type else [])


def _owner_profile_or_404():
    user = User.query.get_or_404(session["user_id"])
    visibility = _get_or_create_visibility(user)
    return user, visibility


def _profile_context(user, visibility, is_owner=True):
    circle_count = CircleMember.query.filter_by(user_id=user.id, status="active").count()
    registration_count = Registration.query.filter(
        Registration.user_id == user.id,
        Registration.status != "cancelled",
    ).count()
    follower_count = UserFollow.query.filter_by(followed_id=user.id).count()
    following_count = UserFollow.query.filter_by(follower_id=user.id).count()
    viewer_id = session.get("user_id")
    return {
        "user": user,
        "display_name": get_user_display_name(user),
        "is_owner": is_owner,
        "is_following": bool(
            viewer_id
            and viewer_id != user.id
            and UserFollow.query.filter_by(follower_id=viewer_id, followed_id=user.id).first()
        ),
        "visibility": visibility,
        "latest_merchant_verification": (
            MerchantVerification.query.filter_by(user_id=user.id)
            .order_by(MerchantVerification.created_at.desc())
            .first()
            if is_owner
            else None
        ),
        "permissions": {
            "interests": is_owner or bool(visibility.show_interests),
            "activities": is_owner,
            "circles": is_owner or visibility.circle_scope == PUBLIC_SCOPE,
            "interactions": is_owner,
            "trust_score": _scope_is_visible(visibility.trust_score_scope, is_owner),
        },
        "interests": _split_interests(user.interests) if (is_owner or bool(visibility.show_interests)) else [],
        "profile_stats": {
            "circles": circle_count if is_owner or visibility.circle_scope == PUBLIC_SCOPE else None,
            "interests": len(_split_interests(user.interests)) if is_owner or visibility.show_interests else None,
            "registrations": registration_count if is_owner or visibility.activity_scope == PUBLIC_SCOPE else None,
            "followers": follower_count,
            "following": following_count,
        },
    }


def _nearby_match_score(current_user, candidate):
    for current_index, current_location in enumerate(_nearby_location_values(current_user)):
        for candidate_index, candidate_location in enumerate(_nearby_location_values(candidate)):
            if locations_match(current_location, candidate_location):
                return current_index + candidate_index
    return 9


def _usable_nearby_location(value):
    value = (value or "").strip()
    if not value or value in UNKNOWN_LOCATION_LABELS:
        return None
    return value


def _nearby_location_values(user):
    values = []
    for value in (user.city, user.detected_city, user.detected_region):
        clean_value = _usable_nearby_location(value)
        if clean_value and clean_value not in values:
            values.append(clean_value)
    return values


def _nearby_locations_match(current_user, candidate):
    return _nearby_match_score(current_user, candidate) < 9


def _user_search_items(query_text):
    query = User.query.filter(User.status == "active")
    if query_text:
        pattern = f"%{query_text}%"
        query = query.filter(
            or_(
                User.username.ilike(pattern),
                User.nickname.ilike(pattern),
                User.city.ilike(pattern),
                User.bio.ilike(pattern),
            )
        )
    return query.order_by(User.created_at.desc(), User.id.desc()).limit(60).all()


def _relationship_items(user_id, relationship, query_text):
    if relationship == "followers":
        query = UserFollow.query.join(User, User.id == UserFollow.follower_id).filter(
            UserFollow.followed_id == user_id,
            User.status == "active",
        )
    else:
        query = UserFollow.query.join(User, User.id == UserFollow.followed_id).filter(
            UserFollow.follower_id == user_id,
            User.status == "active",
        )
    if query_text:
        pattern = f"%{query_text}%"
        query = query.filter(
            or_(
                User.username.ilike(pattern),
                User.nickname.ilike(pattern),
                User.city.ilike(pattern),
                User.bio.ilike(pattern),
            )
        )
    return query.order_by(UserFollow.created_at.desc()).all()


def _registration_items(user, filters):
    rows = _safe_all(
        Registration.query.filter_by(user_id=user.id)
        .order_by(Registration.register_time.desc())
    )
    items = [
        {
            "id": row.activity_id,
            "title": _activity_label(row.activity_id),
            "status": row.status,
            "time": row.register_time,
        }
        for row in rows
    ]
    if filters["q"]:
        items = [item for item in items if _registration_matches(item["id"], filters["q"])]
    if filters["status"]:
        items = [item for item in items if item["status"] == filters["status"]]
    return _ordered_items(items, filters["sort"])


def _circle_items(user, filters):
    rows = _safe_all(
        CircleMember.query.filter_by(user_id=user.id, status="active")
        .order_by(CircleMember.joined_at.desc())
    )
    items = [
        {
            "id": row.circle_id,
            "name": _circle_label(row.circle_id),
            "role": row.role,
            "status": row.status,
            "time": row.joined_at,
        }
        for row in rows
    ]
    if filters["q"]:
        items = [item for item in items if _membership_matches(item["id"], filters["q"])]
    if filters["status"]:
        items = [item for item in items if item["status"] == filters["status"]]
    if filters["type"]:
        items = [item for item in items if item["role"] == filters["type"]]
    return _ordered_items(items, filters["sort"])


def _published_activities(user, filters):
    query = Activity.query.filter(
        or_(
            Activity.organizer_id == user.id,
            and_(user.role == "admin", Activity.is_official.is_(True)),
        )
    )
    if filters["q"]:
        pattern = f"%{filters['q']}%"
        query = query.filter(
            or_(
                Activity.title.ilike(pattern),
                Activity.description.ilike(pattern),
                Activity.location.ilike(pattern),
                Activity.preparation.ilike(pattern),
            )
        )
    if filters["status"]:
        query = query.filter(Activity.status == filters["status"])
    ordering = Activity.created_at.asc() if filters["sort"] == "oldest" else Activity.created_at.desc()
    return _safe_all(query.order_by(ordering, Activity.id.asc() if filters["sort"] == "oldest" else Activity.id.desc()))


def _activity_interactions(user, filters):
    activity_actions = [
        {
            "id": item.target_id,
            "title": _activity_label(item.target_id),
            "action": item.action_type,
            "type": item.action_type,
            "time": item.created_at,
            "url": url_for("activity.activity_detail", activity_id=item.target_id),
        }
        for item in _safe_all(
            Interaction.query.filter_by(user_id=user.id, target_type="activity")
            .order_by(Interaction.created_at.desc())
        )
    ]
    items = activity_actions
    if filters["q"]:
        needle = filters["q"].casefold()
        items = [
            item
            for item in items
            if needle in item["title"].casefold() or needle in item["action"].casefold()
        ]
    if filters["type"]:
        items = [item for item in items if item["type"] == filters["type"]]
    return _ordered_items(items, filters["sort"])


def _circle_interactions(user, filters):
    circle_actions = [
        {
            "id": item.target_id,
            "title": _circle_label(item.target_id),
            "action": item.action_type,
            "type": item.action_type,
            "time": item.created_at,
            "url": url_for("circle.circle_detail", circle_id=item.target_id),
        }
        for item in _safe_all(
            Interaction.query.filter_by(user_id=user.id, target_type="circle")
            .order_by(Interaction.created_at.desc())
        )
    ]
    user_reviews = [
        {
            "id": review.activity_id,
            "title": review.activity.title if review.activity else _activity_label(review.activity_id),
            "type": "user_review",
            "action": f"评价活动伙伴 {review.average_score}/5",
            "time": review.created_at,
            # User reviews currently belong to activities, so the existing
            # activity detail page is the closest available destination.
            "url": url_for("activity.activity_detail", activity_id=review.activity_id),
        }
        for review in _safe_all(
            UserReview.query.filter_by(reviewer_id=user.id)
            .order_by(UserReview.created_at.desc())
        )
    ]
    items = circle_actions + user_reviews
    if filters["q"]:
        needle = filters["q"].casefold()
        items = [
            item
            for item in items
            if needle in item["title"].casefold() or needle in item["action"].casefold()
        ]
    if filters["type"]:
        items = [item for item in items if item["type"] == filters["type"]]
    return _ordered_items(items, filters["sort"])


def _profile_posts(user, filters):
    query = Post.query.join(Post.circle).filter(Post.user_id == user.id)
    if filters["q"]:
        pattern = f"%{filters['q']}%"
        query = query.filter(
            or_(
                Post.title.ilike(pattern),
                Post.content.ilike(pattern),
                Circle.name.ilike(pattern),
                Circle.tag.ilike(pattern),
            )
        )
    if filters["status"]:
        query = query.filter(Post.status == filters["status"])
    if filters["type"]:
        query = query.filter(Post.type == filters["type"])
    ordering = Post.created_at.asc() if filters["sort"] == "oldest" else Post.created_at.desc()
    return _safe_all(query.order_by(ordering, Post.id.asc() if filters["sort"] == "oldest" else Post.id.desc()))


def _profile_comments(user, filters):
    query = (
        Comment.query.outerjoin(Comment.post)
        .outerjoin(Post.circle)
        .outerjoin(Comment.activity)
        .filter(Comment.author_id == user.id)
    )
    if filters["q"]:
        pattern = f"%{filters['q']}%"
        query = query.filter(
            or_(
                Comment.content.ilike(pattern),
                Post.title.ilike(pattern),
                Circle.name.ilike(pattern),
                Activity.title.ilike(pattern),
                Activity.location.ilike(pattern),
            )
        )
    if filters["status"]:
        query = query.filter(Comment.status == filters["status"])
    if filters["type"] == "reply":
        query = query.filter(Comment.parent_id.isnot(None))
    elif filters["type"] == "post":
        query = query.filter(Comment.post_id.isnot(None), Comment.parent_id.is_(None))
    elif filters["type"] == "activity":
        query = query.filter(Comment.activity_id.isnot(None), Comment.parent_id.is_(None))
    ordering = Comment.created_at.asc() if filters["sort"] == "oldest" else Comment.created_at.desc()
    return _safe_all(query.order_by(ordering, Comment.id.asc() if filters["sort"] == "oldest" else Comment.id.desc()))


@profile_bp.route("/")
@login_required
def my_profile():
    return redirect(url_for("profile.view_profile", user_id=session["user_id"]))


@profile_bp.route("/<int:user_id>")
@login_required
def view_profile(user_id):
    user = User.query.get_or_404(user_id)
    display_name = get_user_display_name(user)
    if user.status == "deleted":
        return render_template("profile.html", user=user, display_name=display_name)

    is_owner = session.get("user_id") == user.id
    if is_owner:
        _refresh_detected_location(user)
    visibility = _get_or_create_visibility(user)

    if visibility.profile_scope == PRIVATE_SCOPE and not is_owner:
        abort(404)
    context = _profile_context(user, visibility, is_owner=is_owner)

    default_filters = _empty_filters()
    circles = _circle_items(user, default_filters) if context["permissions"]["circles"] else []
    if not is_owner:
        return render_template(
            "profile.html",
            **context,
            circle_memberships_preview=_preview_items(circles),
            circle_memberships_count=len(circles),
        )

    created_activities = _published_activities(user, default_filters)
    joined_activities = _registration_items(user, default_filters)
    posts = _profile_posts(user, default_filters)
    comments = _profile_comments(user, default_filters)
    favorite_activities_count = ActivityFavorite.query.filter_by(user_id=user.id).count()
    activity_interactions = _activity_interactions(user, default_filters)
    circle_interactions = _circle_interactions(user, default_filters)

    return render_template(
        "profile.html",
        **context,
        created_activities_preview=_preview_items(created_activities),
        created_activities_count=len(created_activities),
        joined_activities_preview=_preview_items(joined_activities),
        joined_activities_count=len(joined_activities),
        circle_memberships_preview=_preview_items(circles),
        circle_memberships_count=len(circles),
        profile_posts_preview=_preview_items(posts),
        profile_posts_count=len(posts),
        profile_comments_preview=_preview_items(comments),
        profile_comments_count=len(comments),
        favorite_activities_count=favorite_activities_count,
        activity_interactions_preview=_preview_items(activity_interactions),
        activity_interactions_count=len(activity_interactions),
        circle_interactions_preview=_preview_items(circle_interactions),
        circle_interactions_count=len(circle_interactions),
    )


@profile_bp.route("/users")
@login_required
def user_search():
    query_text = request.args.get("q", "").strip()
    users = _user_search_items(query_text)
    current_user_id = session["user_id"]
    following_ids = {
        row.followed_id
        for row in UserFollow.query.filter_by(follower_id=current_user_id).all()
    }
    return render_template(
        "users.html",
        query=query_text,
        users=users,
        following_ids=following_ids,
        page_title="搜索用户",
        heading="搜索用户",
        empty_message="暂无匹配用户。",
        nearby_mode=False,
    )


@profile_bp.route("/nearby")
@login_required
def nearby_users():
    current_user = User.query.get_or_404(session["user_id"])
    _refresh_detected_location(current_user)
    current_locations = _nearby_location_values(current_user)
    following_ids = {
        row.followed_id
        for row in UserFollow.query.filter_by(follower_id=current_user.id).all()
    }
    users = []
    location_notice = None
    if current_locations:
        candidates = (
            User.query.filter(
                User.status == "active",
                User.nearby_enabled.is_(True),
                User.id != current_user.id,
            )
            .order_by(User.created_at.desc(), User.id.desc())
            .limit(120)
            .all()
        )
        users = [user for user in candidates if _nearby_locations_match(current_user, user)]
        users = sorted(
            users,
            key=lambda user: (
                _nearby_match_score(current_user, user),
                -(user.created_at.timestamp() if user.created_at else 0),
                -user.id,
            ),
        )[:60]
    else:
        location_notice = "暂时无法识别你的地区，请开启附近的人后刷新或完善城市信息。"

    return render_template(
        "users.html",
        query="",
        users=users,
        following_ids=following_ids,
        page_title="附近的人",
        heading="附近的人",
        empty_message=location_notice or "附近暂时没有主动开启该功能的用户。",
        location_notice=location_notice,
        nearby_mode=True,
        nearby_user=current_user,
        nearby_location_label=" / ".join(current_locations),
    )


@profile_bp.route("/nearby/toggle", methods=["POST"])
@login_required
def toggle_nearby():
    user = User.query.get_or_404(session["user_id"])
    user.nearby_enabled = not bool(user.nearby_enabled)
    if user.nearby_enabled:
        try:
            update_user_detected_location(user, force=True)
        except Exception:
            db.session.rollback()
            user = User.query.get_or_404(session["user_id"])
            user.nearby_enabled = True
            db.session.commit()
            flash("已开启附近的人，但暂时无法更新粗略地区。", "warning")
            return redirect(url_for("profile.nearby_users"))

    db.session.commit()
    if user.nearby_enabled:
        flash("已开启附近的人。不会公开你的真实 IP 或精确地址。", "success")
    else:
        flash("已关闭附近的人。其他用户不会在附近的人列表中看到你。", "success")
    return redirect(url_for("profile.nearby_users"))


@profile_bp.route("/<int:user_id>/followers")
@login_required
def followers(user_id):
    user = User.query.get_or_404(user_id)
    visibility = _get_or_create_visibility(user)
    is_owner = session.get("user_id") == user.id
    if visibility.profile_scope == PRIVATE_SCOPE and not is_owner:
        abort(404)
    query_text = request.args.get("q", "").strip()
    rows = _relationship_items(user.id, "followers", query_text)
    current_user_id = session["user_id"]
    following_ids = {
        row.followed_id
        for row in UserFollow.query.filter_by(follower_id=current_user_id).all()
    }
    return render_template(
        "follows.html",
        **_profile_context(user, visibility, is_owner=is_owner),
        page_title=f"{get_user_display_name(user)} 的粉丝",
        heading="粉丝",
        query=query_text,
        relationship="followers",
        rows=rows,
        following_ids=following_ids,
    )


@profile_bp.route("/<int:user_id>/following")
@login_required
def following(user_id):
    user = User.query.get_or_404(user_id)
    visibility = _get_or_create_visibility(user)
    is_owner = session.get("user_id") == user.id
    if visibility.profile_scope == PRIVATE_SCOPE and not is_owner:
        abort(404)
    query_text = request.args.get("q", "").strip()
    rows = _relationship_items(user.id, "following", query_text)
    current_user_id = session["user_id"]
    following_ids = {
        row.followed_id
        for row in UserFollow.query.filter_by(follower_id=current_user_id).all()
    }
    return render_template(
        "follows.html",
        **_profile_context(user, visibility, is_owner=is_owner),
        page_title=f"{get_user_display_name(user)} 的关注",
        heading="关注",
        query=query_text,
        relationship="following",
        rows=rows,
        following_ids=following_ids,
    )


@profile_bp.route("/<int:user_id>/circles")
@login_required
def user_circles(user_id):
    user = User.query.get_or_404(user_id)
    visibility = _get_or_create_visibility(user)
    is_owner = session.get("user_id") == user.id
    if visibility.profile_scope == PRIVATE_SCOPE and not is_owner:
        abort(404)
    if not (is_owner or visibility.circle_scope == PUBLIC_SCOPE):
        abort(404)
    filters = _section_filters("circle")
    return render_template(
        "user_circles.html",
        **_profile_context(user, visibility, is_owner=is_owner),
        page_title=f"{get_user_display_name(user)} 加入的同好圈",
        items=_circle_items(user, filters),
        filters=filters,
        reset_url=url_for("profile.user_circles", user_id=user.id),
    )


@profile_bp.route("/<int:user_id>/follow", methods=["POST"])
@login_required
def follow_user(user_id):
    current_user_id = session["user_id"]
    fallback_url = request.form.get("next") or request.referrer or url_for("profile.view_profile", user_id=user_id)
    if user_id == current_user_id:
        flash("不能关注自己。", "error")
        return redirect(fallback_url)
    target = User.query.filter(User.id == user_id, User.status == "active").first()
    if target is None:
        flash("用户不存在或不可关注。", "error")
        return redirect(fallback_url)
    existing = UserFollow.query.filter_by(follower_id=current_user_id, followed_id=user_id).first()
    if existing is None:
        db.session.add(UserFollow(follower_id=current_user_id, followed_id=user_id))
        try:
            db.session.commit()
            flash("已关注该用户。", "success")
        except IntegrityError:
            db.session.rollback()
    return redirect(fallback_url)


@profile_bp.route("/<int:user_id>/unfollow", methods=["POST"])
@login_required
def unfollow_user(user_id):
    current_user_id = session["user_id"]
    fallback_url = request.form.get("next") or request.referrer or url_for("profile.view_profile", user_id=user_id)
    follow = UserFollow.query.filter_by(follower_id=current_user_id, followed_id=user_id).first()
    if follow:
        db.session.delete(follow)
        db.session.commit()
        flash("已取消关注。", "success")
    return redirect(fallback_url)


def _render_profile_section(section_key, template_title, heading, items, filter_prefix, status_options, type_options):
    user, visibility = _owner_profile_or_404()
    context = _profile_context(user, visibility, is_owner=True)
    filters = _section_filters(filter_prefix)
    return render_template(
        "profile_section.html",
        **context,
        section_key=section_key,
        page_title=template_title,
        section_heading=heading,
        items=items(user, filters),
        filters=filters,
        filter_prefix=filter_prefix,
        reset_url=_section_reset_url(filter_prefix, ""),
        status_options=status_options,
        type_options=type_options,
    )


@profile_bp.route("/activities/created")
@login_required
def created_activities():
    return _render_profile_section(
        "created_activity",
        "我发布的活动",
        "我发布的活动",
        _published_activities,
        "created_activity",
        ["open", "hidden", "closed"],
        [],
    )


@profile_bp.route("/activities/joined")
@login_required
def joined_activities():
    return _render_profile_section(
        "joined_activity",
        "报名的活动",
        "报名的活动",
        _registration_items,
        "joined_activity",
        ["registered"],
        [],
    )


@profile_bp.route("/circles")
@login_required
def my_circles():
    return _render_profile_section(
        "circle",
        "加入的同好圈",
        "加入的同好圈",
        _circle_items,
        "circle",
        ["active"],
        ["member", "owner"],
    )


@profile_bp.route("/posts")
@login_required
def my_posts():
    return _render_profile_section(
        "post",
        "我的帖子",
        "我的帖子",
        _profile_posts,
        "post",
        ["published", "hidden", "deleted"],
        ["share"],
    )


@profile_bp.route("/comments")
@login_required
def my_comments():
    return _render_profile_section(
        "comment",
        "我的评论",
        "我的评论",
        _profile_comments,
        "comment",
        ["published", "hidden", "deleted"],
        ["post", "activity", "reply"],
    )


@profile_bp.route("/interactions/activities")
@login_required
def my_activity_interactions():
    user, _ = _owner_profile_or_404()
    return _render_profile_section(
        "activity_interaction",
        "活动互动记录",
        "活动互动记录",
        _activity_interactions,
        "activity_interaction",
        [],
        _interaction_type_options(user, "activity"),
    )


@profile_bp.route("/interactions/circles")
@login_required
def my_circle_interactions():
    user, _ = _owner_profile_or_404()
    return _render_profile_section(
        "circle_interaction",
        "同好圈互动记录",
        "同好圈互动记录",
        _circle_interactions,
        "circle_interaction",
        [],
        _interaction_type_options(user, "circle", "user_review"),
    )


@profile_bp.route("/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    post = Post.query.get(post_id)
    fallback_url = request.referrer or url_for("profile.my_posts")
    if post is None:
        flash("帖子不存在或已被移除。", "error")
        return redirect(fallback_url)

    if post.user_id != session["user_id"]:
        flash("您只能删除自己发布的帖子。", "error")
        return redirect(fallback_url)

    if post.status == "deleted":
        flash("该帖子已经删除。", "info")
        return redirect(fallback_url)

    Circle.query.filter_by(pinned_post_id=post.id).update(
        {"pinned_post_id": None},
        synchronize_session=False,
    )
    post.status = "deleted"
    db.session.commit()
    flash("帖子已删除。", "success")
    return redirect(fallback_url)


@profile_bp.route("/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get(comment_id)
    fallback_url = request.referrer or url_for("profile.my_comments")
    if comment is None:
        flash("评论不存在或已被移除。", "error")
        return redirect(fallback_url)

    if comment.author_id != session["user_id"]:
        flash("您只能删除自己发布的评论。", "error")
        return redirect(fallback_url)

    if comment.status == "deleted":
        flash("该评论已经删除。", "info")
        return redirect(fallback_url)

    comment.status = "deleted"
    db.session.commit()
    flash("评论已删除。", "success")
    return redirect(fallback_url)


@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    user = User.query.get_or_404(session["user_id"])
    visibility = _get_or_create_visibility(user)

    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "profile":
            nickname = request.form.get("nickname", "").strip() or user.username
            city = request.form.get("city", "").strip() or None
            bio = request.form.get("bio", "").strip() or None
            interests = _normalize_interests(request.form.get("interests", "")) or None

            if len(nickname) > 80:
                flash("昵称不能超过 80 个字符。", "error")
                return render_template("edit_profile.html", user=user, visibility=visibility)
            if city and len(city) > 80:
                flash("城市不能超过 80 个字符。", "error")
                return render_template("edit_profile.html", user=user, visibility=visibility)
            if bio and len(bio) > BIO_MAX_LENGTH:
                flash(f"个人简介不能超过 {BIO_MAX_LENGTH} 个字符。", "error")
                return render_template("edit_profile.html", user=user, visibility=visibility)
            if interests and len(interests) > INTERESTS_MAX_LENGTH:
                flash(f"兴趣标签总长度不能超过 {INTERESTS_MAX_LENGTH} 个字符。", "error")
                return render_template("edit_profile.html", user=user, visibility=visibility)

            old_avatar = user.avatar
            new_avatar = None
            try:
                new_avatar = _save_avatar(request.files.get("avatar_file"))
            except ValueError as error:
                flash(str(error), "error")
                return render_template("edit_profile.html", user=user, visibility=visibility)

            user.nickname = nickname
            user.city = city
            if new_avatar:
                user.avatar = new_avatar
            elif request.form.get("remove_avatar"):
                user.avatar = None
            user.bio = bio
            user.interests = interests

            try:
                db.session.commit()
                if old_avatar != user.avatar:
                    _delete_managed_avatar(old_avatar)
                session["nickname"] = user.nickname or user.username
                flash("个人资料已更新。", "success")
            except IntegrityError:
                db.session.rollback()
                _delete_managed_avatar(new_avatar)
                flash("用户名或邮箱已被使用，请换一个。", "error")
        elif form_type == "visibility":
            visibility.activity_scope = PUBLIC_SCOPE if request.form.get("show_activities") else PRIVATE_SCOPE
            visibility.circle_scope = PUBLIC_SCOPE if request.form.get("show_circles") else PRIVATE_SCOPE
            visibility.show_interactions = bool(request.form.get("show_interactions"))
            visibility.show_interests = bool(request.form.get("show_interests"))
            visibility.trust_score_scope = PUBLIC_SCOPE if request.form.get("show_trust_score") else PRIVATE_SCOPE
            visibility.profile_scope = PUBLIC_SCOPE if request.form.get("profile_public") else PRIVATE_SCOPE
            db.session.commit()
            flash("主页展示权限已更新。", "success")

        return redirect(url_for("profile.edit_profile"))

    return render_template("edit_profile.html", user=user, visibility=visibility)
