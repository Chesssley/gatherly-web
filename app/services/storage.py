import mimetypes
import os
from functools import lru_cache
from uuid import uuid4

from flask import current_app, url_for
from werkzeug.utils import secure_filename


R2_REQUIRED_ENV_VARS = (
    "R2_ACCOUNT_ID",
    "R2_BUCKET_NAME",
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "R2_PUBLIC_BASE_URL",
)

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
ALLOWED_UPLOAD_DIRECTORIES = {
    "avatars",
    "posts",
    "comments",
    "activities",
    "circles",
    "messages",
    "merchant-verifications",
}

UPLOAD_DIRECTORY_ALIASES = {
    "uploads/avatars": "avatars",
    "uploads/posts": "posts",
    "uploads/comments": "comments",
    "images/activities": "activities",
    "images/circles": "circles",
    "uploads/messages": "messages",
    "uploads/merchant-verifications": "merchant-verifications",
}

CONTENT_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "gif": "image/gif",
}


def is_production_environment():
    app_env = (
        os.environ.get("APP_ENV")
        or os.environ.get("FLASK_ENV")
        or os.environ.get("ENV")
        or ""
    )
    return app_env.strip().lower() in {"production", "prod"}


def r2_config():
    return {name: os.environ.get(name) for name in R2_REQUIRED_ENV_VARS}


def missing_r2_config():
    config = r2_config()
    return [name for name, value in config.items() if not value]


def r2_is_configured():
    return not missing_r2_config()


def require_r2_config():
    missing = missing_r2_config()
    if missing:
        raise RuntimeError(
            "Missing Cloudflare R2 environment variables: " + ", ".join(missing)
        )
    return r2_config()


@lru_cache(maxsize=1)
def r2_client():
    import boto3

    config = require_r2_config()
    endpoint_url = f"https://{config['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name="auto",
        aws_access_key_id=config["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=config["R2_SECRET_ACCESS_KEY"],
    )


def public_base_url():
    config = require_r2_config()
    return config["R2_PUBLIC_BASE_URL"].rstrip("/")


def normalize_upload_directory(directory):
    normalized = str(directory or "").replace("\\", "/").strip("/")
    normalized = UPLOAD_DIRECTORY_ALIASES.get(normalized, normalized)
    if normalized not in ALLOWED_UPLOAD_DIRECTORIES:
        raise ValueError(f"Unsupported upload directory: {directory}")
    return normalized


def extension_from_filename(filename):
    safe_name = secure_filename(filename or "")
    if "." not in safe_name:
        raise ValueError("Image format is not supported.")
    extension = safe_name.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Image format is not supported.")
    return extension


def content_type_for_extension(extension):
    return CONTENT_TYPES.get(extension) or mimetypes.types_map.get(
        f".{extension}",
        "application/octet-stream",
    )


def upload_file(file, directory, extension=None):
    if not file or not file.filename:
        return None

    directory = normalize_upload_directory(directory)
    extension = (extension or extension_from_filename(file.filename)).lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Image format is not supported.")

    filename = secure_filename(f"{uuid4().hex}.{extension}")
    content_type = content_type_for_extension(extension)

    if r2_is_configured():
        key = f"{directory}/{filename}"
        file.stream.seek(0)
        r2_client().upload_fileobj(
            file.stream,
            os.environ["R2_BUCKET_NAME"],
            key,
            ExtraArgs={"ContentType": content_type},
        )
        return f"{public_base_url()}/{key}"

    if is_production_environment():
        require_r2_config()

    local_dir = os.path.join(current_app.static_folder, "uploads", directory)
    os.makedirs(local_dir, exist_ok=True)
    file.stream.seek(0)
    file.save(os.path.join(local_dir, filename))
    return f"/static/uploads/{directory}/{filename}"


def delete_stored_files(paths):
    for path in paths:
        if not path:
            continue
        if r2_is_configured() and path.startswith(f"{public_base_url()}/"):
            key = path[len(public_base_url()) + 1 :]
            try:
                r2_client().delete_object(
                    Bucket=os.environ["R2_BUCKET_NAME"],
                    Key=key,
                )
            except Exception:
                pass
            continue
        local_path = static_path_from_url(path)
        if local_path and os.path.isfile(local_path):
            try:
                os.remove(local_path)
            except OSError:
                pass


def storage_url(value):
    if not value:
        return ""
    value = str(value)
    if value.startswith(("http://", "https://", "data:")):
        return value
    if value.startswith("/static/"):
        return value
    if value.startswith("static/"):
        return f"/{value}"
    if value.startswith("app/static/"):
        return f"/static/{value[len('app/static/'):]}"
    return url_for("static", filename=value)


def static_path_from_url(value):
    if not value:
        return None
    value = str(value).replace("\\", "/")
    if value.startswith("/static/"):
        relative = value[len("/static/") :]
    elif value.startswith("static/"):
        relative = value[len("static/") :]
    elif value.startswith("app/static/"):
        relative = value[len("app/static/") :]
    else:
        return None
    return os.path.join(current_app.static_folder, *relative.split("/"))
