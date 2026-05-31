from datetime import datetime, timedelta
from functools import wraps
import os

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import and_, or_

from app.models import (
    DIRECT_MESSAGE_RETENTION_DAYS,
    DirectMessage,
    User,
    cleanup_expired_direct_messages,
    db,
    get_user_display_name,
    users_are_mutual_followers,
)
from app.utils.upload_utils import delete_saved_images, save_image_files, validate_image_files


messages_bp = Blueprint("messages", __name__, url_prefix="/messages")

MESSAGE_IMAGE_UPLOAD_SUBDIR = os.path.join("uploads", "messages")
MESSAGE_IMAGE_MAX_BYTES = 800 * 1024
MESSAGE_TEXT_MAX_LENGTH = 2000


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login", next=request.url))
        return view(*args, **kwargs)

    return wrapped


def _cleanup_expired():
    if cleanup_expired_direct_messages():
        db.session.commit()


def _conversation_query(current_user_id, other_user_id):
    return DirectMessage.query.filter(
        or_(
            and_(
                DirectMessage.sender_id == current_user_id,
                DirectMessage.recipient_id == other_user_id,
            ),
            and_(
                DirectMessage.sender_id == other_user_id,
                DirectMessage.recipient_id == current_user_id,
            ),
        )
    )


def _sent_before_mutual_follow(current_user_id, other_user_id):
    return DirectMessage.query.filter_by(
        sender_id=current_user_id,
        recipient_id=other_user_id,
    ).count()


def _can_send_message(current_user_id, other_user_id):
    if users_are_mutual_followers(current_user_id, other_user_id):
        return True
    return _sent_before_mutual_follow(current_user_id, other_user_id) == 0


def _conversation_items(current_user_id):
    messages = (
        DirectMessage.query.filter(
            or_(
                DirectMessage.sender_id == current_user_id,
                DirectMessage.recipient_id == current_user_id,
            )
        )
        .order_by(DirectMessage.created_at.desc(), DirectMessage.id.desc())
        .all()
    )
    conversations = {}
    for message in messages:
        other_user = message.recipient if message.sender_id == current_user_id else message.sender
        if not other_user or other_user.status == "deleted":
            continue
        item = conversations.setdefault(
            other_user.id,
            {
                "user": other_user,
                "display_name": get_user_display_name(other_user),
                "last_message": message,
                "unread_count": 0,
            },
        )
        if message.recipient_id == current_user_id and message.read_at is None:
            item["unread_count"] += 1
    return list(conversations.values())


@messages_bp.app_context_processor
def inject_unread_direct_message_count():
    user_id = session.get("user_id")
    if not user_id:
        return {"unread_direct_message_count": 0}
    count = DirectMessage.query.filter_by(recipient_id=user_id, read_at=None).count()
    return {"unread_direct_message_count": count}


@messages_bp.route("/")
@login_required
def message_list():
    _cleanup_expired()
    conversations = _conversation_items(session["user_id"])
    return render_template("messages.html", conversations=conversations, active_user=None)


@messages_bp.route("/<int:user_id>", methods=["GET", "POST"])
@login_required
def conversation(user_id):
    _cleanup_expired()
    current_user_id = session["user_id"]
    if user_id == current_user_id:
        flash("不能给自己发送私信。", "error")
        return redirect(url_for("messages.message_list"))

    other_user = User.query.filter(User.id == user_id, User.status != "deleted").first_or_404()
    saved_paths = []

    if request.method == "POST":
        text_content = request.form.get("content", "").strip()
        image_file = request.files.get("image")
        if not text_content and not (image_file and image_file.filename):
            flash("请输入文字或选择图片。", "error")
            return redirect(url_for("messages.conversation", user_id=user_id))
        if len(text_content) > MESSAGE_TEXT_MAX_LENGTH:
            flash(f"私信文字不能超过 {MESSAGE_TEXT_MAX_LENGTH} 个字符。", "error")
            return redirect(url_for("messages.conversation", user_id=user_id))
        if not _can_send_message(current_user_id, user_id):
            flash("未互相关注前只能发送一条私信，请互相关注后继续聊天。", "error")
            return redirect(url_for("messages.conversation", user_id=user_id))

        try:
            validated_images = validate_image_files(
                [image_file],
                max_count=1,
                max_bytes=MESSAGE_IMAGE_MAX_BYTES,
            )
            saved_paths = save_image_files(validated_images, MESSAGE_IMAGE_UPLOAD_SUBDIR)
        except ValueError as error:
            flash(str(error), "error")
            return redirect(url_for("messages.conversation", user_id=user_id))

        try:
            message = DirectMessage(
                sender_id=current_user_id,
                recipient_id=user_id,
                content=text_content or None,
                message_type="image" if saved_paths else "text",
                image_path=saved_paths[0] if saved_paths else None,
                expires_at=datetime.utcnow() + timedelta(days=DIRECT_MESSAGE_RETENTION_DAYS),
            )
            db.session.add(message)
            db.session.commit()
            flash("私信已发送。", "success")
        except Exception:
            db.session.rollback()
            delete_saved_images(saved_paths)
            flash("私信发送失败，请稍后重试。", "error")
        return redirect(url_for("messages.conversation", user_id=user_id))

    _conversation_query(current_user_id, user_id).filter(
        DirectMessage.recipient_id == current_user_id,
        DirectMessage.read_at.is_(None),
    ).update({"read_at": datetime.utcnow()}, synchronize_session=False)
    db.session.commit()

    messages = (
        _conversation_query(current_user_id, user_id)
        .order_by(DirectMessage.created_at.asc(), DirectMessage.id.asc())
        .all()
    )
    return render_template(
        "messages.html",
        conversations=_conversation_items(current_user_id),
        active_user=other_user,
        active_display_name=get_user_display_name(other_user),
        messages=messages,
        can_send_message=_can_send_message(current_user_id, user_id),
        is_mutual_follow=users_are_mutual_followers(current_user_id, user_id),
        image_max_kb=MESSAGE_IMAGE_MAX_BYTES // 1024,
        text_max_length=MESSAGE_TEXT_MAX_LENGTH,
    )
