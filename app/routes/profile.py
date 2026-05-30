from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import (
    Activity,
    ActivityReview,
    Circle,
    CircleMember,
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


def _registration_items(user):
    rows = _safe_all(
        Registration.query.filter_by(user_id=user.id)
        .order_by(Registration.register_time.desc())
    )
    return [
        {
            "id": row.activity_id,
            "title": _activity_label(row.activity_id),
            "status": row.status,
            "time": row.register_time,
        }
        for row in rows
    ]


def _circle_items(user):
    rows = _safe_all(
        CircleMember.query.filter_by(user_id=user.id)
        .order_by(CircleMember.joined_at.desc())
    )
    return [
        {
            "id": row.circle_id,
            "name": _circle_label(row.circle_id),
            "role": row.role,
            "status": row.status,
            "time": row.joined_at,
        }
        for row in rows
    ]


def _activity_interactions(user):
    activity_actions = [
        {
            "title": _activity_label(item.target_id),
            "action": item.action_type,
            "time": item.created_at,
        }
        for item in _safe_all(
            Interaction.query.filter_by(user_id=user.id, target_type="activity")
            .order_by(Interaction.created_at.desc())
        )
    ]
    activity_reviews = [
        {
            "title": review.activity.title if review.activity else _activity_label(review.activity_id),
            "action": f"活动评分 {review.average_score}/5",
            "time": review.created_at,
        }
        for review in _safe_all(
            ActivityReview.query.filter_by(reviewer_id=user.id)
            .order_by(ActivityReview.created_at.desc())
        )
    ]
    return sorted(activity_actions + activity_reviews, key=lambda item: item["time"], reverse=True)


def _circle_interactions(user):
    circle_actions = [
        {
            "title": _circle_label(item.target_id),
            "action": item.action_type,
            "time": item.created_at,
        }
        for item in _safe_all(
            Interaction.query.filter_by(user_id=user.id, target_type="circle")
            .order_by(Interaction.created_at.desc())
        )
    ]
    posts = [
        {
            "title": post.circle.name if post.circle else _circle_label(post.circle_id),
            "action": f"发布帖子：{post.title}",
            "time": post.created_at,
        }
        for post in _safe_all(Post.query.filter_by(user_id=user.id).order_by(Post.created_at.desc()))
    ]
    user_reviews = [
        {
            "title": review.activity.title if review.activity else _activity_label(review.activity_id),
            "action": f"评价活动伙伴 {review.average_score}/5",
            "time": review.created_at,
        }
        for review in _safe_all(
            UserReview.query.filter_by(reviewer_id=user.id)
            .order_by(UserReview.created_at.desc())
        )
    ]
    return sorted(circle_actions + posts + user_reviews, key=lambda item: item["time"], reverse=True)


@profile_bp.route("/")
@login_required
def my_profile():
    return redirect(url_for("profile.view_profile", user_id=session["user_id"]))


@profile_bp.route("/<int:user_id>")
def view_profile(user_id):
    user = User.query.get_or_404(user_id)
    display_name = get_user_display_name(user)
    if user.status == "deleted":
        return render_template("profile.html", user=user, display_name=display_name)

    is_owner = session.get("user_id") == user.id
    visibility = _get_or_create_visibility(user)

    if visibility.profile_scope == PRIVATE_SCOPE and not is_owner:
        abort(404)

    permissions = {
        "interests": is_owner or bool(visibility.show_interests),
        "activities": _scope_is_visible(visibility.activity_scope, is_owner),
        "circles": _scope_is_visible(visibility.circle_scope, is_owner),
        "interactions": is_owner or bool(visibility.show_interactions),
        "trust_score": _scope_is_visible(visibility.trust_score_scope, is_owner),
    }

    return render_template(
        "profile.html",
        user=user,
        display_name=display_name,
        is_owner=is_owner,
        visibility=visibility,
        permissions=permissions,
        interests=_split_interests(user.interests) if permissions["interests"] else [],
        registrations=_registration_items(user) if permissions["activities"] else [],
        circle_memberships=_circle_items(user) if permissions["circles"] else [],
        activity_interactions=_activity_interactions(user) if permissions["interactions"] else [],
        circle_interactions=_circle_interactions(user) if permissions["interactions"] else [],
    )


@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    user = User.query.get_or_404(session["user_id"])
    visibility = _get_or_create_visibility(user)

    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "profile":
            user.nickname = request.form.get("nickname", "").strip() or user.username
            user.avatar = request.form.get("avatar", "").strip() or None
            user.interests = request.form.get("interests", "").strip() or None
            user.email = request.form.get("email", "").strip() or user.email

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

            try:
                db.session.commit()
                session["nickname"] = user.nickname or user.username
                flash("个人资料已更新。", "success")
            except IntegrityError:
                db.session.rollback()
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
