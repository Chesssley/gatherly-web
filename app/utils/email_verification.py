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

from app.models import EmailVerificationCode, db


EMAIL_CODE_TTL_MINUTES = 10
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


def _send_mail(to_email, subject, body):
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


def send_verification_code(email, purpose, user=None):
    """Create a short-lived code, store only its hash, and send it by SMTP.

    When SMTP is not configured locally, the code is printed to the app console
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
    if not sent:
        current_app.logger.info(
            "SMTP not configured; verification code for %s/%s is %s",
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
