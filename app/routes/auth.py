# -*- coding: utf-8 -*-
"""认证相关路由（登录 / 注册 / 登出）"""

import os
import time
import unicodedata
from datetime import date, datetime

from flask import Blueprint, current_app, jsonify, render_template, redirect, url_for, flash, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import (
    Circle,
    CircleMember,
    MerchantVerification,
    User,
    create_notification,
    db,
    ensure_merchant_verification_schema,
    ensure_user_account_schema,
)
from app.forms import RegistrationForm
from app.utils.email_verification import (
    email_configuration_error,
    email_code_retry_after_seconds,
    is_email_code_rate_limited,
    is_console_email_provider,
    send_verification_code,
    verify_email_code,
)
from app.utils.location_utils import get_client_ip
from app.utils.upload_limits import upload_limit
from app.utils.upload_utils import delete_saved_images, save_image_files, validate_upload_files

auth_bp = Blueprint("auth", __name__)
MERCHANT_DOCUMENT_LIMIT = upload_limit("merchant_verification")
MERCHANT_DOCUMENT_UPLOAD_SUBDIR = "merchant-verifications"
REGISTER_FORM_DRAFT_FIELDS = ("username", "email", "nickname", "city")
EMAIL_CODE_SESSION_LIMIT_SECONDS = 60 * 60
EMAIL_CODE_SESSION_LIMIT_MAX = 10
EMAIL_CODE_SPAM_FOLDER_MESSAGE = "若未收到验证码，请检查垃圾邮件或稍后重试。"
EMAIL_CODE_SUCCESS_ALERT_SESSION_KEY = "email_code_success_alert"
DELETE_ACCOUNT_CONFIRM_TEXT = "DELETE MY ACCOUNT"
LOGIN_FAILURE_WINDOW_SECONDS = 5 * 60
LOGIN_FAILURE_MAX_ATTEMPTS = 5
LOGIN_FAILURE_COOLDOWN_MESSAGE = "登录尝试过于频繁，请稍后再试。"
LOGIN_FAILURE_MESSAGE = "邮箱或密码错误"
PENDING_ONBOARDING_USER_SESSION_KEY = "pending_onboarding_user_id"
SIGNUP_MIN_AGE = 13
_login_failure_attempts = {}

SIGNUP_PURPOSE_OPTIONS = {
    "find_events": "发现活动，认识同好",
    "host_events": "创建同好圈或组织活动",
    "both": "两者都想试试",
}

SIGNUP_GENDER_OPTIONS = {
    "female": "女性",
    "male": "男性",
    "non_binary": "非二元 / 多元性别",
    "prefer_not": "暂不透露",
}


@auth_bp.before_app_request
def ensure_account_schema():
    ensure_user_account_schema()
    ensure_merchant_verification_schema()


def _get_session_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def _merchant_verification_redirect():
    if request.form.get("return_to") == "profile":
        return redirect(url_for("profile.my_profile"))
    return redirect(url_for("auth.account_settings"))


def _redirect_after_code_send():
    next_url = request.form.get("next", "").strip()
    if next_url:
        return redirect(next_url)
    if request.form.get("return_to") == "admin_account":
        return redirect(url_for("admin.admin_account"))
    return redirect(url_for("auth.account_settings"))


def _store_register_form_draft():
    session["register_form_draft"] = {
        field: (request.form.get(field) or "").strip()
        for field in REGISTER_FORM_DRAFT_FIELDS
    }


def _get_register_form_draft():
    return session.get("register_form_draft", {})


def _clear_register_form_draft():
    session.pop("register_form_draft", None)
    session.pop("register_email_draft", None)


def _clear_pending_onboarding():
    session.pop(PENDING_ONBOARDING_USER_SESSION_KEY, None)


def _pending_onboarding_user():
    user_id = session.get(PENDING_ONBOARDING_USER_SESSION_KEY)
    if not user_id:
        return None
    user = User.query.get(user_id)
    if user is None:
        _clear_pending_onboarding()
    return user


def _session_email_code_attempts(now=None):
    now = now or time.time()
    recent_attempts = []
    for value in session.get("email_code_send_attempts", []):
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            continue
        if now - timestamp < EMAIL_CODE_SESSION_LIMIT_SECONDS:
            recent_attempts.append(timestamp)
    session["email_code_send_attempts"] = recent_attempts
    return recent_attempts


def _session_email_code_retry_after_seconds():
    now = time.time()
    recent_attempts = sorted(_session_email_code_attempts(now))
    if len(recent_attempts) < EMAIL_CODE_SESSION_LIMIT_MAX:
        return 0
    unlock_index = max(0, len(recent_attempts) - EMAIL_CODE_SESSION_LIMIT_MAX)
    retry_after = EMAIL_CODE_SESSION_LIMIT_SECONDS - (now - recent_attempts[unlock_index])
    return max(0, int(retry_after) + 1)


def _is_session_email_code_rate_limited():
    recent_attempts = _session_email_code_attempts()
    return len(recent_attempts) >= EMAIL_CODE_SESSION_LIMIT_MAX


def _record_session_email_code_attempt():
    now = time.time()
    recent_attempts = []
    for value in session.get("email_code_send_attempts", []):
        try:
            timestamp = float(value)
        except (TypeError, ValueError):
            continue
        if now - timestamp < EMAIL_CODE_SESSION_LIMIT_SECONDS:
            recent_attempts.append(timestamp)
    recent_attempts.append(now)
    session["email_code_send_attempts"] = recent_attempts


def _client_ip():
    return get_client_ip() or "unknown"


def _login_failure_keys(identifier):
    normalized_identifier = (identifier or "").strip().lower() or "unknown"
    return (f"ip:{_client_ip()}", f"account:{normalized_identifier}")


def _recent_login_failures(key, now=None):
    now = now or time.time()
    recent = [
        timestamp
        for timestamp in _login_failure_attempts.get(key, [])
        if now - timestamp < LOGIN_FAILURE_WINDOW_SECONDS
    ]
    if recent:
        _login_failure_attempts[key] = recent
    else:
        _login_failure_attempts.pop(key, None)
    return recent


def _is_login_rate_limited(identifier):
    now = time.time()
    return any(
        len(_recent_login_failures(key, now)) >= LOGIN_FAILURE_MAX_ATTEMPTS
        for key in _login_failure_keys(identifier)
    )


def _record_login_failure(identifier):
    now = time.time()
    for key in _login_failure_keys(identifier):
        recent = _recent_login_failures(key, now)
        recent.append(now)
        _login_failure_attempts[key] = recent


def _clear_login_failures(identifier):
    for key in _login_failure_keys(identifier):
        _login_failure_attempts.pop(key, None)


def _stored_password_looks_hashed(stored_password):
    return (stored_password or "").startswith(
        ("scrypt:", "pbkdf2:", "argon2:", "sha256$", "sha512$")
    )


def _check_user_password(user, password):
    stored_password = user.password_hash or ""
    try:
        if check_password_hash(stored_password, password):
            return True
    except (TypeError, ValueError):
        pass

    if not _stored_password_looks_hashed(stored_password) and stored_password == password:
        user.password_hash = generate_password_hash(password)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return False
        return True

    return False


def _is_email_code_send_rate_limited(email, purpose):
    return _is_session_email_code_rate_limited() or is_email_code_rate_limited(
        email, purpose
    )


def _email_code_send_retry_after_seconds(email=None, purpose=None):
    return max(
        _session_email_code_retry_after_seconds(),
        email_code_retry_after_seconds(email, purpose) if email and purpose else 0,
    )


def _email_code_rate_limit_message(seconds):
    seconds = max(1, int(seconds or 1))
    return f"验证码发送过于频繁，请在 {seconds} 秒后重试。"


def _flash_email_code_send_result(sent, success_message="验证码已发送，请查收邮箱。"):
    if sent:
        if is_console_email_provider():
            flash("本地未配置邮件服务，验证码已打印到控制台。", "info")
        else:
            flash(success_message, "success")
        session[EMAIL_CODE_SUCCESS_ALERT_SESSION_KEY] = EMAIL_CODE_SPAM_FOLDER_MESSAGE
    elif configuration_error := email_configuration_error():
        flash(configuration_error, "error")
    elif is_console_email_provider():
        flash("本地未配置邮件服务，验证码已打印到控制台。", "info")
        session[EMAIL_CODE_SUCCESS_ALERT_SESSION_KEY] = EMAIL_CODE_SPAM_FOLDER_MESSAGE
    else:
        flash("验证码发送失败，请稍后再试。", "error")


def _normalize_delete_confirm_text(value):
    value = unicodedata.normalize("NFKC", value or "")
    return value.strip().upper()


def _wants_auth_json():
    return (
        request.accept_mimetypes.best == "application/json"
        or request.headers.get("Accept", "").lower().find("application/json") != -1
        or request.form.get("auth_modal_flow") == "1"
    )


def _json_error(message, status=400, errors=None, retry_after=None):
    payload = {"ok": False, "message": message}
    if errors:
        payload["errors"] = errors
    if retry_after is not None:
        payload["retry_after"] = max(1, int(retry_after or 1))
    return jsonify(payload), status


def _json_success(message, **extra):
    payload = {"ok": True, "message": message}
    payload.update(extra)
    return jsonify(payload)


def _auth_modal_redirect(view="login", next_url=None):
    params = {"auth": view}
    if next_url:
        params["next"] = next_url
    return redirect(url_for("activity.index", **params))


def _registration_form_errors(form):
    errors = []
    for field_errors in form.errors.values():
        errors.extend(field_errors)
    return errors


def _signup_interest_categories():
    try:
        from app.routes.circle import CIRCLE_CREATE_INTEREST_CATEGORIES
    except Exception:
        return [
            {"icon": "🎉", "tag": "社交活动"},
            {"icon": "🎨", "tag": "兴趣爱好"},
            {"icon": "🌲", "tag": "旅行与户外"},
            {"icon": "🎮", "tag": "游戏"},
            {"icon": "🎵", "tag": "音乐"},
            {"icon": "💻", "tag": "科技"},
        ]
    return CIRCLE_CREATE_INTEREST_CATEGORIES


def _signup_interest_tags():
    return [category["tag"] for category in _signup_interest_categories()]


def _selected_signup_interests():
    available = set(_signup_interest_tags())
    selected = []
    for value in request.form.getlist("interests"):
        tag = value.strip()
        if tag in available and tag not in selected:
            selected.append(tag)
    return selected


def _age_from_birthdate(raw_value):
    try:
        birthday = datetime.strptime((raw_value or "").strip(), "%Y-%m-%d").date()
    except ValueError:
        return None
    today = date.today()
    if birthday > today:
        return None
    return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))


def _recommended_onboarding_circles(interests, limit=6):
    query = Circle.query.filter_by(status="active")
    circles = (
        query.order_by(Circle.is_pinned.desc(), Circle.is_system.desc(), Circle.member_count.desc())
        .limit(40)
        .all()
    )
    if not circles:
        return []

    interests = set(interests or [])

    def circle_score(circle):
        score = 0
        searchable = " ".join(
            value
            for value in (circle.name, circle.tag, circle.description)
            if value
        )
        if circle.tag in interests:
            score += 20
        score += sum(6 for interest in interests if interest and interest in searchable)
        if circle.is_pinned:
            score += 4
        if circle.is_system:
            score += 2
        score += min(circle.member_count or 0, 50) / 50
        return score

    ranked = sorted(circles, key=circle_score, reverse=True)
    return ranked[:limit]


def _onboarding_template_context(user, form_values=None, errors=None):
    interests = _selected_signup_interests() if request.method == "POST" else []
    if not interests and user and user.interests:
        interests = [item.strip() for item in user.interests.replace("，", ",").split(",") if item.strip()]
    recommended_circles = _recommended_onboarding_circles(interests)
    return {
        "pending_user": user,
        "purpose_options": SIGNUP_PURPOSE_OPTIONS,
        "gender_options": SIGNUP_GENDER_OPTIONS,
        "interest_categories": _signup_interest_categories(),
        "selected_interests": interests,
        "recommended_circles": recommended_circles,
        "form_values": form_values or {},
        "onboarding_errors": errors or [],
        "min_age": SIGNUP_MIN_AGE,
    }


@auth_bp.route("/register/send-code", methods=["POST"])
def send_register_code():
    _store_register_form_draft()
    email = (request.form.get("email") or "").strip()
    wants_json = _wants_auth_json()

    if request.form.get("auth_modal_flow") == "1":
        form = RegistrationForm()
        if not form.validate():
            errors = _registration_form_errors(form)
            message = errors[0] if errors else "请检查注册信息。"
            return _json_error(message, errors=errors)

    if not email:
        if wants_json:
            return _json_error("请先填写邮箱。")
        flash("请先填写邮箱。", "error")
        return _auth_modal_redirect("register")
    if len(email) > 120:
        if wants_json:
            return _json_error("邮箱不能超过 120 个字符。")
        flash("邮箱不能超过 120 个字符。", "error")
        return _auth_modal_redirect("register")
    if User.query.filter_by(email=email).first():
        if wants_json:
            return _json_error("该邮箱已被注册，请使用其他邮箱或直接登录。")
        flash("该邮箱已被注册，请使用其他邮箱或直接登录。", "error")
        return _auth_modal_redirect("register")
    if _is_email_code_send_rate_limited(email, "register"):
        retry_after = _email_code_send_retry_after_seconds(email, "register")
        if wants_json:
            return _json_error(
                _email_code_rate_limit_message(retry_after),
                retry_after=retry_after,
            )
        flash(_email_code_rate_limit_message(retry_after), "error")
        return _auth_modal_redirect("register")

    try:
        _record_session_email_code_attempt()
        sent = send_verification_code(email, "register")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to send register verification code")
        if wants_json:
            return _json_error("验证码发送失败，请稍后再试。", status=500)
        flash("验证码发送失败，请稍后再试。", "error")
    else:
        if wants_json:
            if sent or is_console_email_provider():
                return _json_success(
                    "验证码已发送，请查收邮箱。",
                    email=email,
                    next_step="verify",
                    spam_message=EMAIL_CODE_SPAM_FOLDER_MESSAGE,
                )
            if configuration_error := email_configuration_error():
                return _json_error(configuration_error, status=500)
            return _json_error("验证码发送失败，请稍后再试。", status=500)
        _flash_email_code_send_result(sent)
    return _auth_modal_redirect("register")


@auth_bp.route("/account/email-code", methods=["POST"])
def send_account_email_code():
    user = _get_session_user()
    if user is None:
        return redirect(url_for("auth.login", next=request.form.get("next") or request.referrer or request.url))

    purpose = request.form.get("purpose", "").strip()
    if purpose == "change_password":
        session["account_settings_active_panel"] = "change-password-panel"
        email = user.email
    elif purpose == "change_email":
        session["account_settings_active_panel"] = "change-email-panel"
        email = request.form.get("email", "").strip()
        session["account_change_email_draft"] = email
        if not email:
            flash("请先填写新邮箱。", "error")
            return _redirect_after_code_send()
        if len(email) > 120:
            flash("邮箱不能超过 120 个字符。", "error")
            return _redirect_after_code_send()
        if User.query.filter(User.email == email, User.id != user.id).first():
            flash("该邮箱已被其他用户占用，请更换后重试。", "error")
            return _redirect_after_code_send()
    else:
        flash("无效的验证码用途。", "error")
        return _redirect_after_code_send()

    if _is_email_code_send_rate_limited(email, purpose):
        retry_after = _email_code_send_retry_after_seconds(email, purpose)
        flash(_email_code_rate_limit_message(retry_after), "error")
        return _redirect_after_code_send()

    try:
        _record_session_email_code_attempt()
        sent = send_verification_code(email, purpose, user=user)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to send account verification code")
        flash("验证码发送失败，请稍后再试。", "error")
    else:
        _flash_email_code_send_result(sent)
    return _redirect_after_code_send()


@auth_bp.route("/forgot-password/send-code", methods=["POST"])
def send_reset_password_code():
    email = request.form.get("email", "").strip()
    session["forgot_password_email_draft"] = email
    wants_json = _wants_auth_json()
    if not email:
        if wants_json:
            return _json_error("请先填写注册邮箱。")
        flash("请先填写注册邮箱。", "error")
        return redirect(url_for("auth.forgot_password"))
    if len(email) > 120:
        if wants_json:
            return _json_error("邮箱不能超过 120 个字符。")
        flash("邮箱不能超过 120 个字符。", "error")
        return redirect(url_for("auth.forgot_password"))
    if _is_session_email_code_rate_limited():
        retry_after = _email_code_send_retry_after_seconds()
        if wants_json:
            return _json_error(
                _email_code_rate_limit_message(retry_after),
                retry_after=retry_after,
            )
        flash(_email_code_rate_limit_message(retry_after), "error")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email, status="active").first()
    if user and is_email_code_rate_limited(email, "reset_password"):
        retry_after = _email_code_send_retry_after_seconds(email, "reset_password")
        if wants_json:
            return _json_error(
                _email_code_rate_limit_message(retry_after),
                retry_after=retry_after,
            )
        flash(_email_code_rate_limit_message(retry_after), "error")
        return redirect(url_for("auth.forgot_password"))

    _record_session_email_code_attempt()
    try:
        if user:
            sent = send_verification_code(email, "reset_password")
        else:
            sent = True
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to send reset password verification code")
        if wants_json:
            return _json_error("验证码发送失败，请稍后再试。", status=500)
        flash("验证码发送失败，请稍后再试。", "error")
    else:
        if wants_json:
            if user and not (sent or is_console_email_provider()):
                if configuration_error := email_configuration_error():
                    return _json_error(configuration_error, status=500)
                return _json_error("验证码发送失败，请稍后再试。", status=500)
            return _json_success(
                "如果该邮箱已注册，验证码将发送到对应邮箱。",
                email=email,
            )
        if user:
            _flash_email_code_send_result(
                sent,
                success_message="如果该邮箱已注册，验证码将发送到对应邮箱。",
            )
        else:
            flash("如果该邮箱已注册，验证码将发送到对应邮箱。", "success")
    return redirect(url_for("auth.forgot_password"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    登录路由。
    GET：回到首页并打开登录弹窗
    POST：验证登录表单 → 写入 session → 重定向首页
    支持 next 参数：登录成功后跳转到 next 指定的页面
    """
    next_page = request.args.get("next") or request.form.get("next", "")

    if request.method == "GET":
        return _auth_modal_redirect("login", next_page)

    if request.method == "POST":
        identifier = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        wants_json = _wants_auth_json()

        if not identifier or not password:
            if wants_json:
                return _json_error(LOGIN_FAILURE_MESSAGE)
            flash(LOGIN_FAILURE_MESSAGE, "error")
            return _auth_modal_redirect("login", next_page)

        if _is_login_rate_limited(identifier):
            if wants_json:
                return _json_error(LOGIN_FAILURE_COOLDOWN_MESSAGE, status=429)
            flash(LOGIN_FAILURE_COOLDOWN_MESSAGE, "error")
            return _auth_modal_redirect("login", next_page)

        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if not user or user.status != "active" or not _check_user_password(user, password):
            _record_login_failure(identifier)
            if wants_json:
                return _json_error(LOGIN_FAILURE_MESSAGE)
            flash(LOGIN_FAILURE_MESSAGE, "error")
            return _auth_modal_redirect("login", next_page)

        # 登录成功，写入 session
        _clear_login_failures(identifier)
        session.clear()
        session["user_id"] = user.id
        session["nickname"] = user.nickname or user.username
        flash(f"欢迎回来，{session['nickname']}！", "success")

        if wants_json:
            return _json_success(
                "登录成功。",
                redirect=next_page or url_for("activity.index"),
            )
        if next_page:
            return redirect(next_page)
        return redirect(url_for("activity.index"))

    return _auth_modal_redirect("login", next_page)


@auth_bp.route("/logout")
def logout():
    """退出登录，清除 session 并重定向到首页"""
    session.clear()
    return redirect(url_for("activity.index"))


@auth_bp.route("/account/settings")
def account_settings():
    user = _get_session_user()
    if user is None:
        return redirect(url_for("auth.login", next=request.url))
    if user.status == "deleted":
        session.clear()
        flash("该账号已注销", "error")
        return redirect(url_for("activity.index"))
    latest_merchant_verification = (
        MerchantVerification.query.filter_by(user_id=user.id)
        .order_by(MerchantVerification.created_at.desc())
        .first()
    )
    account_change_email_draft = session.get("account_change_email_draft", "")
    account_settings_active_panel = session.pop("account_settings_active_panel", None)
    if not account_settings_active_panel and account_change_email_draft:
        account_settings_active_panel = "change-email-panel"
    return render_template(
        "account_settings.html",
        user=user,
        latest_merchant_verification=latest_merchant_verification,
        account_change_email_draft=account_change_email_draft,
        account_settings_active_panel=account_settings_active_panel,
        merchant_document_limit=MERCHANT_DOCUMENT_LIMIT,
        delete_account_confirm_text=DELETE_ACCOUNT_CONFIRM_TEXT,
    )


@auth_bp.route("/account/merchant-verification", methods=["POST"])
def apply_merchant_verification():
    user = _get_session_user()
    if user is None:
        return redirect(url_for("auth.login", next=url_for("auth.account_settings")))

    business_name = request.form.get("business_name", "").strip()
    reason = request.form.get("reason", "").strip()
    contact = request.form.get("contact", "").strip()
    if not business_name:
        flash("请填写商家名称。", "error")
        return _merchant_verification_redirect()
    if not reason:
        flash("请填写认证理由。", "error")
        return _merchant_verification_redirect()
    if MerchantVerification.query.filter_by(user_id=user.id, status="pending").first():
        flash("您已有待审核的商家认证申请。", "info")
        return _merchant_verification_redirect()

    try:
        validated_documents = validate_upload_files(
            [request.files.get("document")],
            "merchant_verification",
        )
        if not validated_documents:
            raise ValueError("请上传营业执照或其他商家证明图片。")
    except ValueError as exc:
        flash(str(exc), "error")
        return _merchant_verification_redirect()

    saved_paths = []
    try:
        saved_paths = save_image_files(validated_documents, MERCHANT_DOCUMENT_UPLOAD_SUBDIR)
        verification = MerchantVerification(
            user_id=user.id,
            business_name=business_name,
            document_url=saved_paths[0],
            reason=reason,
            contact=contact or None,
        )
        db.session.add(verification)
        db.session.flush()
        for admin in User.query.filter_by(role="admin", status="active").all():
            create_notification(
                admin.id,
                "merchant_verification_application",
                "新的商家认证申请",
                f"{user.nickname or user.username} 提交了商家“{business_name}”的认证申请。",
                "merchant_verification",
                verification.id,
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
        delete_saved_images(saved_paths)
        flash("商家认证申请提交失败，请稍后重试。", "error")
        return _merchant_verification_redirect()

    flash("商家认证申请已提交。", "success")
    return _merchant_verification_redirect()


@auth_bp.route("/account/delete", methods=["POST"])
def delete_account():
    user = _get_session_user()
    if user is None:
        return redirect(url_for("auth.login", next=url_for("auth.account_settings")))
    if user.status == "deleted":
        session.clear()
        flash("该账号已注销", "error")
        return redirect(url_for("activity.index"))

    current_password = request.form.get("current_password", "")
    confirm_text = _normalize_delete_confirm_text(request.form.get("confirm_text"))
    if not _check_user_password(user, current_password):
        session["account_settings_active_panel"] = "delete-account-panel"
        flash("当前密码错误", "error")
        return redirect(url_for("auth.account_settings"))
    if confirm_text != DELETE_ACCOUNT_CONFIRM_TEXT:
        session["account_settings_active_panel"] = "delete-account-panel"
        flash(f"确认文字不正确，请输入 {DELETE_ACCOUNT_CONFIRM_TEXT}。", "error")
        return redirect(url_for("auth.account_settings"))

    old_email = user.email
    user.status = "deleted"
    user.deleted_at = datetime.utcnow()
    user.username = f"deleted_user_{user.id}"
    user.email = f"deleted_{user.id}_{old_email}"
    user.nickname = "已注销用户"
    user.avatar = None
    db.session.commit()

    session.clear()
    flash("账号已注销", "success")
    return redirect(url_for("activity.index"))


@auth_bp.route("/account/change-email", methods=["POST"])
def change_email():
    user = _get_session_user()
    if user is None:
        return redirect(url_for("auth.login", next=url_for("auth.account_settings")))
    if user.status == "deleted":
        session.clear()
        flash("该账号已注销", "error")
        return redirect(url_for("activity.index"))

    new_email = request.form.get("email", "").strip()
    current_password = request.form.get("current_password", "")
    email_code = request.form.get("email_verification_code", "")
    session["account_settings_active_panel"] = "change-email-panel"
    session["account_change_email_draft"] = new_email

    if not new_email:
        flash("新邮箱不能为空。", "error")
    elif len(new_email) > 120:
        flash("邮箱不能超过 120 个字符。", "error")
    elif new_email.lower() == (user.email or "").lower():
        flash("新邮箱与当前邮箱相同，无需修改。", "info")
    elif not current_password or not _check_user_password(user, current_password):
        flash("当前密码错误，无法修改邮箱。", "error")
    elif User.query.filter(User.email == new_email, User.id != user.id).first():
        flash("该邮箱已被其他用户占用，请更换后重试。", "error")
    elif not verify_email_code(new_email, "change_email", email_code, user=user):
        flash("新邮箱验证码错误或已过期，请重新获取。", "error")
    else:
        user.email = new_email
        user.email_verified_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("邮箱修改失败，请稍后重试。", "error")
        else:
            session.pop("account_change_email_draft", None)
            session.pop("account_settings_active_panel", None)
            flash("邮箱已更新。", "success")
    return redirect(url_for("auth.account_settings"))


@auth_bp.route("/account/change-password", methods=["POST"])
def change_password():
    user = _get_session_user()
    if user is None:
        return redirect(url_for("auth.login", next=url_for("auth.account_settings")))
    if user.status == "deleted":
        session.clear()
        flash("该账号已注销", "error")
        return redirect(url_for("activity.index"))

    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm_password = request.form.get("confirm_password", "")
    password_code = request.form.get("password_verification_code", "")
    session["account_settings_active_panel"] = "change-password-panel"

    if not current_password or not _check_user_password(user, current_password):
        flash("当前密码错误，无法修改密码。", "error")
    elif not new_password:
        flash("请输入新密码。", "error")
    elif new_password != confirm_password:
        flash("新密码和确认新密码不一致。", "error")
    elif len(new_password) < 6:
        flash("新密码至少需要 6 个字符。", "error")
    elif not verify_email_code(user.email, "change_password", password_code, user=user):
        flash("改密验证码错误或已过期，请重新获取。", "error")
    else:
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        session.pop("account_settings_active_panel", None)
        flash("密码已更新，请使用新密码登录。", "success")
    return redirect(url_for("auth.account_settings"))


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        session["forgot_password_email_draft"] = email
        email_code = request.form.get("email_code", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        user = User.query.filter_by(email=email, status="active").first()
        wants_json = _wants_auth_json()

        if not email:
            if wants_json:
                return _json_error("请填写注册邮箱。")
            flash("请填写注册邮箱。", "error")
        elif not user:
            if wants_json:
                return _json_error("邮箱、验证码或新密码无效。")
            flash("邮箱、验证码或新密码无效。", "error")
        elif not new_password:
            if wants_json:
                return _json_error("请输入新密码。")
            flash("请输入新密码。", "error")
        elif new_password != confirm_password:
            if wants_json:
                return _json_error("新密码和确认新密码不一致。")
            flash("新密码和确认新密码不一致。", "error")
        elif len(new_password) < 6:
            if wants_json:
                return _json_error("新密码至少需要 6 个字符。")
            flash("新密码至少需要 6 个字符。", "error")
        elif not verify_email_code(email, "reset_password", email_code):
            if wants_json:
                return _json_error("邮箱、验证码或新密码无效。")
            flash("邮箱、验证码或新密码无效。", "error")
        else:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            session.pop("forgot_password_email_draft", None)
            flash("密码已重置，请使用新密码登录。", "success")
            if wants_json:
                return _json_success("密码已重置，请使用新密码登录。")
            return _auth_modal_redirect("login")

    return render_template(
        "forgot_password.html",
        forgot_password_email_draft=session.get("forgot_password_email_draft", ""),
    )


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    注册路由（US-02-01）。
    GET：回到首页并打开注册弹窗
    POST：验证表单 → 密码加密 → 写入数据库 → 重定向到登录页
    """
    if request.method == "GET":
        return _auth_modal_redirect("register")

    form = RegistrationForm()
    if request.method == "POST":
        _store_register_form_draft()
    register_form_draft = _get_register_form_draft()

    wants_json = _wants_auth_json()

    if form.validate_on_submit():
        username = form.username.data.strip()
        nickname = request.form.get("nickname", "").strip() or username
        email = form.email.data.strip()
        city = request.form.get("city", "").strip() or None

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            if wants_json:
                return _json_error("该用户名已被注册，请选择其他用户名")
            flash("该用户名已被注册，请选择其他用户名", "error")
            return _auth_modal_redirect("register")

        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            if wants_json:
                return _json_error("该邮箱已被注册，请使用其他邮箱或直接登录")
            flash("该邮箱已被注册，请使用其他邮箱或直接登录", "error")
            return _auth_modal_redirect("register")

        email_code = request.form.get("email_code", "").strip()
        if not verify_email_code(email, "register", email_code):
            if wants_json:
                return _json_error("邮箱验证码错误或已过期，请重新获取。")
            flash("邮箱验证码错误或已过期，请重新获取。", "error")
            return _auth_modal_redirect("register")

        hashed_password = generate_password_hash(form.password.data)

        new_user = User(
            username=username,
            nickname=nickname,
            email=email,
            city=city,
            email_verified_at=datetime.utcnow(),
            password_hash=hashed_password,
            role="user",
            trust_score=100,
        )

        try:
            db.session.add(new_user)
            db.session.commit()
            _clear_register_form_draft()
            session[PENDING_ONBOARDING_USER_SESSION_KEY] = new_user.id
            flash("邮箱验证通过，请完成最后几步设置。", "success")
            if wants_json:
                return _json_success(
                    "邮箱验证通过，请继续完成注册。",
                    email=email,
                    redirect=url_for("auth.signup_onboarding"),
                )
            return redirect(url_for("auth.signup_onboarding"))
        except Exception as e:
            db.session.rollback()
            if "UNIQUE constraint failed" in str(e):
                if "username" in str(e):
                    if wants_json:
                        return _json_error("该用户名已被注册，请选择其他用户名")
                    flash("该用户名已被注册，请选择其他用户名", "error")
                elif "email" in str(e):
                    if wants_json:
                        return _json_error("该邮箱已被注册，请使用其他邮箱")
                    flash("该邮箱已被注册，请使用其他邮箱", "error")
            else:
                if wants_json:
                    return _json_error("注册失败，请稍后重试。", status=500)
                flash("注册失败，请稍后重试。", "error")
    elif request.method == "POST" and wants_json:
        errors = _registration_form_errors(form)
        return _json_error(errors[0] if errors else "请检查注册信息。", errors=errors)

    return _auth_modal_redirect("register")


@auth_bp.route("/register/onboarding", methods=["GET", "POST"])
def signup_onboarding():
    if session.get("user_id"):
        return redirect(url_for("activity.index"))

    user = _pending_onboarding_user()
    if user is None:
        flash("请先完成邮箱验证后继续注册。", "error")
        return _auth_modal_redirect("register")

    if request.method == "POST":
        form_values = {
            "purpose": request.form.get("purpose", "").strip(),
            "birthdate": request.form.get("birthdate", "").strip(),
            "gender": request.form.get("gender", "").strip(),
        }
        selected_interests = _selected_signup_interests()
        selected_circle_ids = []
        for value in request.form.getlist("circle_ids"):
            try:
                selected_circle_ids.append(int(value))
            except (TypeError, ValueError):
                continue

        errors = []
        if form_values["purpose"] not in SIGNUP_PURPOSE_OPTIONS:
            errors.append("请选择你使用聚场的主要目的。")
        age = _age_from_birthdate(form_values["birthdate"])
        if age is None:
            errors.append("请填写有效的生日。")
        elif age < SIGNUP_MIN_AGE:
            errors.append(f"你需要年满 {SIGNUP_MIN_AGE} 岁才能注册聚场。")
        if form_values["gender"] not in SIGNUP_GENDER_OPTIONS:
            errors.append("请选择性别 / 偏好，或选择暂不透露。")
        if not selected_interests:
            errors.append("请至少选择 1 个兴趣。")
        if len(", ".join(selected_interests)) > 500:
            errors.append("兴趣标签总长度不能超过 500 个字符。")

        if errors:
            return render_template(
                "signup_onboarding.html",
                **_onboarding_template_context(user, form_values=form_values, errors=errors),
            )

        try:
            user.interests = ", ".join(selected_interests)
            if selected_circle_ids:
                circles = Circle.query.filter(
                    Circle.id.in_(selected_circle_ids),
                    Circle.status == "active",
                ).all()
                existing_memberships = {
                    row.circle_id
                    for row in CircleMember.query.filter_by(user_id=user.id).all()
                }
                for circle in circles:
                    if circle.id in existing_memberships:
                        continue
                    db.session.add(
                        CircleMember(
                            circle_id=circle.id,
                            user_id=user.id,
                            status="active",
                        )
                    )
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to complete signup onboarding")
            return render_template(
                "signup_onboarding.html",
                **_onboarding_template_context(
                    user,
                    form_values=form_values,
                    errors=["完成注册失败，请稍后再试。"],
                ),
            )

        session.clear()
        session["user_id"] = user.id
        session["nickname"] = user.nickname or user.username
        flash("欢迎加入聚场！已根据你的兴趣准备首页推荐。", "success")
        return redirect(url_for("activity.index"))

    return render_template(
        "signup_onboarding.html",
        **_onboarding_template_context(user),
    )
