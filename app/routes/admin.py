from datetime import datetime
from functools import wraps

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import Activity, AdminLog, Circle, CircleMember, Comment, Interaction, Post, User, db

admin_bp = Blueprint("admin", __name__)

USER_STATUSES = {"active", "banned"}
ACTIVITY_STATUSES = {"open", "hidden", "closed"}
CIRCLE_STATUSES = {"active", "hidden"}
CONTENT_STATUSES = {"published", "hidden"}
SORT_OPTIONS = {"newest", "oldest"}


def _list_filters():
    return {
        "q": request.args.get("q", "").strip(),
        "status": request.args.get("status", "").strip(),
        "type": request.args.get("type", "").strip(),
        "sort": request.args.get("sort", "newest").strip()
        if request.args.get("sort", "newest").strip() in SORT_OPTIONS
        else "newest",
    }


def _apply_sort(query, created_at, item_id):
    if request.args.get("sort") == "oldest":
        return query.order_by(created_at.asc(), item_id.asc())
    return query.order_by(created_at.desc(), item_id.desc())


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
        "circles": Circle.query.filter(Circle.status != "deleted").count(),
        "posts": Post.query.count(),
        "comments": Comment.query.count(),
    }
    logs = AdminLog.query.order_by(AdminLog.created_at.desc()).limit(30).all()
    return render_template("admin_dashboard.html", stats=stats, logs=logs)


@admin_bp.route("/admin/logs")
@admin_required
def admin_logs():
    _ensure_admin_schema()
    filters = _list_filters()
    query = AdminLog.query.join(AdminLog.admin)
    if filters["q"]:
        pattern = f"%{filters['q']}%"
        query = query.filter(
            or_(
                User.username.ilike(pattern),
                AdminLog.action.ilike(pattern),
                AdminLog.target_type.ilike(pattern),
                AdminLog.detail.ilike(pattern),
                AdminLog.ip_address.ilike(pattern),
            )
        )
    if filters["type"]:
        query = query.filter(AdminLog.target_type == filters["type"])
    logs = _apply_sort(query, AdminLog.created_at, AdminLog.id).limit(100).all()
    type_options = [
        row[0]
        for row in db.session.query(AdminLog.target_type)
        .distinct()
        .order_by(AdminLog.target_type)
        .all()
        if row[0]
    ]
    return render_template("admin_logs.html", logs=logs, filters=filters, type_options=type_options)


@admin_bp.route("/admin/users")
@admin_required
def admin_users():
    _ensure_admin_schema()
    filters = _list_filters()
    query = User.query
    if filters["q"]:
        pattern = f"%{filters['q']}%"
        query = query.filter(
            or_(
                User.username.ilike(pattern),
                User.nickname.ilike(pattern),
                User.email.ilike(pattern),
                User.interests.ilike(pattern),
            )
        )
    if filters["status"]:
        query = query.filter(User.status == filters["status"])
    if filters["type"]:
        query = query.filter(User.role == filters["type"])
    users = _apply_sort(query, User.created_at, User.id).all()
    return render_template(
        "admin_users.html",
        users=users,
        filters=filters,
        status_options=sorted(USER_STATUSES | {"deleted"}),
        type_options=["user", "admin"],
    )


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
    filters = _list_filters()
    query = Activity.query.join(Activity.organizer)
    if filters["q"]:
        pattern = f"%{filters['q']}%"
        query = query.filter(
            or_(
                Activity.title.ilike(pattern),
                Activity.description.ilike(pattern),
                Activity.location.ilike(pattern),
                Activity.preparation.ilike(pattern),
                User.username.ilike(pattern),
            )
        )
    if filters["status"]:
        query = query.filter(Activity.status == filters["status"])
    activities = _apply_sort(query, Activity.created_at, Activity.id).all()
    return render_template(
        "admin_activities.html",
        activities=activities,
        filters=filters,
        status_options=sorted(ACTIVITY_STATUSES),
    )


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
    filters = _list_filters()
    circles = (
        db.session.query(Circle, func.count(Post.id).label("post_count"))
        .outerjoin(Post, Post.circle_id == Circle.id)
        .filter(Circle.status != "deleted")
    )
    if filters["q"]:
        pattern = f"%{filters['q']}%"
        circles = circles.filter(
            or_(
                Circle.name.ilike(pattern),
                Circle.tag.ilike(pattern),
                Circle.description.ilike(pattern),
            )
        )
    if filters["status"]:
        circles = circles.filter(Circle.status == filters["status"])
    if filters["type"] == "official":
        circles = circles.filter(Circle.is_system.is_(True))
    elif filters["type"] == "custom":
        circles = circles.filter(Circle.is_system.is_(False))
    circles = circles.group_by(Circle.id)
    circles = _apply_sort(circles, Circle.created_at, Circle.id).all()
    return render_template(
        "admin_circles.html",
        circles=circles,
        filters=filters,
        status_options=sorted(CIRCLE_STATUSES),
        type_options=["official", "custom"],
    )


@admin_bp.route("/admin/circles/<int:circle_id>/status", methods=["POST"])
@admin_required
def update_circle_status(circle_id):
    _ensure_admin_schema()
    return _update_status(Circle, circle_id, CIRCLE_STATUSES, "同好圈", "admin.admin_circles")


@admin_bp.route("/admin/posts")
@admin_required
def admin_posts():
    _ensure_admin_schema()
    filters = _list_filters()
    query = Post.query.join(Post.user).join(Post.circle)
    if filters["q"]:
        pattern = f"%{filters['q']}%"
        query = query.filter(
            or_(
                Post.title.ilike(pattern),
                Post.content.ilike(pattern),
                User.username.ilike(pattern),
                Circle.name.ilike(pattern),
                Circle.tag.ilike(pattern),
            )
        )
    if filters["status"]:
        query = query.filter(Post.status == filters["status"])
    if filters["type"]:
        query = query.filter(Post.type == filters["type"])
    posts = _apply_sort(query, Post.created_at, Post.id).all()
    type_options = [
        row[0]
        for row in db.session.query(Post.type).distinct().order_by(Post.type).all()
        if row[0]
    ]
    return render_template(
        "admin_posts.html",
        posts=posts,
        filters=filters,
        status_options=sorted(CONTENT_STATUSES | {"deleted"}),
        type_options=type_options,
    )


def _delete_comment_record(comment):
    Comment.query.filter_by(parent_id=comment.id).update(
        {"parent_id": comment.parent_id},
        synchronize_session=False,
    )
    Interaction.query.filter_by(target_type="comment", target_id=comment.id).delete(
        synchronize_session=False,
    )
    db.session.delete(comment)


def _delete_post_comments(post):
    comments = Comment.query.filter_by(post_id=post.id).all()
    comments_by_parent = {}
    for comment in comments:
        comments_by_parent.setdefault(comment.parent_id, []).append(comment)

    ordered_comments = []
    visited_ids = set()

    def collect_children_first(comment):
        if comment.id in visited_ids:
            return
        visited_ids.add(comment.id)
        for reply in comments_by_parent.get(comment.id, []):
            collect_children_first(reply)
        ordered_comments.append(comment)

    for comment in comments:
        collect_children_first(comment)

    for comment in ordered_comments:
        Interaction.query.filter_by(target_type="comment", target_id=comment.id).delete(
            synchronize_session=False,
        )
        db.session.delete(comment)


def _delete_post_record(post):
    _delete_post_comments(post)
    Interaction.query.filter_by(target_type="post", target_id=post.id).delete(
        synchronize_session=False,
    )
    db.session.delete(post)


@admin_bp.route("/admin/circles/<int:circle_id>/delete", methods=["POST"])
@admin_required
def delete_circle(circle_id):
    _ensure_admin_schema()
    circle = Circle.query.get(circle_id)
    if circle is None or circle.status == "deleted":
        flash("同好圈不存在或已被删除。", "error")
        return redirect(url_for("admin.admin_circles"))

    admin = get_current_user()
    circle_name = circle.name
    try:
        for post in Post.query.filter_by(circle_id=circle.id).all():
            _delete_post_record(post)
        CircleMember.query.filter_by(circle_id=circle.id).delete(synchronize_session=False)
        if circle.is_system:
            # Keep a tombstone so automatic official-circle synchronization
            # does not recreate a deleted official circle.
            circle.status = "deleted"
        else:
            db.session.delete(circle)
        log_admin_action(
            admin.id,
            "delete_circle",
            "同好圈",
            circle.id,
            f"name: {circle_name}",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("同好圈删除失败，请稍后重试。", "error")
    else:
        flash(f"同好圈“{circle_name}”已删除。", "success")
    return redirect(url_for("admin.admin_circles"))


@admin_bp.route("/admin/posts/<int:post_id>/delete", methods=["POST"])
@admin_required
def delete_post(post_id):
    _ensure_admin_schema()
    post = Post.query.get(post_id)
    if post is None:
        flash("帖子不存在或已被删除。", "error")
        return redirect(url_for("admin.admin_posts"))

    admin = get_current_user()
    post_title = post.title
    try:
        _delete_post_record(post)
        log_admin_action(
            admin.id,
            "delete_post",
            "帖子",
            post.id,
            f"title: {post_title}",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("帖子删除失败，请稍后重试。", "error")
    else:
        flash(f"帖子《{post_title}》已删除。", "success")
    return redirect(url_for("admin.admin_posts"))


@admin_bp.route("/admin/posts/<int:post_id>/status", methods=["POST"])
@admin_required
def update_post_status(post_id):
    return _update_status(Post, post_id, CONTENT_STATUSES, "帖子", "admin.admin_posts")


@admin_bp.route("/admin/comments")
@admin_required
def admin_comments():
    _ensure_admin_schema()
    filters = _list_filters()
    query = Comment.query.join(Comment.author).outerjoin(Comment.post).outerjoin(Post.circle)
    if filters["q"]:
        pattern = f"%{filters['q']}%"
        query = query.filter(
            or_(
                Comment.content.ilike(pattern),
                User.username.ilike(pattern),
                Post.title.ilike(pattern),
                Circle.name.ilike(pattern),
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
    comments = _apply_sort(query, Comment.created_at, Comment.id).all()
    return render_template(
        "admin_comments.html",
        comments=comments,
        filters=filters,
        status_options=sorted(CONTENT_STATUSES | {"deleted"}),
        type_options=["post", "activity", "reply"],
    )


@admin_bp.route("/admin/comments/<int:comment_id>/delete", methods=["POST"])
@admin_required
def delete_comment(comment_id):
    _ensure_admin_schema()
    comment = Comment.query.get(comment_id)
    if comment is None:
        flash("评论不存在或已被删除。", "error")
        return redirect(url_for("admin.admin_comments"))

    admin = get_current_user()
    comment_summary = comment.content.strip()[:40] or "(无文字内容)"
    try:
        _delete_comment_record(comment)
        log_admin_action(
            admin.id,
            "delete_comment",
            "评论",
            comment.id,
            f"content: {comment_summary}",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("评论删除失败，请稍后重试。", "error")
    else:
        flash("评论已删除。", "success")
    return redirect(url_for("admin.admin_comments"))


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
