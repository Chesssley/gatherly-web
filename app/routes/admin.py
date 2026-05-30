from datetime import datetime
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import Activity, AdminLog, Circle, Comment, Post, User, db

admin_bp = Blueprint("admin", __name__)

USER_STATUSES = {"active", "banned"}
ACTIVITY_STATUSES = {"open", "hidden", "closed"}
CIRCLE_STATUSES = {"active", "hidden"}
CONTENT_STATUSES = {"published", "hidden"}


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    _ensure_admin_schema()
    return User.query.get(user_id)


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = get_current_user()
        if user is None:
            return redirect(url_for("auth.login", next=request.url))
        if user.role != "admin":
            flash("您没有权限访问后台管理系统。", "error")
            return redirect(url_for("activity.index"))
        return view(*args, **kwargs)

    return wrapped_view


def _ensure_admin_schema():
    AdminLog.__table__.create(db.engine, checkfirst=True)
    if db.engine.dialect.name != "sqlite":
        return

    table_columns = {
        "user": ("status", "ALTER TABLE user ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"),
        "activity": ("status", "ALTER TABLE activity ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'open'"),
        "circle": ("status", "ALTER TABLE circle ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'"),
        "post": ("status", "ALTER TABLE post ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'published'"),
        "comment": ("status", "ALTER TABLE comment ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'published'"),
    }
    changed = False
    for table_name, (column_name, statement) in table_columns.items():
        rows = db.session.execute(text(f'PRAGMA table_info("{table_name}")')).fetchall()
        if rows and column_name not in {row[1] for row in rows}:
            db.session.execute(text(statement))
            changed = True
    user_columns = {
        row[1] for row in db.session.execute(text('PRAGMA table_info("user")')).fetchall()
    }
    if user_columns and "banned_at" not in user_columns:
        db.session.execute(text("ALTER TABLE user ADD COLUMN banned_at DATETIME"))
        changed = True
    if changed:
        db.session.commit()


@admin_bp.before_app_request
def ensure_admin_schema():
    _ensure_admin_schema()


def log_admin_action(admin_id, action, target_type, target_id, detail=None):
    db.session.add(
        AdminLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=request.remote_addr,
        )
    )


@admin_bp.after_app_request
def log_official_circle_creation(response):
    if (
        request.endpoint == "circle.create_circle"
        and request.method == "POST"
        and response.status_code in {301, 302, 303, 307, 308}
        and request.form.get("circle_type", "").strip() in {"official", "system"}
    ):
        admin = get_current_user()
        if admin and admin.role == "admin":
            circle = (
                Circle.query.filter_by(owner_id=admin.id, is_system=True)
                .order_by(Circle.id.desc())
                .first()
            )
            if circle:
                log_admin_action(
                    admin.id,
                    "create_official_circle",
                    "同好圈",
                    circle.id,
                    f"official_circle: false -> true; name: {circle.name}",
                )
                db.session.commit()
    return response


def _update_status(model, target_id, allowed_statuses, target_type, list_endpoint):
    _ensure_admin_schema()
    target = model.query.get_or_404(target_id)
    new_status = request.form.get("status", "").strip()
    if new_status not in allowed_statuses:
        flash("无效的状态值，未进行修改。", "error")
        return redirect(url_for(list_endpoint))

    previous_status = target.status
    if previous_status == new_status:
        flash("状态没有变化。", "success")
        return redirect(url_for(list_endpoint))

    target.status = new_status
    log_admin_action(
        get_current_user().id,
        "update_status",
        target_type,
        target.id,
        f"status: {previous_status} -> {new_status}",
    )
    db.session.commit()
    flash(f"{target_type} #{target.id} 状态已更新为 {new_status}。", "success")
    return redirect(url_for(list_endpoint))


@admin_bp.app_context_processor
def inject_current_user():
    return {"current_user": get_current_user()}


@admin_bp.route("/admin")
@admin_required
def admin_dashboard():
    _ensure_admin_schema()
    stats = {
        "users": User.query.count(),
        "activities": Activity.query.count(),
        "circles": Circle.query.count(),
        "posts": Post.query.count(),
        "comments": Comment.query.count(),
    }
    logs = AdminLog.query.order_by(AdminLog.created_at.desc()).limit(30).all()
    return render_template("admin_dashboard.html", stats=stats, logs=logs)


@admin_bp.route("/admin/logs")
@admin_required
def admin_logs():
    _ensure_admin_schema()
    logs = AdminLog.query.order_by(AdminLog.created_at.desc()).limit(100).all()
    return render_template("admin_logs.html", logs=logs)


@admin_bp.route("/admin/users")
@admin_required
def admin_users():
    _ensure_admin_schema()
    users = User.query.order_by(User.created_at.desc(), User.id.desc()).all()
    return render_template("admin_users.html", users=users)


def _update_user_ban_status(user_id, new_status):
    _ensure_admin_schema()
    user = User.query.get_or_404(user_id)
    admin = get_current_user()

    if new_status == "banned" and user.id == admin.id:
        flash("不能封禁当前登录的管理员账号。", "error")
        return redirect(url_for("admin.admin_users"))

    previous_status = user.status
    if previous_status == new_status:
        flash("账号状态没有变化。", "info")
        return redirect(url_for("admin.admin_users"))
    if previous_status not in USER_STATUSES:
        flash("当前账号状态不支持此操作。", "error")
        return redirect(url_for("admin.admin_users"))

    user.status = new_status
    user.banned_at = datetime.utcnow() if new_status == "banned" else None
    log_admin_action(
        admin.id,
        "ban_user" if new_status == "banned" else "unban_user",
        "用户",
        user.id,
        f"status: {previous_status} -> {new_status}",
    )
    db.session.commit()
    flash("用户已封禁" if new_status == "banned" else "用户已解封", "success")
    return redirect(url_for("admin.admin_users"))


@admin_bp.route("/admin/users/<int:user_id>/ban", methods=["POST"])
@admin_required
def ban_user(user_id):
    return _update_user_ban_status(user_id, "banned")


@admin_bp.route("/admin/users/<int:user_id>/unban", methods=["POST"])
@admin_required
def unban_user(user_id):
    return _update_user_ban_status(user_id, "active")


@admin_bp.route("/admin/users/<int:user_id>/promote-admin", methods=["POST"])
@admin_required
def promote_admin(user_id):
    _ensure_admin_schema()
    user = User.query.get_or_404(user_id)
    admin = get_current_user()

    if user.status != "active":
        flash("只有正常状态的用户可以设为管理员。", "error")
        return redirect(url_for("admin.admin_users"))
    if user.role == "admin":
        flash("该用户已经是管理员。", "info")
        return redirect(url_for("admin.admin_users"))

    previous_role = user.role
    user.role = "admin"
    log_admin_action(
        admin.id,
        "promote_admin",
        "用户",
        user.id,
        f"role: {previous_role} -> admin",
    )
    db.session.commit()
    flash("已设为管理员", "success")
    return redirect(url_for("admin.admin_users"))


@admin_bp.route("/admin/users/<int:user_id>/demote-admin", methods=["POST"])
@admin_required
def demote_admin(user_id):
    _ensure_admin_schema()
    user = User.query.get_or_404(user_id)
    admin = get_current_user()

    if user.id == admin.id:
        flash("不能撤销自己的管理员权限。", "error")
        return redirect(url_for("admin.admin_users"))
    if user.role != "admin":
        flash("该用户不是管理员。", "info")
        return redirect(url_for("admin.admin_users"))
    if User.query.filter_by(role="admin").count() <= 1:
        flash("系统必须保留至少一个管理员。", "error")
        return redirect(url_for("admin.admin_users"))

    user.role = "user"
    log_admin_action(
        admin.id,
        "demote_admin",
        "用户",
        user.id,
        "role: admin -> user",
    )
    db.session.commit()
    flash("已撤销管理员权限", "success")
    return redirect(url_for("admin.admin_users"))


@admin_bp.route("/admin/activities")
@admin_required
def admin_activities():
    _ensure_admin_schema()
    activities = Activity.query.order_by(Activity.created_at.desc(), Activity.id.desc()).all()
    return render_template("admin_activities.html", activities=activities)


@admin_bp.route("/admin/activities/<int:activity_id>/status", methods=["POST"])
@admin_required
def update_activity_status(activity_id):
    return _update_status(
        Activity,
        activity_id,
        ACTIVITY_STATUSES,
        "活动",
        "admin.admin_activities",
    )


@admin_bp.route("/admin/circles")
@admin_required
def admin_circles():
    _ensure_admin_schema()
    circles = (
        db.session.query(Circle, func.count(Post.id).label("post_count"))
        .outerjoin(Post, Post.circle_id == Circle.id)
        .group_by(Circle.id)
        .order_by(Circle.created_at.desc(), Circle.id.desc())
        .all()
    )
    return render_template("admin_circles.html", circles=circles)


@admin_bp.route("/admin/circles/<int:circle_id>/status", methods=["POST"])
@admin_required
def update_circle_status(circle_id):
    _ensure_admin_schema()
    circle = Circle.query.get_or_404(circle_id)
    if not circle.is_system:
        flash("仅允许修改官方圈子状态。", "error")
        return redirect(url_for("admin.admin_circles"))
    return _update_status(Circle, circle_id, CIRCLE_STATUSES, "同好圈", "admin.admin_circles")


@admin_bp.route("/admin/posts")
@admin_required
def admin_posts():
    _ensure_admin_schema()
    posts = Post.query.order_by(Post.created_at.desc(), Post.id.desc()).all()
    return render_template("admin_posts.html", posts=posts)


@admin_bp.route("/admin/posts/<int:post_id>/status", methods=["POST"])
@admin_required
def update_post_status(post_id):
    return _update_status(Post, post_id, CONTENT_STATUSES, "帖子", "admin.admin_posts")


@admin_bp.route("/admin/comments")
@admin_required
def admin_comments():
    _ensure_admin_schema()
    comments = Comment.query.order_by(Comment.created_at.desc(), Comment.id.desc()).all()
    return render_template("admin_comments.html", comments=comments)


@admin_bp.route("/admin/comments/<int:comment_id>/status", methods=["POST"])
@admin_required
def update_comment_status(comment_id):
    return _update_status(
        Comment,
        comment_id,
        CONTENT_STATUSES,
        "评论",
        "admin.admin_comments",
    )


@admin_bp.route("/admin/account", methods=["GET", "POST"])
@admin_required
def admin_account():
    user = get_current_user()

    if request.method == "POST":
        nickname = request.form.get("nickname", "").strip()
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not nickname:
            flash("昵称不能为空。", "error")
        elif not username:
            flash("用户名不能为空。", "error")
        elif not email:
            flash("邮箱不能为空。", "error")
        elif not current_password or not check_password_hash(user.password, current_password):
            flash("当前密码错误，无法保存管理员账号信息。", "error")
        elif User.query.filter(User.username == username, User.id != user.id).first():
            flash("该用户名已被其他用户占用，请更换后重试。", "error")
        elif User.query.filter(User.email == email, User.id != user.id).first():
            flash("该邮箱已被其他用户占用，请更换后重试。", "error")
        elif confirm_password and not new_password:
            flash("请输入新密码。", "error")
        elif new_password and new_password != confirm_password:
            flash("新密码和确认新密码不一致，无法保存。", "error")
        elif new_password and len(new_password) < 6:
            flash("新密码至少需要 6 个字符。", "error")
        else:
            user.nickname = nickname
            user.username = username
            user.email = email
            if new_password:
                user.password = generate_password_hash(new_password)

            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash("用户名或邮箱已被其他用户占用，请更换后重试。", "error")
            else:
                session["nickname"] = user.nickname or user.username
                flash("管理员账号信息已更新", "success")
                return redirect(url_for("admin.admin_account"))

    return render_template("admin_account.html", user=user)
