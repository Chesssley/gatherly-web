from datetime import datetime, timedelta
from functools import wraps
import os

from flask import Blueprint, flash, jsonify, redirect, render_template, request, session, url_for
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


def _user_has_sent_message(sender_id, recipient_id):
    return DirectMessage.query.filter_by(
        sender_id=sender_id,
        recipient_id=recipient_id,
    ).first() is not None


def _message_permission_state(current_user_id, other_user_id):
    if not current_user_id:
        return {
            "can_send": False,
            "send_block_reason": "请先登录后再发送私信。",
            "mutual_follow": False,
            "has_both_sides_replied": False,
            "show_follow_suggestion": False,
        }
    if current_user_id == other_user_id:
        return {
            "can_send": False,
            "send_block_reason": "不能给自己发送私信。",
            "mutual_follow": False,
            "has_both_sides_replied": False,
            "show_follow_suggestion": False,
        }

    mutual_follow = users_are_mutual_followers(current_user_id, other_user_id)
    current_user_has_sent = _user_has_sent_message(current_user_id, other_user_id)
    other_user_has_sent = _user_has_sent_message(other_user_id, current_user_id)
    has_both_sides_replied = current_user_has_sent and other_user_has_sent

    if mutual_follow:
        can_send = True
        reason = None
    elif has_both_sides_replied:
        can_send = True
        reason = None
    elif not current_user_has_sent:
        can_send = True
        reason = None
    else:
        can_send = False
        reason = "已发送第一条私信，等待对方回复后即可继续聊天。"

    return {
        "can_send": can_send,
        "send_block_reason": reason,
        "mutual_follow": mutual_follow,
        "has_both_sides_replied": has_both_sides_replied,
        "show_follow_suggestion": (not mutual_follow) and has_both_sides_replied,
    }


def _message_notice(permission_state):
    if permission_state["mutual_follow"]:
        return None
    if permission_state["show_follow_suggestion"]:
        return "你们还没有互相关注，但已经可以继续聊天。建议关注对方，方便以后联系。"
    if permission_state["send_block_reason"]:
        return permission_state["send_block_reason"]
    return "你们还没有互相关注。对方回复前，只能发送一条私信。"


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


def _message_to_dict(message, current_user_id):
    return {
        "id": message.id,
        "sender_id": message.sender_id,
        "sender_name": get_user_display_name(message.sender),
        "content": message.content or "",
        "message_type": message.message_type,
        "image_url": (
            url_for("static", filename=message.image_path)
            if message.image_path
            else None
        ),
        "created_at": message.created_at.strftime("%Y-%m-%d %H:%M")
        if message.created_at
        else "",
        "is_mine": message.sender_id == current_user_id,
    }


def _permission_payload(current_user_id, other_user_id):
    state = _message_permission_state(current_user_id, other_user_id)
    return {
        **state,
        "notice": _message_notice(state),
    }


def _json_login_required():
    if "user_id" not in session:
        return jsonify({"ok": False, "error": "请先登录后再操作。"}), 401
    return None


def _active_message_user_or_404(user_id):
    return User.query.filter(User.id == user_id, User.status != "deleted").first_or_404()


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

    other_user = _active_message_user_or_404(user_id)
    saved_paths = []

    if request.method == "POST":
        permission_state = _message_permission_state(current_user_id, user_id)
        text_content = request.form.get("content", "").strip()
        image_file = request.files.get("image")
        if not text_content and not (image_file and image_file.filename):
            flash("请输入文字或选择图片。", "error")
            return redirect(url_for("messages.conversation", user_id=user_id))
        if len(text_content) > MESSAGE_TEXT_MAX_LENGTH:
            flash(f"私信文字不能超过 {MESSAGE_TEXT_MAX_LENGTH} 个字符。", "error")
            return redirect(url_for("messages.conversation", user_id=user_id))
        if not permission_state["can_send"]:
            flash(permission_state["send_block_reason"] or "暂时不能发送私信。", "error")
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
    permission_state = _message_permission_state(current_user_id, user_id)
    last_message_id = messages[-1].id if messages else 0
    return render_template(
        "messages.html",
        conversations=_conversation_items(current_user_id),
        active_user=other_user,
        active_display_name=get_user_display_name(other_user),
        messages=messages,
        can_send_message=permission_state["can_send"],
        send_block_reason=permission_state["send_block_reason"],
        is_mutual_follow=permission_state["mutual_follow"],
        has_both_sides_replied=permission_state["has_both_sides_replied"],
        show_follow_suggestion=permission_state["show_follow_suggestion"],
        message_notice=_message_notice(permission_state),
        last_message_id=last_message_id,
        image_max_kb=MESSAGE_IMAGE_MAX_BYTES // 1024,
        text_max_length=MESSAGE_TEXT_MAX_LENGTH,
    )


@messages_bp.route("/api/conversation/<int:user_id>/poll")
def poll_conversation(user_id):
    login_error = _json_login_required()
    if login_error:
        return login_error

    current_user_id = session["user_id"]
    if user_id == current_user_id:
        return jsonify({"ok": False, "error": "不能访问自己的私信会话。"}), 400

    _active_message_user_or_404(user_id)
    after_id = request.args.get("after_id", 0, type=int) or 0
    after_id = max(after_id, 0)

    new_messages = (
        _conversation_query(current_user_id, user_id)
        .filter(DirectMessage.id > after_id)
        .order_by(DirectMessage.created_at.asc(), DirectMessage.id.asc())
        .limit(50)
        .all()
    )
    _conversation_query(current_user_id, user_id).filter(
        DirectMessage.recipient_id == current_user_id,
        DirectMessage.read_at.is_(None),
    ).update({"read_at": datetime.utcnow()}, synchronize_session=False)
    db.session.commit()

    latest_message = (
        _conversation_query(current_user_id, user_id)
        .order_by(DirectMessage.id.desc())
        .first()
    )
    last_message_id = latest_message.id if latest_message else after_id

    return jsonify(
        {
            "ok": True,
            "messages": [_message_to_dict(message, current_user_id) for message in new_messages],
            "last_message_id": last_message_id,
            **_permission_payload(current_user_id, user_id),
        }
    )


@messages_bp.route("/api/conversation/<int:user_id>/send", methods=["POST"])
def send_conversation_message(user_id):
    login_error = _json_login_required()
    if login_error:
        return login_error

    current_user_id = session["user_id"]
    if user_id == current_user_id:
        return jsonify({"ok": False, "error": "不能给自己发送私信。"}), 400

    _active_message_user_or_404(user_id)
    permission_state = _message_permission_state(current_user_id, user_id)
    if not permission_state["can_send"]:
        return jsonify(
            {
                "ok": False,
                "error": permission_state["send_block_reason"] or "暂时不能发送私信。",
                **_permission_payload(current_user_id, user_id),
            }
        ), 403

    data = request.get_json(silent=True) or {}
    text_content = str(data.get("content", "")).strip()
    if not text_content:
        return jsonify({"ok": False, "error": "请输入私信内容。"}), 400
    if len(text_content) > MESSAGE_TEXT_MAX_LENGTH:
        return jsonify(
            {
                "ok": False,
                "error": f"私信文字不能超过 {MESSAGE_TEXT_MAX_LENGTH} 个字符。",
            }
        ), 400

    try:
        message = DirectMessage(
            sender_id=current_user_id,
            recipient_id=user_id,
            content=text_content,
            message_type="text",
            expires_at=datetime.utcnow() + timedelta(days=DIRECT_MESSAGE_RETENTION_DAYS),
        )
        db.session.add(message)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({"ok": False, "error": "私信发送失败，请稍后重试。"}), 500

    return jsonify(
        {
            "ok": True,
            "message": _message_to_dict(message, current_user_id),
            **_permission_payload(current_user_id, user_id),
        }
    )
