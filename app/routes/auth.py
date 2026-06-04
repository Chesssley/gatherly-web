# -*- coding: utf-8 -*-
"""认证相关路由（登录 / 注册 / 登出）"""

import os
import time
import unicodedata
from datetime import datetime

from flask import Blueprint, current_app, render_template, redirect, url_for, flash, request, session
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import (
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
EMAIL_CODE_SPAM_FOLDER_MESSAGE = "若在邮箱没有看到验证码，请检查邮箱垃圾箱"
EMAIL_CODE_SUCCESS_ALERT_SESSION_KEY = "email_code_success_alert"
DELETE_ACCOUNT_CONFIRM_TEXT = "DELETE MY ACCOUNT"
LOGIN_FAILURE_WINDOW_SECONDS = 5 * 60
LOGIN_FAILURE_MAX_ATTEMPTS = 5
LOGIN_FAILURE_COOLDOWN_MESSAGE = "登录尝试过于频繁，请稍后再试。"
LOGIN_FAILURE_MESSAGE = "邮箱或密码错误"
_login_failure_attempts = {}


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


@auth_bp.route("/register/send-code", methods=["POST"])
def send_register_code():
    _store_register_form_draft()
    email = (request.form.get("email") or "").strip()

    if not email:
        flash("请先填写邮箱。", "error")
        return redirect(url_for("auth.register"))
    if len(email) > 120:
        flash("邮箱不能超过 120 个字符。", "error")
        return redirect(url_for("auth.register"))
    if User.query.filter_by(email=email).first():
        flash("该邮箱已被注册，请使用其他邮箱或直接登录。", "error")
        return redirect(url_for("auth.register"))
    if _is_email_code_send_rate_limited(email, "register"):
        retry_after = _email_code_send_retry_after_seconds(email, "register")
        flash(_email_code_rate_limit_message(retry_after), "error")
        return redirect(url_for("auth.register"))

    try:
        _record_session_email_code_attempt()
        sent = send_verification_code(email, "register")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to send register verification code")
        flash("验证码发送失败，请稍后再试。", "error")
    else:
        _flash_email_code_send_result(sent)
    return redirect(url_for("auth.register"))


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
    if not email:
        flash("请先填写注册邮箱。", "error")
        return redirect(url_for("auth.forgot_password"))
    if len(email) > 120:
        flash("邮箱不能超过 120 个字符。", "error")
        return redirect(url_for("auth.forgot_password"))
    if _is_session_email_code_rate_limited():
        retry_after = _email_code_send_retry_after_seconds()
        flash(_email_code_rate_limit_message(retry_after), "error")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.filter_by(email=email, status="active").first()
    if user and is_email_code_rate_limited(email, "reset_password"):
        retry_after = _email_code_send_retry_after_seconds(email, "reset_password")
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
        flash("验证码发送失败，请稍后再试。", "error")
    else:
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
    登录页路由。
    GET：显示登录表单
    POST：验证登录表单 → 写入 session → 重定向首页
    支持 next 参数：登录成功后跳转到 next 指定的页面
    """
    next_page = request.args.get("next") or request.form.get("next", "")

    if request.method == "GET" and next_page:
        flash("请先登录后再报名活动", "info")

    if request.method == "POST":
        identifier = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not identifier or not password:
            flash(LOGIN_FAILURE_MESSAGE, "error")
            return render_template("login.html")

        if _is_login_rate_limited(identifier):
            flash(LOGIN_FAILURE_COOLDOWN_MESSAGE, "error")
            return render_template("login.html")

        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if not user or user.status != "active" or not _check_user_password(user, password):
            _record_login_failure(identifier)
            flash(LOGIN_FAILURE_MESSAGE, "error")
            return render_template("login.html")

        # 登录成功，写入 session
        _clear_login_failures(identifier)
        session.clear()
        session["user_id"] = user.id
        session["nickname"] = user.nickname or user.username
        flash(f"欢迎回来，{session['nickname']}！", "success")

        if next_page:
            return redirect(next_page)
        return redirect(url_for("activity.index"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """退出登录，清除 session 并重定向到首页"""
    session.clear()
    flash("您已退出登录", "info")
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

        if not email:
            flash("请填写注册邮箱。", "error")
        elif not user:
            flash("邮箱、验证码或新密码无效。", "error")
        elif not new_password:
            flash("请输入新密码。", "error")
        elif new_password != confirm_password:
            flash("新密码和确认新密码不一致。", "error")
        elif len(new_password) < 6:
            flash("新密码至少需要 6 个字符。", "error")
        elif not verify_email_code(email, "reset_password", email_code):
            flash("邮箱、验证码或新密码无效。", "error")
        else:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            session.pop("forgot_password_email_draft", None)
            flash("密码已重置，请使用新密码登录。", "success")
            return redirect(url_for("auth.login"))

    return render_template(
        "forgot_password.html",
        forgot_password_email_draft=session.get("forgot_password_email_draft", ""),
    )


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """
    注册页路由（US-02-01）。
    GET：显示注册表单
    POST：验证表单 → 密码加密 → 写入数据库 → 重定向到登录页
    """
    form = RegistrationForm()
    if request.method == "POST":
        _store_register_form_draft()
    register_form_draft = _get_register_form_draft()

    if form.validate_on_submit():
        username = form.username.data.strip()
        nickname = request.form.get("nickname", "").strip() or username
        email = form.email.data.strip()
        city = request.form.get("city", "").strip() or None

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("该用户名已被注册，请选择其他用户名", "error")
            return render_template(
                "register.html",
                form=form,
                register_form_draft=register_form_draft,
            )

        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash("该邮箱已被注册，请使用其他邮箱或直接登录", "error")
            return render_template(
                "register.html",
                form=form,
                register_form_draft=register_form_draft,
            )

        email_code = request.form.get("email_code", "").strip()
        if not verify_email_code(email, "register", email_code):
            flash("邮箱验证码错误或已过期，请重新获取。", "error")
            return render_template(
                "register.html",
                form=form,
                register_form_draft=register_form_draft,
            )

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
            flash("注册成功！现在可以登录了。", "success")
            return redirect(url_for("auth.login"))
        except Exception as e:
            db.session.rollback()
            if "UNIQUE constraint failed" in str(e):
                if "username" in str(e):
                    flash("该用户名已被注册，请选择其他用户名", "error")
                elif "email" in str(e):
                    flash("该邮箱已被注册，请使用其他邮箱", "error")
            else:
                flash("注册失败，请稍后重试。", "error")

    return render_template(
        "register.html",
        form=form,
        register_form_draft=register_form_draft,
    )
