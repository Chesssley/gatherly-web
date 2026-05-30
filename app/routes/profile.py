from functools import wraps
import os
from urllib.parse import urlencode
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import (
    Activity,
    ActivityReview,
    Circle,
    CircleMember,
    Comment,
    Interaction,
    Post,
    ProfileVisibility,
    Registration,
    User,
    UserReview,
    db,
    get_user_display_name,
)

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


def _activity_label(activity_id):
    activity = Activity.query.get(activity_id)
    if activity:
        return activity.title

    from app.routes.activity import activities

    mock_activity = next((item for item in activities if item.get("id") == activity_id), None)
    return mock_activity["title"] if mock_activity else f"活动 #{activity_id}"


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

    from app.routes.activity import activities

    mock_activity = next((item for item in activities if item.get("id") == activity_id), {})
    return _matches_text(
        query,
        mock_activity.get("title"),
        mock_activity.get("description"),
        mock_activity.get("detail"),
        mock_activity.get("location"),
        mock_activity.get("category"),
    )


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


def _interaction_type_options(user, target_type, review_type):
    action_types = [
        row[0]
        for row in db.session.query(Interaction.action_type)
        .filter_by(user_id=user.id, target_type=target_type)
        .distinct()
        .order_by(Interaction.action_type)
        .all()
        if row[0]
    ]
    return action_types + [review_type]


def _owner_profile_or_404():
    user = User.query.get_or_404(session["user_id"])
    visibility = _get_or_create_visibility(user)
    return user, visibility


def _profile_context(user, visibility, is_owner=True):
    return {
        "user": user,
        "display_name": get_user_display_name(user),
        "is_owner": is_owner,
        "visibility": visibility,
        "permissions": {
            "interests": is_owner or bool(visibility.show_interests),
            "activities": is_owner,
            "circles": is_owner,
            "interactions": is_owner,
            "trust_score": _scope_is_visible(visibility.trust_score_scope, is_owner),
        },
        "interests": _split_interests(user.interests) if (is_owner or bool(visibility.show_interests)) else [],
    }


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
    query = Activity.query.filter(Activity.organizer_id == user.id)
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
    activity_reviews = [
        {
            "id": review.activity_id,
            "title": review.activity.title if review.activity else _activity_label(review.activity_id),
            "type": "activity_review",
            "action": f"活动评分 {review.average_score}/5",
            "time": review.created_at,
            "url": url_for("activity.activity_detail", activity_id=review.activity_id),
        }
        for review in _safe_all(
            ActivityReview.query.filter_by(reviewer_id=user.id)
            .order_by(ActivityReview.created_at.desc())
        )
    ]
    items = activity_actions + activity_reviews
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
    visibility = _get_or_create_visibility(user)

    if visibility.profile_scope == PRIVATE_SCOPE and not is_owner:
        abort(404)
    context = _profile_context(user, visibility, is_owner=is_owner)
    if not is_owner:
        return render_template("profile.html", **context)

    default_filters = _empty_filters()
    created_activities = _published_activities(user, default_filters)
    joined_activities = _registration_items(user, default_filters)
    circles = _circle_items(user, default_filters)
    posts = _profile_posts(user, default_filters)
    comments = _profile_comments(user, default_filters)
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
        activity_interactions_preview=_preview_items(activity_interactions),
        activity_interactions_count=len(activity_interactions),
        circle_interactions_preview=_preview_items(circle_interactions),
        circle_interactions_count=len(circle_interactions),
    )


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
        _interaction_type_options(user, "activity", "activity_review"),
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
            email = request.form.get("email", "").strip()
            bio = request.form.get("bio", "").strip() or None
            interests = _normalize_interests(request.form.get("interests", "")) or None

            if len(nickname) > 80:
                flash("昵称不能超过 80 个字符。", "error")
                return render_template("edit_profile.html", user=user, visibility=visibility)
            if not email:
                flash("邮箱不能为空。", "error")
                return render_template("edit_profile.html", user=user, visibility=visibility)
            if len(email) > 120:
                flash("邮箱不能超过 120 个字符。", "error")
                return render_template("edit_profile.html", user=user, visibility=visibility)
            if bio and len(bio) > BIO_MAX_LENGTH:
                flash(f"个人简介不能超过 {BIO_MAX_LENGTH} 个字符。", "error")
                return render_template("edit_profile.html", user=user, visibility=visibility)
            if interests and len(interests) > INTERESTS_MAX_LENGTH:
                flash(f"兴趣标签总长度不能超过 {INTERESTS_MAX_LENGTH} 个字符。", "error")
                return render_template("edit_profile.html", user=user, visibility=visibility)

            current_password = request.form.get("current_password", "")
            new_password = request.form.get("new_password", "")
            confirm_password = request.form.get("confirm_password", "")
            if new_password or confirm_password:
                if not current_password or not check_password_hash(user.password, current_password):
                    flash("修改密码前必须先校验原密码。", "error")
                    return render_template("edit_profile.html", user=user, visibility=visibility)
                if new_password != confirm_password:
                    flash("两次输入的新密码不一致。", "error")
                    return render_template("edit_profile.html", user=user, visibility=visibility)
                if len(new_password) < 6:
                    flash("新密码至少需要 6 个字符。", "error")
                    return render_template("edit_profile.html", user=user, visibility=visibility)
                user.password = generate_password_hash(new_password)

            old_avatar = user.avatar
            new_avatar = None
            try:
                new_avatar = _save_avatar(request.files.get("avatar_file"))
            except ValueError as error:
                flash(str(error), "error")
                return render_template("edit_profile.html", user=user, visibility=visibility)

            user.nickname = nickname
            user.email = email
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
