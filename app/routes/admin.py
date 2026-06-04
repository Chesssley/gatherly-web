from datetime import datetime
from functools import wraps
from ipaddress import ip_address

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import case, func, or_, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import (
    Activity,
    AdminLog,
    Circle,
    CircleMember,
    Comment,
    Feedback,
    Interaction,
    MerchantVerification,
    Post,
    Registration,
    User,
    create_notification,
    db,
    skip_non_sqlite_schema_helper,
)
from app.utils.email_verification import verify_email_code
from app.utils.location_utils import COUNTRY_NAME_MAP, format_ip_region, get_client_ip

admin_bp = Blueprint("admin", __name__)

USER_STATUSES = {"active", "banned"}
ACTIVITY_STATUSES = {"open", "hidden", "closed", "cancelled"}
ADMIN_ACTIVITY_CANCEL_REASON = "管理员后台取消活动"
CIRCLE_STATUSES = {"active", "hidden"}
CONTENT_STATUSES = {"published", "hidden"}
FEEDBACK_STATUSES = ("open", "replied", "closed")
SORT_OPTIONS = {"newest", "oldest"}
ADMIN_LIST_PER_PAGE = 20


class ListPagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = (total + per_page - 1) // per_page if total else 0
        self.has_prev = page > 1
        self.has_next = page < self.pages
        self.prev_num = page - 1 if self.has_prev else None
        self.next_num = page + 1 if self.has_next else None

    def iter_pages(
        self,
        left_edge=2,
        left_current=2,
        right_current=4,
        right_edge=2,
    ):
        last = 0
        for num in range(1, self.pages + 1):
            if (
                num <= left_edge
                or self.page - left_current < num < self.page + right_current
                or num > self.pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num


def _admin_page():
    return max(request.args.get("page", 1, type=int) or 1, 1)


def _paginate_query(query, per_page=ADMIN_LIST_PER_PAGE):
    return query.paginate(page=_admin_page(), per_page=per_page, error_out=False)


def _paginate_items(items, per_page=ADMIN_LIST_PER_PAGE):
    page = _admin_page()
    total = len(items)
    start = (page - 1) * per_page
    return ListPagination(items[start : start + per_page], page, per_page, total)


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


def _mask_ip_address(value):
    value = (value or "").strip()
    if not value or value.lower() == "unknown":
        return ""
    try:
        parsed_ip = ip_address(value)
    except ValueError:
        return ""
    if parsed_ip.version == 4:
        parts = value.split(".")
        if len(parts) == 4:
            return f"{parts[0]}.{parts[1]}.*.*"
    parts = parsed_ip.exploded.split(":")
    return f"{parts[0]}:{parts[1]}:*:*:*:*:*:*"


def _admin_user_ip_region_label(user):
    return format_ip_region(user) or "未知"


def _country_search_terms(query_text):
    query_text = (query_text or "").strip()
    if not query_text:
        return set()
    normalized_query = query_text.casefold()
    terms = {query_text}
    for raw_value, label in COUNTRY_NAME_MAP.items():
        if normalized_query in raw_value.casefold() or normalized_query in label.casefold():
            terms.add(raw_value)
            terms.add(label)
    return terms


def _admin_user_matches_search(user, query_text):
    normalized_query = (query_text or "").strip().casefold()
    if not normalized_query:
        return True

    generic_values = (
        user.username,
        user.nickname,
        user.email,
        user.city,
        user.interests,
        user.detected_city,
        user.detected_region,
        _admin_user_ip_region_label(user),
        user.last_ip,
        _mask_ip_address(user.last_ip),
    )
    if any(normalized_query in (value or "").casefold() for value in generic_values):
        return True

    region_values = (
        user.detected_city,
        user.detected_region,
        _admin_user_ip_region_label(user),
    )
    return any(
        term.casefold() in (value or "").casefold()
        for term in _country_search_terms(query_text)
        for value in region_values
    )


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
    # Legacy SQLite fallback only; production PostgreSQL schema is managed by migrations.
    if skip_non_sqlite_schema_helper("_ensure_admin_schema"):
        return

    AdminLog.__table__.create(db.engine, checkfirst=True)

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
            ip_address=get_client_ip(),
        )
    )


def _notify_admin_result(target, previous_status, new_status):
    related_type = None
    recipient_ids = set()
    label = f"{target.__class__.__name__} #{target.id}"

    if isinstance(target, Activity):
        related_type = "activity"
        recipient_ids.add(target.organizer_id)
        label = f"活动“{target.title}”"
        if new_status in {"closed", "cancelled"}:
            recipient_ids.update(
                row[0]
                for row in db.session.query(Registration.user_id)
                .filter_by(activity_id=target.id)
                .all()
            )
    elif isinstance(target, Circle):
        related_type = "circle"
        recipient_ids.add(target.owner_id)
        label = f"同好圈“{target.name}”"
    elif isinstance(target, Post):
        related_type = "post"
        recipient_ids.add(target.user_id)
        label = f"帖子“{target.title}”"
    elif isinstance(target, Comment):
        related_type = "comment"
        recipient_ids.add(target.author_id)
        label = f"评论 #{target.id}"

    for recipient_id in recipient_ids:
        if recipient_id:
            create_notification(
                recipient_id,
                "admin_result",
                "管理员处理结果",
                f"{label}的状态已由 {previous_status} 更新为 {new_status}。",
                related_type,
                target.id,
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


def _set_status(model, target_id, new_status, allowed_statuses, target_type, list_endpoint):
    _ensure_admin_schema()
    target = model.query.get_or_404(target_id)
    if new_status not in allowed_statuses:
        flash("无效的状态值，未进行修改。", "error")
        return redirect(url_for(list_endpoint))

    previous_status = target.status
    if previous_status == new_status:
        flash("状态没有变化。", "success")
        return redirect(url_for(list_endpoint))

    target.status = new_status
    if isinstance(target, Activity):
        if new_status == "cancelled":
            target.cancel_reason = (
                request.form.get("cancel_reason", "").strip()
                or ADMIN_ACTIVITY_CANCEL_REASON
            )
            target.cancelled_at = datetime.utcnow()
        elif previous_status == "cancelled":
            target.cancel_reason = None
            target.cancelled_at = None
    _notify_admin_result(target, previous_status, new_status)
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


def _update_status(model, target_id, allowed_statuses, target_type, list_endpoint):
    return _set_status(
        model,
        target_id,
        request.form.get("status", "").strip(),
        allowed_statuses,
        target_type,
        list_endpoint,
    )


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
        "feedback_open": Feedback.query.filter_by(status="open").count(),
        "merchant_pending": MerchantVerification.query.filter_by(status="pending").count(),
        "logs": AdminLog.query.count(),
    }
    return render_template("admin_dashboard.html", stats=stats)


@admin_bp.route("/admin/feedback")
@admin_required
def admin_feedback():
    filters = _list_filters()
    query = Feedback.query.join(Feedback.user)
    if filters["status"] in FEEDBACK_STATUSES:
        query = query.filter(Feedback.status == filters["status"])
    if filters["type"]:
        query = query.filter(Feedback.category == filters["type"])
    if filters["q"]:
        pattern = f"%{filters['q']}%"
        query = query.filter(
            or_(
                Feedback.title.ilike(pattern),
                Feedback.content.ilike(pattern),
                Feedback.category.ilike(pattern),
                User.username.ilike(pattern),
                User.nickname.ilike(pattern),
                User.email.ilike(pattern),
            )
        )

    status_rank = case(
        (Feedback.status == "open", 0),
        (Feedback.status == "replied", 1),
        else_=2,
    )
    if filters["sort"] == "oldest":
        query = query.order_by(status_rank, Feedback.created_at.asc(), Feedback.id.asc())
    else:
        query = query.order_by(status_rank, Feedback.created_at.desc(), Feedback.id.desc())

    pagination = _paginate_query(query)
    feedback_items = pagination.items
    category_options = [
        row[0]
        for row in db.session.query(Feedback.category)
        .distinct()
        .order_by(Feedback.category)
        .all()
        if row[0]
    ]
    return render_template(
        "admin_feedback_list.html",
        feedback_items=feedback_items,
        pagination=pagination,
        page=pagination.page,
        per_page=pagination.per_page,
        filters=filters,
        status_options=FEEDBACK_STATUSES,
        type_options=category_options,
    )


@admin_bp.route("/admin/feedback/<int:feedback_id>")
@admin_required
def admin_feedback_detail(feedback_id):
    feedback_item = Feedback.query.get_or_404(feedback_id)
    return render_template("admin_feedback_detail.html", feedback=feedback_item)


@admin_bp.route("/admin/feedback/<int:feedback_id>/reply", methods=["POST"])
@admin_required
def reply_feedback(feedback_id):
    feedback_item = Feedback.query.get_or_404(feedback_id)
    reply_content = request.form.get("admin_reply", "").strip()
    if not reply_content:
        flash("请填写回复内容。", "error")
        return redirect(url_for("admin.admin_feedback_detail", feedback_id=feedback_item.id))
    if len(reply_content) > 1000:
        flash("回复内容不能超过 1000 个字。", "error")
        return redirect(url_for("admin.admin_feedback_detail", feedback_id=feedback_item.id))

    admin = get_current_user()
    feedback_item.admin_reply = reply_content
    feedback_item.replied_by_id = admin.id
    feedback_item.replied_at = datetime.utcnow()
    feedback_item.status = "replied"
    create_notification(
        feedback_item.user_id,
        "feedback_reply",
        "你的反馈已收到回复",
        f"管理员已回复你的问题反馈：{feedback_item.title}",
        "feedback",
        feedback_item.id,
    )
    log_admin_action(
        admin.id,
        "reply_feedback",
        "feedback",
        feedback_item.id,
        f"category: {feedback_item.category}; title: {feedback_item.title}",
    )
    db.session.commit()
    flash("反馈回复已发送给用户。", "success")
    return redirect(url_for("admin.admin_feedback_detail", feedback_id=feedback_item.id))


@admin_bp.route("/admin/feedback/<int:feedback_id>/close", methods=["POST"])
@admin_required
def close_feedback(feedback_id):
    feedback_item = Feedback.query.get_or_404(feedback_id)
    if feedback_item.status == "closed":
        flash("该反馈已经关闭。", "info")
        return redirect(url_for("admin.admin_feedback_detail", feedback_id=feedback_item.id))

    previous_status = feedback_item.status
    feedback_item.status = "closed"
    log_admin_action(
        get_current_user().id,
        "close_feedback",
        "feedback",
        feedback_item.id,
        f"status: {previous_status} -> closed; category: {feedback_item.category}; title: {feedback_item.title}",
    )
    db.session.commit()
    flash("反馈已关闭。", "success")
    return redirect(url_for("admin.admin_feedback_detail", feedback_id=feedback_item.id))


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
    pagination = _paginate_query(_apply_sort(query, AdminLog.created_at, AdminLog.id))
    logs = pagination.items
    type_options = [
        row[0]
        for row in db.session.query(AdminLog.target_type)
        .distinct()
        .order_by(AdminLog.target_type)
        .all()
        if row[0]
    ]
    return render_template(
        "admin_logs.html",
        logs=logs,
        pagination=pagination,
        page=pagination.page,
        per_page=pagination.per_page,
        filters=filters,
        type_options=type_options,
    )


@admin_bp.route("/admin/users")
@admin_required
def admin_users():
    _ensure_admin_schema()
    filters = _list_filters()
    query = User.query
    if filters["status"]:
        query = query.filter(User.status == filters["status"])
    if filters["type"]:
        query = query.filter(User.role == filters["type"])
    users = _apply_sort(query, User.created_at, User.id).all()
    if filters["q"]:
        users = [user for user in users if _admin_user_matches_search(user, filters["q"])]
    pagination = _paginate_items(users)
    users = pagination.items
    verified_merchant_user_ids = {
        row[0]
        for row in db.session.query(MerchantVerification.user_id)
        .filter(MerchantVerification.status == "approved")
        .distinct()
        .all()
    }
    return render_template(
        "admin_users.html",
        users=users,
        pagination=pagination,
        page=pagination.page,
        per_page=pagination.per_page,
        ip_region_labels={user.id: _admin_user_ip_region_label(user) for user in users},
        masked_ip_addresses={user.id: _mask_ip_address(user.last_ip) for user in users},
        verified_merchant_user_ids=verified_merchant_user_ids,
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
    create_notification(
        user.id,
        "admin_result",
        "账号状态更新",
        f"您的账号状态已由 {previous_status} 更新为 {new_status}。",
        "user",
        user.id,
    )
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


def _update_user_merchant_status(user_id, grant):
    user = User.query.get_or_404(user_id)
    admin = get_current_user()
    approved_verifications = MerchantVerification.query.filter_by(
        user_id=user.id,
        status="approved",
    ).all()

    if grant:
        if user.status != "active":
            flash("只有正常状态的用户可以授予商家资质。", "error")
            return redirect(url_for("admin.admin_users"))
        if approved_verifications:
            flash("该用户已经拥有商家资质。", "info")
            return redirect(url_for("admin.admin_users"))

        verification = MerchantVerification(
            user_id=user.id,
            business_name=user.nickname or user.username,
            reason="管理员在用户管理中手动授予商家资质。",
            status="approved",
            reviewer_id=admin.id,
            reviewed_at=datetime.utcnow(),
        )
        db.session.add(verification)
        db.session.flush()
        create_notification(
            user.id,
            "merchant_verification_result",
            "商家资质已授予",
            "管理员已为您授予商家资质。您现在可以发布官方认证或优质活动。",
            "merchant_verification",
            verification.id,
        )
        log_admin_action(
            admin.id,
            "grant_merchant_qualification",
            "用户",
            user.id,
            "merchant_qualification: false -> true",
        )
        message = "已授予商家资质"
    else:
        if not approved_verifications:
            flash("该用户当前没有商家资质。", "info")
            return redirect(url_for("admin.admin_users"))

        for verification in approved_verifications:
            verification.status = "revoked"
            verification.reviewer_id = admin.id
            verification.reviewed_at = datetime.utcnow()
        create_notification(
            user.id,
            "merchant_verification_result",
            "商家资质已取消",
            "管理员已取消您的商家资质。您创建的活动将不再显示官方认证标识。",
            "user",
            user.id,
        )
        log_admin_action(
            admin.id,
            "revoke_merchant_qualification",
            "用户",
            user.id,
            "merchant_qualification: true -> false",
        )
        message = "已取消商家资质"

    db.session.commit()
    flash(message, "success")
    return redirect(url_for("admin.admin_users"))


@admin_bp.route("/admin/users/<int:user_id>/action", methods=["POST"])
@admin_required
def apply_user_action(user_id):
    action = request.form.get("action", "").strip()
    if action == "view":
        return redirect(url_for("profile.view_profile", user_id=user_id))
    handlers = {
        "promote_admin": promote_admin,
        "demote_admin": demote_admin,
        "ban": ban_user,
        "unban": unban_user,
    }
    if action == "grant_merchant":
        return _update_user_merchant_status(user_id, True)
    if action == "revoke_merchant":
        return _update_user_merchant_status(user_id, False)
    if action not in handlers:
        flash("请选择有效的用户操作。", "error")
        return redirect(url_for("admin.admin_users"))
    return handlers[action](user_id)


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
    pagination = _paginate_query(_apply_sort(query, Activity.created_at, Activity.id))
    activities = pagination.items
    return render_template(
        "admin_activities.html",
        activities=activities,
        pagination=pagination,
        page=pagination.page,
        per_page=pagination.per_page,
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


def _set_activity_featured(activity_id, is_featured=None):
    activity = Activity.query.get_or_404(activity_id)
    previous_value = bool(activity.is_featured)
    new_value = not previous_value if is_featured is None else bool(is_featured)
    if previous_value == new_value:
        flash("活动精选状态没有变化。", "info")
        return redirect(url_for("admin.admin_activities"))

    activity.is_featured = new_value
    log_admin_action(
        get_current_user().id,
        "feature_activity" if new_value else "unfeature_activity",
        "活动",
        activity.id,
        f"is_featured: {previous_value} -> {new_value}",
    )
    db.session.commit()
    flash("活动精选状态已更新。", "success")
    return redirect(url_for("admin.admin_activities"))


@admin_bp.route("/admin/activities/<int:activity_id>/featured", methods=["POST"])
@admin_required
def toggle_activity_featured(activity_id):
    return _set_activity_featured(activity_id)


@admin_bp.route("/admin/activities/<int:activity_id>/action", methods=["POST"])
@admin_required
def apply_activity_action(activity_id):
    action = request.form.get("action", "").strip()
    if action in ACTIVITY_STATUSES:
        return _set_status(
            Activity,
            activity_id,
            action,
            ACTIVITY_STATUSES,
            "活动",
            "admin.admin_activities",
        )
    if action == "feature":
        return _set_activity_featured(activity_id, True)
    if action == "unfeature":
        return _set_activity_featured(activity_id, False)
    flash("请选择有效的活动操作。", "error")
    return redirect(url_for("admin.admin_activities"))


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
    pagination = _paginate_query(_apply_sort(circles, Circle.created_at, Circle.id))
    circles = pagination.items
    return render_template(
        "admin_circles.html",
        circles=circles,
        pagination=pagination,
        page=pagination.page,
        per_page=pagination.per_page,
        filters=filters,
        status_options=sorted(CIRCLE_STATUSES),
        type_options=["official", "custom"],
    )


@admin_bp.route("/admin/circles/<int:circle_id>/status", methods=["POST"])
@admin_required
def update_circle_status(circle_id):
    _ensure_admin_schema()
    return _update_status(Circle, circle_id, CIRCLE_STATUSES, "同好圈", "admin.admin_circles")


@admin_bp.route("/admin/circles/<int:circle_id>/pin", methods=["POST"])
@admin_required
def toggle_circle_pin(circle_id):
    return _set_circle_pinned(circle_id)


def _set_circle_pinned(circle_id, is_pinned=None):
    _ensure_admin_schema()
    circle = Circle.query.get(circle_id)
    if circle is None or circle.status == "deleted":
        flash("同好圈不存在或已被删除。", "error")
        return redirect(url_for("admin.admin_circles"))

    previous_value = bool(circle.is_pinned)
    new_value = not previous_value if is_pinned is None else bool(is_pinned)
    if previous_value == new_value:
        flash("同好圈置顶状态没有变化。", "info")
        return redirect(url_for("admin.admin_circles"))

    circle.is_pinned = new_value
    circle.pinned_at = datetime.utcnow() if new_value else None
    log_admin_action(
        get_current_user().id,
        "pin_circle" if new_value else "unpin_circle",
        "同好圈",
        circle.id,
        f"is_pinned: {previous_value} -> {new_value}; name: {circle.name}",
    )
    db.session.commit()
    flash(
        f"同好圈“{circle.name}”已{'置顶' if new_value else '取消置顶'}。",
        "success",
    )
    return redirect(url_for("admin.admin_circles"))


@admin_bp.route("/admin/circles/<int:circle_id>/action", methods=["POST"])
@admin_required
def apply_circle_action(circle_id):
    action = request.form.get("action", "").strip()
    if action == "hide":
        return _set_status(
            Circle,
            circle_id,
            "hidden",
            CIRCLE_STATUSES,
            "同好圈",
            "admin.admin_circles",
        )
    if action == "restore":
        return _set_status(
            Circle,
            circle_id,
            "active",
            CIRCLE_STATUSES,
            "同好圈",
            "admin.admin_circles",
        )
    if action == "pin":
        return _set_circle_pinned(circle_id, True)
    if action == "unpin":
        return _set_circle_pinned(circle_id, False)
    flash("请选择有效的同好圈操作。", "error")
    return redirect(url_for("admin.admin_circles"))


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
    pagination = _paginate_query(_apply_sort(query, Post.created_at, Post.id))
    posts = pagination.items
    type_options = [
        row[0]
        for row in db.session.query(Post.type).distinct().order_by(Post.type).all()
        if row[0]
    ]
    return render_template(
        "admin_posts.html",
        posts=posts,
        pagination=pagination,
        page=pagination.page,
        per_page=pagination.per_page,
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
    Circle.query.filter_by(pinned_post_id=post.id).update(
        {"pinned_post_id": None},
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


@admin_bp.route("/admin/posts/<int:post_id>/action", methods=["POST"])
@admin_required
def apply_post_action(post_id):
    action = request.form.get("action", "").strip()
    if action == "hide":
        return _set_status(
            Post,
            post_id,
            "hidden",
            CONTENT_STATUSES,
            "帖子",
            "admin.admin_posts",
        )
    if action == "restore":
        return _set_status(
            Post,
            post_id,
            "published",
            CONTENT_STATUSES,
            "帖子",
            "admin.admin_posts",
        )
    flash("请选择有效的帖子操作。", "error")
    return redirect(url_for("admin.admin_posts"))


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
    pagination = _paginate_query(_apply_sort(query, Comment.created_at, Comment.id))
    comments = pagination.items
    return render_template(
        "admin_comments.html",
        comments=comments,
        pagination=pagination,
        page=pagination.page,
        per_page=pagination.per_page,
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


@admin_bp.route("/admin/comments/<int:comment_id>/action", methods=["POST"])
@admin_required
def apply_comment_action(comment_id):
    action = request.form.get("action", "").strip()
    if action == "hide":
        return _set_status(
            Comment,
            comment_id,
            "hidden",
            CONTENT_STATUSES,
            "评论",
            "admin.admin_comments",
        )
    if action == "restore":
        return _set_status(
            Comment,
            comment_id,
            "published",
            CONTENT_STATUSES,
            "评论",
            "admin.admin_comments",
        )
    flash("请选择有效的评论操作。", "error")
    return redirect(url_for("admin.admin_comments"))


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
        email_changed = email.lower() != (user.email or "").lower()

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
        elif email_changed and not verify_email_code(
            email,
            "change_email",
            request.form.get("email_verification_code", ""),
            user=user,
        ):
            flash("新邮箱验证码错误或已过期，请重新获取。", "error")
        elif new_password and not verify_email_code(
            user.email,
            "change_password",
            request.form.get("password_verification_code", ""),
            user=user,
        ):
            flash("改密验证码错误或已过期，请重新获取。", "error")
        else:
            user.nickname = nickname
            user.username = username
            user.email = email
            if email_changed:
                user.email_verified_at = datetime.utcnow()
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


@admin_bp.route("/admin/merchant-verifications")
@admin_required
def merchant_verifications():
    pagination = _paginate_query(
        MerchantVerification.query.join(MerchantVerification.user).order_by(
            MerchantVerification.created_at.desc(),
            MerchantVerification.id.desc(),
        )
    )
    applications = pagination.items
    return render_template(
        "admin_merchant_verifications.html",
        applications=applications,
        pagination=pagination,
        page=pagination.page,
        per_page=pagination.per_page,
    )


@admin_bp.route("/admin/merchant-verifications/<int:verification_id>/review", methods=["POST"])
@admin_required
def review_merchant_verification(verification_id):
    verification = MerchantVerification.query.get_or_404(verification_id)
    decision = request.form.get("decision", "").strip()
    reject_reason = request.form.get("reject_reason", "").strip()
    if decision not in {"approved", "rejected"}:
        flash("请选择有效的审核结果。", "error")
        return redirect(url_for("admin.merchant_verifications"))
    if verification.status != "pending":
        flash("该认证申请已经处理。", "info")
        return redirect(url_for("admin.merchant_verifications"))

    admin = get_current_user()
    verification.status = decision
    verification.reject_reason = reject_reason if decision == "rejected" else None
    verification.reviewer_id = admin.id
    verification.reviewed_at = datetime.utcnow()
    create_notification(
        verification.user_id,
        "merchant_verification_result",
        "商家认证审核结果",
        (
            f"您的商家认证申请“{verification.business_name}”已通过审核。"
            if decision == "approved"
            else f"您的商家认证申请“{verification.business_name}”未通过审核。"
            + (f" 原因：{reject_reason}" if reject_reason else "")
        ),
        "merchant_verification",
        verification.id,
    )
    log_admin_action(
        admin.id,
        "review_merchant_verification",
        "merchant_verification",
        verification.id,
        f"status: pending -> {decision}"
        + (f"; reject_reason: {reject_reason}" if reject_reason else ""),
    )
    db.session.commit()
    flash("商家认证审核结果已保存。", "success")
    return redirect(url_for("admin.merchant_verifications"))
