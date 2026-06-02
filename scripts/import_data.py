import json
import os
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
import sys
import warnings

from sqlalchemy import Date, DateTime, Time, func, inspect, select, text
from sqlalchemy.exc import SAWarning

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.models import db


EXPORT_PATH = ROOT_DIR / "gatherly_export.json"


def load_payload():
    if not EXPORT_PATH.exists():
        raise FileNotFoundError(f"Export file not found: {EXPORT_PATH}")
    payload = json.loads(EXPORT_PATH.read_text(encoding="utf-8"))
    if payload.get("format") != "gatherly-sqlalchemy-json-v1":
        raise ValueError("Unsupported export format.")
    return payload


def sorted_metadata_tables():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Cannot correctly sort tables.*",
            category=SAWarning,
        )
        return list(db.metadata.sorted_tables)


def parse_value(column, value):
    if value is None:
        return None
    if isinstance(column.type, DateTime):
        return datetime.fromisoformat(value)
    if isinstance(column.type, Date):
        return date.fromisoformat(value)
    if isinstance(column.type, Time):
        return time.fromisoformat(value)

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
    return {table.name: table_count(table) for table in tables}


def clear_nullable_foreign_keys(tables):
    for table in tables:
        nullable_fk_columns = [
            column for column in table.columns if column.foreign_keys and column.nullable
        ]
        if not nullable_fk_columns:
            continue
        values = {column.name: None for column in nullable_fk_columns}
        db.session.execute(table.update().values(**values))


def clear_tables(tables):
    clear_nullable_foreign_keys(tables)
    for table in reversed(tables):
        db.session.execute(table.delete())


def insert_rows(table, rows):
    inserted = 0

    for row in rows:
        insert_values = {}
        for column in table.columns:
            if column.name not in row:
                continue
            value = parse_value(column, row[column.name])
            insert_values[column.name] = value

        if insert_values:
            db.session.execute(table.insert().values(**insert_values))
            inserted += 1

    return inserted


def quoted_table_name(preparer, schema, table_name):
    if schema:
        return f"{preparer.quote_schema(schema)}.{preparer.quote(table_name)}"
    return preparer.quote(table_name)


def postgresql_foreign_keys(tables):
    if db.engine.dialect.name != "postgresql":
        return []

    inspector = inspect(db.engine)
    foreign_keys = []
    for table in tables:
        for foreign_key in inspector.get_foreign_keys(table.name, schema=table.schema):
            if not foreign_key.get("name"):
                continue
            foreign_keys.append(
                {
                    "table_schema": table.schema,
                    "table_name": table.name,
                    "name": foreign_key["name"],
                    "columns": foreign_key["constrained_columns"],
                    "referred_schema": foreign_key.get("referred_schema"),
                    "referred_table": foreign_key["referred_table"],
                    "referred_columns": foreign_key["referred_columns"],
                    "options": foreign_key.get("options") or {},
                }
            )
    return foreign_keys


def drop_postgresql_foreign_keys(foreign_keys):
    if not foreign_keys:
        return

    preparer = db.engine.dialect.identifier_preparer
    for foreign_key in foreign_keys:
        db.session.execute(
            text(
                f"ALTER TABLE "
                f"{quoted_table_name(preparer, foreign_key['table_schema'], foreign_key['table_name'])} "
                f"DROP CONSTRAINT IF EXISTS {preparer.quote(foreign_key['name'])}"
            )
        )


def restore_postgresql_foreign_keys(foreign_keys):
    if not foreign_keys:
        return

    preparer = db.engine.dialect.identifier_preparer
    for foreign_key in foreign_keys:
        source_columns = ", ".join(preparer.quote(column) for column in foreign_key["columns"])
        referred_columns = ", ".join(
            preparer.quote(column) for column in foreign_key["referred_columns"]
        )
        statement = (
            f"ALTER TABLE "
            f"{quoted_table_name(preparer, foreign_key['table_schema'], foreign_key['table_name'])} "
            f"ADD CONSTRAINT {preparer.quote(foreign_key['name'])} "
            f"FOREIGN KEY ({source_columns}) "
            f"REFERENCES "
            f"{quoted_table_name(preparer, foreign_key['referred_schema'], foreign_key['referred_table'])} "
            f"({referred_columns})"
        )
        options = foreign_key["options"]
        if options.get("onupdate"):
            statement += f" ON UPDATE {options['onupdate']}"
        if options.get("ondelete"):
            statement += f" ON DELETE {options['ondelete']}"
        if options.get("deferrable"):
            statement += " DEFERRABLE"
        if options.get("initially"):
            statement += f" INITIALLY {options['initially']}"
        db.session.execute(text(statement))


def reset_postgresql_sequences(tables):
    if db.engine.dialect.name != "postgresql":
        return

    preparer = db.engine.dialect.identifier_preparer
    for table in tables:
        id_column = table.columns.get("id")
        if id_column is None or not id_column.primary_key:
            continue

        quoted_table = preparer.quote(table.name)
        quoted_id = preparer.quote(id_column.name)
        sequence_name = db.session.execute(
            text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
            {"table_name": table.name, "column_name": id_column.name},
        ).scalar()
        if not sequence_name:
            continue

        db.session.execute(
            text(
                "SELECT setval("
                "CAST(:sequence_name AS regclass), "
                f"COALESCE((SELECT MAX({quoted_id}) FROM {quoted_table}), 1), "
                f"(SELECT MAX({quoted_id}) IS NOT NULL FROM {quoted_table})"
                ")"
            ),
            {"sequence_name": sequence_name},
        )


def main():
    payload = load_payload()
    app = create_app()

    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        sorted_tables = sorted_metadata_tables()
        table_map = {table.name: table for table in sorted_tables}
        metadata_tables = [
            table for table in sorted_tables if table.name in existing_tables
        ]
        export_entries = payload["tables"]
        import_tables = []

        for entry in export_entries:
            table = table_map.get(entry["name"])
            if table is None:
                print(f"{entry['name']}: skipped (not in current metadata)")
                continue
            if table.name not in existing_tables:
                print(f"{table.name}: skipped (table does not exist)")
                continue
            import_tables.append(table)

        counts = target_row_counts(metadata_tables)
        non_empty = {name: count for name, count in counts.items() if count}
        if non_empty:
            if os.environ.get("CONFIRM_IMPORT") != "YES":
                print("Target database is not empty. Set CONFIRM_IMPORT=YES to clear and import.")
                for name, count in non_empty.items():
                    print(f"{name}: {count} existing rows")
                raise SystemExit(1)

        imported_counts = {}

        try:
            foreign_keys = postgresql_foreign_keys(metadata_tables)
            drop_postgresql_foreign_keys(foreign_keys)

            if non_empty:
                clear_tables(metadata_tables)
                db.session.flush()

            for entry in export_entries:
                table = table_map.get(entry["name"])
                if table is None or table not in import_tables:
                    continue
                imported_counts[table.name] = insert_rows(table, entry["rows"])

            reset_postgresql_sequences(metadata_tables)
            restore_postgresql_foreign_keys(foreign_keys)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        for table in import_tables:
            print(f"{table.name}: imported {imported_counts.get(table.name, 0)} rows")
        print("Import complete.")


if __name__ == "__main__":
    main()
