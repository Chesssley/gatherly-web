"""Upload legacy app/static/uploads files to Cloudflare R2 and rewrite DB URLs.

Default mode is dry-run. Set CONFIRM_R2_MIGRATION=YES to upload and update.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Text, String, select, update

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env")

from app import create_app  # noqa: E402
from app.models import db  # noqa: E402
from app.services.storage import (  # noqa: E402
    R2_REQUIRED_ENV_VARS,
    content_type_for_extension,
    public_base_url,
    r2_client,
)


UPLOAD_ROOT = ROOT_DIR / "app" / "static" / "uploads"
CONFIRM_VALUE = "YES"
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
SKIPPED_FILE_NAMES = {".gitkeep", ".DS_Store", "Thumbs.db"}
SKIPPED_DIR_NAMES = {"__pycache__"}
UPLOAD_REFERENCE_RE = re.compile(
    r"(app/static/uploads/|/static/uploads/|static/uploads/)([^\s\"'<>)]*)"
)


def log(message):
    print(message, flush=True)


def require_environment():
    missing = [name for name in ("DATABASE_URL", *R2_REQUIRED_ENV_VARS) if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))


def is_dry_run():
    return os.environ.get("CONFIRM_R2_MIGRATION") != CONFIRM_VALUE


def should_skip_path(path):
    parts = path.relative_to(UPLOAD_ROOT).parts
    for part in parts[:-1]:
        if part in SKIPPED_DIR_NAMES or part.startswith("."):
            return True

    filename = path.name
    if filename in SKIPPED_FILE_NAMES or filename.startswith("."):
        return True
    return path.suffix.lower().lstrip(".") not in ALLOWED_IMAGE_EXTENSIONS


def iter_upload_files(upload_root):
    if not upload_root.exists():
        return [], 0

    files = []
    skipped = 0
    for path in upload_root.rglob("*"):
        if path.is_dir():
            continue
        if should_skip_path(path):
            skipped += 1
            continue
        files.append(path)
    return files, skipped


def relative_upload_path(path):
    return path.relative_to(UPLOAD_ROOT).as_posix()


def r2_key_for_path(path):
    return f"uploads/{relative_upload_path(path)}"


def r2_url_for_relative_path(relative_path):
    return f"{public_base_url()}/uploads/{relative_path}"


def upload_files(files, dry_run):
    uploaded = {}
    skipped = 0
    failed = {}
    client = None if dry_run else r2_client()
    bucket = os.environ["R2_BUCKET_NAME"]

    for path in files:
        relative_path = relative_upload_path(path)
        key = f"uploads/{relative_path}"
        url = r2_url_for_relative_path(relative_path)
        if dry_run:
            log(f"[dry-run] upload {path} -> r2://{bucket}/{key}")
            uploaded[relative_path] = url
            continue

        extension = path.suffix.lower().lstrip(".")
        try:
            with path.open("rb") as file_obj:
                client.upload_fileobj(
                    file_obj,
                    bucket,
                    key,
                    ExtraArgs={"ContentType": content_type_for_extension(extension)},
                )
            uploaded[relative_path] = url
            log(f"[upload] {path} -> {url}")
        except Exception as exc:
            failed[relative_path] = str(exc)
            skipped += 1
            log(f"[upload-failed] {path}: {exc}")

    return uploaded, skipped, failed


def convert_value(value, uploaded):
    if not isinstance(value, str):
        return value, False

    changed = False

    def replace(match):
        nonlocal changed
        relative_path = match.group(2).replace("\\", "/").lstrip("/")
        new_url = uploaded.get(relative_path)
        if not new_url:
            return match.group(0)
        changed = True
        return new_url

    converted = UPLOAD_REFERENCE_RE.sub(replace, value)
    return converted, changed


def string_columns(table):
    return [
        column
        for column in table.columns
        if isinstance(column.type, (String, Text))
    ]


def primary_key_filter(table, row):
    conditions = []
    for column in table.primary_key.columns:
        conditions.append(column == row[column.name])
    return conditions


def plan_database_updates(uploaded):
    plans = []
    metadata = db.metadata
    for table in metadata.sorted_tables:
        columns = string_columns(table)
        if not columns or not table.primary_key.columns:
            continue

        rows = db.session.execute(select(table)).mappings()
        for row in rows:
            updates = {}
            for column in columns:
                converted, changed = convert_value(row[column.name], uploaded)
                if changed:
                    updates[column.name] = converted
            if updates:
                plans.append((table, dict(row), updates))
    return plans


def apply_database_updates(plans):
    updated_records = 0
    with db.engine.begin() as connection:
        for table, row, updates in plans:
            statement = update(table).where(*primary_key_filter(table, row)).values(**updates)
            result = connection.execute(statement)
            updated_records += result.rowcount or 0
            log(f"[db-update] {table.name} {updates}")
    return updated_records


def main():
    require_environment()
    dry_run = is_dry_run()
    log("Mode: dry-run" if dry_run else "Mode: execute")
    log(f"Upload root: {UPLOAD_ROOT}")

    files, skipped_scan_files = iter_upload_files(UPLOAD_ROOT)
    log(f"Scanned files: {len(files)}")
    log(f"Planned uploads: {len(files)}")

    uploaded, skipped_files, failed = upload_files(files, dry_run=dry_run)
    log(f"Uploaded files: {len(uploaded) if not dry_run else 0}")
    log(f"Skipped files: {skipped_scan_files + skipped_files}")
    if failed:
        log(f"Failed uploads: {len(failed)}")
        if not dry_run:
            raise RuntimeError("One or more uploads failed; database updates were not attempted.")

    app = create_app()
    with app.app_context():
        plans = plan_database_updates(uploaded)
        log(f"Planned DB record updates: {len(plans)}")
        sample_url = next(iter(uploaded.values()), "")
        if sample_url:
            log(f"Example new URL: {sample_url}")
        if dry_run:
            for table, row, updates in plans[:20]:
                pk = {column.name: row[column.name] for column in table.primary_key.columns}
                log(f"[dry-run] update {table.name} pk={pk} fields={list(updates)}")
            log("Dry-run complete. Set CONFIRM_R2_MIGRATION=YES to execute.")
            return

        try:
            updated_records = apply_database_updates(plans)
        except Exception:
            db.session.rollback()
            log("Database update failed; transaction rolled back.")
            raise

        log(f"Updated records: {updated_records}")
        log(f"Example new URL: {next(iter(uploaded.values()), '')}")
        log("Migration complete. Local files were not deleted.")


if __name__ == "__main__":
    main()
