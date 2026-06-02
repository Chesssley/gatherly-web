import json
import os
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
import sys
import traceback
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import warnings

from sqlalchemy import (
    Date,
    DateTime,
    Time,
    Boolean,
    Integer,
    bindparam,
    func,
    inspect,
    select,
    text,
)
from sqlalchemy.exc import SAWarning

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.models import db


EXPORT_PATH = ROOT_DIR / "gatherly_export.json"
EXPORT_FORMAT = "gatherly-sqlalchemy-json-v1"
SYSTEM_TABLES = {"alembic_version", "sqlite_sequence"}
DELAYED_FOREIGN_KEYS = {
    ("circle", "pinned_post_id"): ("post", "id"),
}
CONNECT_TIMEOUT_SECONDS = 10


def log(message):
    print(message, flush=True)


def warn(message):
    log(f"WARNING: {message}")


def normalize_database_url(raw_database_url):
    if not raw_database_url:
        raise RuntimeError("DATABASE_URL is not set.")

    parts = urlsplit(raw_database_url)
    if parts.scheme not in {"postgresql", "postgres"}:
        raise RuntimeError(
            "DATABASE_URL must start with postgresql:// or postgres:// for Neon import. "
            f"Current scheme: {parts.scheme or '(missing)'}"
        )

    scheme = "postgresql" if parts.scheme == "postgres" else parts.scheme
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.setdefault("connect_timeout", str(CONNECT_TIMEOUT_SECONDS))
    normalized = urlunsplit(
        (scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )
    safe_database = parts.path.lstrip("/") or "(missing database)"
    safe_host = parts.hostname or "(missing host)"
    return normalized, f"{scheme}://{safe_host}/{safe_database}"


def load_payload():
    if not EXPORT_PATH.exists():
        raise FileNotFoundError(f"Export file not found: {EXPORT_PATH}")

    try:
        payload = json.loads(EXPORT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Could not parse JSON export file {EXPORT_PATH}: "
            f"line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc

    if payload.get("format") != EXPORT_FORMAT:
        raise ValueError(
            f"Unsupported export format: {payload.get('format')!r}. "
            f"Expected {EXPORT_FORMAT!r}."
        )
    if not isinstance(payload.get("tables"), list):
        raise ValueError("Invalid export payload: 'tables' must be a list.")

    for entry in payload["tables"]:
        name = entry.get("name", "(missing name)")
        rows = entry.get("rows", [])
        if not isinstance(rows, list):
            raise ValueError(f"Invalid export payload: rows for table {name!r} must be a list.")
        log(f"  {name}: {len(rows)} rows in export")
    return payload


def sorted_metadata_tables():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Cannot correctly sort tables.*",
            category=SAWarning,
        )
        return list(db.metadata.sorted_tables)


def business_tables(tables, existing_tables):
    return [
        table
        for table in tables
        if table.name in existing_tables and table.name not in SYSTEM_TABLES
    ]


def parse_value(column, value):
    if value is None:
        return None

    if value == "" and isinstance(column.type, (DateTime, Date, Time)):
        return None

    if isinstance(column.type, DateTime):
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value))
    if isinstance(column.type, Date):
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        return date.fromisoformat(str(value))
    if isinstance(column.type, Time):
        if isinstance(value, time):
            return value
        return time.fromisoformat(str(value))
    if isinstance(column.type, Boolean):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "t", "yes", "y", "on"}:
                return True
            if normalized in {"0", "false", "f", "no", "n", "off", ""}:
                return False
        return bool(value)
    if isinstance(column.type, Integer) and value == "":
        return None

    try:
        python_type = column.type.python_type
    except NotImplementedError:
        return value

    if python_type is Decimal and isinstance(value, str):
        return Decimal(value)
    return value


def table_count(table):
    return db.session.execute(select(func.count()).select_from(table)).scalar_one()


def target_row_counts(tables):
    counts = {}
    for table in tables:
        counts[table.name] = table_count(table)
        log(f"  {table.name}: {counts[table.name]} existing rows")
    return counts


def clear_delayed_foreign_keys(tables):
    table_map = {table.name: table for table in tables}
    for table_name, column_name in DELAYED_FOREIGN_KEYS:
        table = table_map.get(table_name)
        if table is None or column_name not in table.columns:
            continue
        log(f"  Clearing delayed foreign key {table_name}.{column_name}")
        db.session.execute(table.update().values({column_name: None}))


def clear_tables(tables):
    clear_delayed_foreign_keys(tables)
    for table in reversed(tables):
        log(f"  Deleting rows from {table.name}")
        db.session.execute(table.delete())


def export_table_entries(payload):
    entries = []
    seen = set()
    for entry in payload["tables"]:
        name = entry.get("name")
        if not name:
            warn("Skipping export entry without table name.")
            continue
        if name in seen:
            warn(f"Duplicate export entry for table {name}; later entry ignored.")
            continue
        seen.add(name)
        entries.append(entry)
    return {entry["name"]: entry for entry in entries}


def row_identity(table, row):
    primary_key_columns = list(table.primary_key.columns)
    if not primary_key_columns:
        return None
    values = []
    for column in primary_key_columns:
        if column.name not in row:
            return None
        values.append(row[column.name])
    return tuple(values)


def build_primary_key_filter(table, identity):
    primary_key_columns = list(table.primary_key.columns)
    clauses = []
    params = {}
    for index, column in enumerate(primary_key_columns):
        param_name = f"pk_{index}"
        clauses.append(column == bindparam(param_name))
        params[param_name] = parse_value(column, identity[index])
    return clauses, params


def check_referenced_row(table_map, referred_table_name, referred_column_name, raw_value):
    referred_table = table_map.get(referred_table_name)
    if referred_table is None or referred_column_name not in referred_table.columns:
        return False
    referred_column = referred_table.columns[referred_column_name]
    value = parse_value(referred_column, raw_value)
    exists_statement = select(referred_column).where(referred_column == value).limit(1)
    return db.session.execute(exists_statement).first() is not None


def insert_rows(table, rows, export_columns):
    inserted = 0
    delayed_updates = []
    current_columns = {column.name: column for column in table.columns}
    export_column_names = set(export_columns or [])
    observed_row_columns = set()

    for row in rows:
        if isinstance(row, dict):
            observed_row_columns.update(row.keys())

    unknown_columns = (export_column_names | observed_row_columns) - set(current_columns)
    for column_name in sorted(unknown_columns):
        warn(f"{table.name}.{column_name} exists in export but not current model; skipping.")

    missing_columns = set(current_columns) - (export_column_names | observed_row_columns)
    for column_name in sorted(missing_columns):
        warn(f"{table.name}.{column_name} missing from export; database default or NULL will be used.")

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"{table.name} row {index} is not an object.")

        insert_values = {}
        delayed_values = {}
        for column_name, raw_value in row.items():
            column = current_columns.get(column_name)
            if column is None:
                continue
            if (table.name, column_name) in DELAYED_FOREIGN_KEYS and raw_value is not None:
                insert_values[column_name] = None
                delayed_values[column_name] = raw_value
                continue
            insert_values[column_name] = parse_value(column, raw_value)

        if not insert_values:
            warn(f"{table.name} row {index} had no importable columns; skipped.")
            continue

        db.session.execute(table.insert().values(**insert_values))
        inserted += 1

        if delayed_values:
            identity = row_identity(table, row)
            if identity is None:
                warn(
                    f"{table.name} row {index} has delayed foreign keys but no complete "
                    "primary key; delayed values skipped."
                )
            else:
                delayed_updates.append((table.name, identity, delayed_values))

    return inserted, delayed_updates


def restore_delayed_foreign_keys(delayed_updates, table_map):
    restored = 0
    skipped = 0

    for table_name, identity, delayed_values in delayed_updates:
        table = table_map[table_name]
        update_values = {}

        for column_name, raw_value in delayed_values.items():
            referred_table_name, referred_column_name = DELAYED_FOREIGN_KEYS[(table_name, column_name)]
            if raw_value is None:
                update_values[column_name] = None
                continue
            if check_referenced_row(table_map, referred_table_name, referred_column_name, raw_value):
                update_values[column_name] = parse_value(table.columns[column_name], raw_value)
            else:
                skipped += 1
                warn(
                    f"Skipped delayed foreign key {table_name}.{column_name}={raw_value!r}; "
                    f"{referred_table_name}.{referred_column_name} does not exist."
                )

        if not update_values:
            continue

        clauses, params = build_primary_key_filter(table, identity)
        statement = table.update()
        for clause in clauses:
            statement = statement.where(clause)
        db.session.execute(statement.values(**update_values), params)
        restored += 1

    log(f"  Delayed foreign key rows restored: {restored}; skipped values: {skipped}")


def quoted_table_name(preparer, table):
    if table.schema:
        return f"{preparer.quote_schema(table.schema)}.{preparer.quote(table.name)}"
    return preparer.quote(table.name)


def reset_postgresql_sequences(tables):
    preparer = db.engine.dialect.identifier_preparer
    for table in tables:
        id_column = table.columns.get("id")
        if id_column is None or not id_column.primary_key:
            continue

        quoted_table = quoted_table_name(preparer, table)
        quoted_id = preparer.quote(id_column.name)
        sequence_name = db.session.execute(
            text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
            {"table_name": quoted_table, "column_name": id_column.name},
        ).scalar()
        if not sequence_name:
            log(f"  {table.name}: no serial sequence found")
            continue

        db.session.execute(
            text(
                "SELECT setval("
                "CAST(:sequence_name AS regclass), "
                f"COALESCE((SELECT MAX({quoted_id}) FROM {quoted_table}), 1), "
                "true"
                ")"
            ),
            {"sequence_name": sequence_name},
        )
        log(f"  {table.name}: reset {sequence_name}")


def import_tables_in_metadata_order(payload, tables):
    entry_map = export_table_entries(payload)
    table_map = {table.name: table for table in tables}
    imported_counts = {}
    all_delayed_updates = []

    for export_table_name in sorted(set(entry_map) - set(table_map) - SYSTEM_TABLES):
        warn(f"{export_table_name} exists in export but not current metadata; skipping table.")

    for table in tables:
        entry = entry_map.get(table.name)
        if entry is None:
            warn(f"{table.name} missing from export; no rows imported for this table.")
            imported_counts[table.name] = 0
            continue

        rows = entry.get("rows", [])
        export_columns = entry.get("columns", [])
        log(f"  Importing {table.name}: {len(rows)} rows")
        inserted, delayed_updates = insert_rows(table, rows, export_columns)
        imported_counts[table.name] = inserted
        all_delayed_updates.extend(delayed_updates)
        log(f"  Imported {table.name}: {inserted} rows")

    return imported_counts, all_delayed_updates


def main():
    app = None

    try:
        log("[1/8] Starting import script")

        log("[2/8] Loading gatherly_export.json")
        payload = load_payload()

        log("[3/8] Checking DATABASE_URL")
        normalized_database_url, safe_database_url = normalize_database_url(
            os.environ.get("DATABASE_URL")
        )
        os.environ["DATABASE_URL"] = normalized_database_url
        log(f"  Database: {safe_database_url}")

        log("[4/8] Testing database connection")
        app = create_app()
        with app.app_context():
            db.session.execute(text("select 1")).scalar_one()
            log(f"  Connected. SQLAlchemy dialect: {db.engine.dialect.name}")
            if db.engine.dialect.name != "postgresql":
                raise RuntimeError(
                    f"Connected database dialect must be postgresql, got {db.engine.dialect.name!r}."
                )

            inspector = inspect(db.engine)
            existing_tables = set(inspector.get_table_names())
            sorted_tables = sorted_metadata_tables()
            importable_tables = business_tables(sorted_tables, existing_tables)
            missing_tables = [
                table.name
                for table in sorted_tables
                if table.name not in SYSTEM_TABLES and table.name not in existing_tables
            ]
            for table_name in missing_tables:
                warn(f"{table_name} is in metadata but missing in target database; skipped.")

            log("[5/8] Checking existing business rows")
            counts = target_row_counts(importable_tables)
            non_empty = {name: count for name, count in counts.items() if count}
            if non_empty and os.environ.get("CONFIRM_IMPORT") != "YES":
                log("Target database has existing business rows.")
                log("Set CONFIRM_IMPORT=YES to clear business tables and import again.")
                raise SystemExit(1)

            imported_counts = {}
            try:
                log("[6/8] Importing tables")
                if non_empty:
                    log("  CONFIRM_IMPORT=YES detected; clearing business tables first.")
                    clear_tables(importable_tables)
                    db.session.flush()

                imported_counts, delayed_updates = import_tables_in_metadata_order(
                    payload, importable_tables
                )
                db.session.flush()

                log("[7/8] Restoring delayed foreign keys")
                restore_delayed_foreign_keys(
                    delayed_updates,
                    {table.name: table for table in importable_tables},
                )
                db.session.flush()

                log("[8/8] Fixing PostgreSQL sequences")
                reset_postgresql_sequences(importable_tables)

                db.session.commit()
            except Exception:
                db.session.rollback()
                raise

            for table in importable_tables:
                log(f"{table.name}: imported {imported_counts.get(table.name, 0)} rows")
            log("IMPORT SUCCESS")

    except SystemExit:
        if app is not None:
            with app.app_context():
                db.session.rollback()
        log("IMPORT FAILED")
        raise
    except Exception:
        if app is not None:
            with app.app_context():
                db.session.rollback()
        log("IMPORT FAILED")
        traceback.print_exc()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
