# -*- coding: utf-8 -*-
"""Email verification code helpers."""

import hashlib
import hmac
import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

from flask import current_app
import requests

from app.models import EmailVerificationCode, db


EMAIL_CODE_TTL_MINUTES = 10
EMAIL_CODE_RATE_LIMIT_RULES = (
    (timedelta(seconds=60), 1),
    (timedelta(hours=1), 5),
    (timedelta(hours=24), 10),
)
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
PURPOSE_LABELS = {
    "register": "注册账号",
    "change_email": "更改邮箱",
    "change_password": "更改密码",
    "reset_password": "重置密码",
}


def _normalized_email(email):
    return (email or "").strip().lower()


def _code_hash(email, purpose, code):
    secret = current_app.config.get("SECRET_KEY") or "dev-secret-key"
    message = f"{_normalized_email(email)}:{purpose}:{code}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _mail_bool(name):
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_production_env():
    value = (
        os.environ.get("APP_ENV")
        or os.environ.get("FLASK_ENV")
        or os.environ.get("ENV")
        or ""
    )
    return value.strip().lower() in {"production", "prod"}


def _email_provider():
    provider = os.environ.get("EMAIL_PROVIDER", "").strip().lower()
    if provider:
        return provider
    if (
        os.environ.get("BREVO_API_KEY")
        or os.environ.get("BREVO_SENDER_EMAIL")
        or os.environ.get("MAIL_SENDER_EMAIL")
        or os.environ.get("MAIL_FROM")
        or os.environ.get("RENDER")
        or _is_production_env()
    ):
        return "brevo"
    return "console"


def is_console_email_provider():
    return _email_provider() == "console"


def is_email_code_rate_limited(email, purpose):
    """Return True when an email+purpose has too many recent code sends."""
    email = _normalized_email(email)
    purpose = (purpose or "").strip()
    if not email or not purpose:
        return False

    now = datetime.utcnow()
    for window, max_attempts in EMAIL_CODE_RATE_LIMIT_RULES:
        recent_count = EmailVerificationCode.query.filter(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == purpose,
            EmailVerificationCode.created_at >= now - window,
        ).count()
        if recent_count >= max_attempts:
            return True
    return False


def _email_api_timeout():
    value = os.environ.get("EMAIL_API_TIMEOUT", "15").strip()
    try:
        return float(value)
    except ValueError:
        current_app.logger.warning(
            "Invalid EMAIL_API_TIMEOUT=%r; using default 15 seconds", value
        )
        return 15.0


def _mail_config():
    return {
        "server": os.environ.get("MAIL_SERVER", "").strip(),
        "port": int(os.environ.get("MAIL_PORT", "587") or 587),
        "username": os.environ.get("MAIL_USERNAME", "").strip(),
        "password": os.environ.get("MAIL_PASSWORD", ""),
        "use_tls": _mail_bool("MAIL_USE_TLS"),
        "sender": _first_env_value("MAIL_DEFAULT_SENDER", "MAIL_FROM"),
    }


def _first_env_value(*names):
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def email_configuration_error():
    provider = _email_provider()
    if provider == "brevo":
        missing = []
        if not os.environ.get("BREVO_API_KEY", "").strip():
            missing.append("BREVO_API_KEY")
        if not _first_env_value("BREVO_SENDER_EMAIL", "MAIL_SENDER_EMAIL", "MAIL_FROM"):
            missing.append("BREVO_SENDER_EMAIL or MAIL_SENDER_EMAIL or MAIL_FROM")
        if missing:
            return (
                "邮件服务配置缺失，请联系管理员检查 Render 环境变量："
                + ", ".join(missing)
            )
    if provider == "smtp":
        config = _mail_config()
        missing = [
            name
            for name, value in (
                ("MAIL_SERVER", config["server"]),
                ("MAIL_DEFAULT_SENDER or MAIL_FROM", config["sender"]),
            )
            if not value
        ]
        if missing:
            return (
                "邮件服务配置缺失，请联系管理员检查 Render 环境变量："
                + ", ".join(missing)
            )
    return None


def _smtp_ready(config):
    return bool(config["server"] and config["port"] and config["sender"])


def _send_mail_smtp(to_email, subject, body):
    config = _mail_config()
    if not _smtp_ready(config):
        missing = [
            name
            for name, value in (
                ("MAIL_SERVER", config["server"]),
                ("MAIL_DEFAULT_SENDER or MAIL_FROM", config["sender"]),
            )
            if not value
        ]
        current_app.logger.error(
            "SMTP email is not configured; missing environment variable(s): %s",
            ", ".join(missing),
        )
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config["sender"]
    message["To"] = to_email
    message.set_content(body)

    with smtplib.SMTP(config["server"], config["port"], timeout=15) as smtp:
        if config["use_tls"]:
            smtp.starttls()
        if config["username"] or config["password"]:
            smtp.login(config["username"], config["password"])
        smtp.send_message(message)
    return True


def _send_mail_brevo(to_email, subject, body):
    api_key = os.environ.get("BREVO_API_KEY", "").strip()
    sender_email = _first_env_value(
        "BREVO_SENDER_EMAIL",
        "MAIL_SENDER_EMAIL",
        "MAIL_FROM",
    )
    sender_name = _first_env_value("BREVO_SENDER_NAME", "MAIL_SENDER_NAME") or "Gatherly"

    if not api_key or not sender_email:
        missing = []
        if not api_key:
            missing.append("BREVO_API_KEY")
        if not sender_email:
            missing.append("BREVO_SENDER_EMAIL or MAIL_SENDER_EMAIL or MAIL_FROM")
        current_app.logger.error(
            "Brevo email API is not configured; missing environment variable(s): %s",
            ", ".join(missing),
        )
        return False

    payload = {
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "to": [
            {
                "email": to_email,
            }
        ],
        "subject": subject,
        "textContent": body,
    }
    try:
        response = requests.post(
            BREVO_API_URL,
            json=payload,
            headers={
                "api-key": api_key,
                "accept": "application/json",
                "content-type": "application/json",
            },
            timeout=_email_api_timeout(),
        )
    except requests.RequestException:
        current_app.logger.exception("Brevo email API request failed for %s", to_email)
        return False

    if 200 <= response.status_code < 300:
        return True

    current_app.logger.error(
        "Brevo email API returned HTTP %s for %s: %s",
        response.status_code,
        to_email,
        response.text[:500],
    )
    return False


def _send_mail_console(to_email, purpose, code):
    current_app.logger.info(
        "Console email provider; verification code for %s/%s is %s",
        purpose,
        to_email,
        code,
    )
    print(f"[DEV EMAIL CODE] {purpose} {to_email}: {code}")
    return True


def _send_mail(to_email, subject, body):
    provider = _email_provider()
    if provider == "brevo":
        return _send_mail_brevo(to_email, subject, body)
    if provider == "smtp":
        try:
            return _send_mail_smtp(to_email, subject, body)
        except (OSError, smtplib.SMTPException):
            current_app.logger.exception("SMTP email send failed for %s", to_email)
            return False
    if provider == "console":
        return None

    current_app.logger.error(
        "Unsupported EMAIL_PROVIDER=%r; expected brevo, smtp, or console", provider
    )
    return False


def send_verification_code(email, purpose, user=None):
    """Create a short-lived code, store only its hash, and send it.

    When the console provider is selected locally, the code is printed to the app console
    to keep development unblocked.
    """
    email = _normalized_email(email)
    code = f"{secrets.randbelow(1000000):06d}"
    now = datetime.utcnow()
    user_id = user.id if user else None

    label = PURPOSE_LABELS.get(purpose, "邮箱确认")
    subject = f"Gatherly {label}验证码"
    body = (
        f"你的 Gatherly {label}验证码是：{code}\n\n"
        f"验证码 {EMAIL_CODE_TTL_MINUTES} 分钟内有效，请勿转发给他人。"
    )
    sent = _send_mail(email, subject, body)
    if sent is None and is_console_email_provider():
        sent = _send_mail_console(email, purpose, code)
    if not sent:
        db.session.rollback()
        return False

    EmailVerificationCode.query.filter_by(
        email=email,
        purpose=purpose,
        user_id=user_id,
        used_at=None,
    ).update({"used_at": now}, synchronize_session=False)

    verification = EmailVerificationCode(
        user_id=user_id,
        email=email,
        code=_code_hash(email, purpose, code),
        purpose=purpose,
        expires_at=now + timedelta(minutes=EMAIL_CODE_TTL_MINUTES),
    )
    db.session.add(verification)
    db.session.commit()
    return True


def verify_email_code(email, purpose, code, user=None):
    email = _normalized_email(email)
    code = (code or "").strip()
    if not (len(code) == 6 and code.isdigit()):
        return False

    now = datetime.utcnow()
    user_id = user.id if user else None
    rows = (
        EmailVerificationCode.query.filter(
            EmailVerificationCode.email == email,
            EmailVerificationCode.purpose == purpose,
            EmailVerificationCode.user_id == user_id,
            EmailVerificationCode.used_at.is_(None),
            EmailVerificationCode.expires_at >= now,
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .limit(5)
        .all()
    )
    expected = _code_hash(email, purpose, code)
    for row in rows:
        if hmac.compare_digest(row.code, expected):
            row.used_at = now
            return True
    return False
