# -*- coding: utf-8 -*-
"""Email verification code helpers."""

import hashlib
import hmac
import json
import os
import secrets
import smtplib
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from email.message import EmailMessage

from flask import current_app

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


def _email_provider():
    provider = os.environ.get("EMAIL_PROVIDER", "").strip().lower()
    return provider or "console"


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
        "sender": os.environ.get("MAIL_DEFAULT_SENDER", "").strip(),
    }


def _smtp_ready(config):
    return bool(config["server"] and config["port"] and config["sender"])


def _send_mail_smtp(to_email, subject, body):
    config = _mail_config()
    if not _smtp_ready(config):
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
    sender_email = os.environ.get("BREVO_SENDER_EMAIL", "").strip()
    sender_name = os.environ.get("BREVO_SENDER_NAME", "").strip() or "Gatherly"

    if not api_key or not sender_email:
        current_app.logger.error(
            "Brevo email API is not configured; BREVO_API_KEY and "
            "BREVO_SENDER_EMAIL are required"
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
    request = urllib.request.Request(
        BREVO_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": api_key,
            "accept": "application/json",
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=_email_api_timeout()) as response:
            status = response.getcode()
            if status in {200, 201, 202}:
                return True
            response_body = response.read(500).decode("utf-8", errors="replace")
            current_app.logger.error(
                "Brevo email API returned unexpected status %s for %s: %s",
                status,
                to_email,
                response_body,
            )
    except urllib.error.HTTPError as exc:
        response_body = exc.read(500).decode("utf-8", errors="replace")
        current_app.logger.error(
            "Brevo email API returned HTTP %s for %s: %s",
            exc.code,
            to_email,
            response_body,
        )
    except urllib.error.URLError as exc:
        current_app.logger.error(
            "Brevo email API request failed for %s: %s", to_email, exc.reason
        )
    except OSError as exc:
        current_app.logger.error(
            "Brevo email API request failed for %s: %s", to_email, exc
        )
    return False


def _send_mail(to_email, subject, body):
    provider = _email_provider()
    if provider == "brevo":
        return _send_mail_brevo(to_email, subject, body)
    if provider == "smtp":
        return _send_mail_smtp(to_email, subject, body)
    if provider == "console":
        return False

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
    db.session.flush()

    label = PURPOSE_LABELS.get(purpose, "邮箱确认")
    subject = f"Gatherly {label}验证码"
    body = (
        f"你的 Gatherly {label}验证码是：{code}\n\n"
        f"验证码 {EMAIL_CODE_TTL_MINUTES} 分钟内有效，请勿转发给他人。"
    )
    sent = _send_mail(email, subject, body)
    if not sent and is_console_email_provider():
        current_app.logger.info(
            "Console email provider; verification code for %s/%s is %s",
            purpose,
            email,
            code,
        )
        print(f"[DEV EMAIL CODE] {purpose} {email}: {code}")

    db.session.commit()
    return sent


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
