from datetime import datetime
from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from app.models import Notification, User, cleanup_expired_notifications, db


notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login", next=request.url))
        return view(*args, **kwargs)

    return wrapped


def _cleanup_expired():
    if cleanup_expired_notifications():
        db.session.commit()


def _notification_url(notification):
    if notification.related_type == "activity" and notification.related_id:
        return url_for("activity.activity_detail", activity_id=notification.related_id)
    if notification.related_type == "circle" and notification.related_id:
        return url_for("circle.circle_detail", circle_id=notification.related_id)
    if notification.related_type == "merchant_verification":
        user = db.session.get(User, session.get("user_id"))
        if user and user.role == "admin":
            return url_for("admin.merchant_verifications")
        return url_for("auth.account_settings")
    return None


def _json_login_required():
    if "user_id" not in session:
        return jsonify({"ok": False, "error": "请先登录后再操作。"}), 401
    return None


def _notification_summary_item(notification):
    return {
        "id": notification.id,
        "text": notification.title,
        "url": _notification_url(notification),
        "created_at": (
            notification.created_at.strftime("%Y-%m-%d %H:%M")
            if notification.created_at
            else ""
        ),
    }


@notifications_bp.app_context_processor
def inject_unread_notification_count():
    user_id = session.get("user_id")
    if not user_id:
        return {"unread_notification_count": 0}
    count = Notification.query.filter_by(recipient_id=user_id, read_at=None).count()
    return {"unread_notification_count": count}


@notifications_bp.route("/summary")
def summary():
    login_error = _json_login_required()
    if login_error:
        return login_error

    user_id = session["user_id"]
    unread_count = Notification.query.filter_by(
        recipient_id=user_id,
        read_at=None,
    ).count()
    latest_notifications = (
        Notification.query.filter_by(recipient_id=user_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(5)
        .all()
    )
    return jsonify(
        {
            "ok": True,
            "unread_count": unread_count,
            "has_unread": unread_count > 0,
            "latest": [
                _notification_summary_item(notification)
                for notification in latest_notifications
            ],
        }
    ), 200


@notifications_bp.route("/")
@login_required
def notification_list():
    _cleanup_expired()
    notifications = (
        Notification.query.filter_by(recipient_id=session["user_id"])
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(100)
        .all()
    )
    return render_template(
        "notifications.html",
        notifications=[
            {"notification": notification, "url": _notification_url(notification)}
            for notification in notifications
        ],
    )


@notifications_bp.route("/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_read(notification_id):
    notification = Notification.query.filter_by(
        id=notification_id,
        recipient_id=session["user_id"],
    ).first_or_404()
    if notification.read_at is None:
        notification.read_at = datetime.utcnow()
        db.session.commit()
    return redirect(request.form.get("next") or url_for("notifications.notification_list"))


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read():
    Notification.query.filter_by(
        recipient_id=session["user_id"],
        read_at=None,
    ).update({"read_at": datetime.utcnow()}, synchronize_session=False)
    db.session.commit()
    return redirect(url_for("notifications.notification_list"))
