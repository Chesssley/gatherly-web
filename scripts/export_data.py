import json
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
import sys
import warnings

from sqlalchemy import inspect, select
from sqlalchemy.exc import SAWarning

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.models import db


EXPORT_PATH = ROOT_DIR / "gatherly_export.json"


def serialize_value(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def ordered_select(table):
    statement = select(table)
    primary_key_columns = list(table.primary_key.columns)
    if primary_key_columns:
        statement = statement.order_by(*primary_key_columns)
    return statement


def sorted_metadata_tables():
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Cannot correctly sort tables.*",
            category=SAWarning,
        )
        return list(db.metadata.sorted_tables)


def table_rows(table):
    rows = db.session.execute(ordered_select(table)).mappings()
    exported_rows = []
    for row in rows:
        exported_rows.append(
            {
                column.name: serialize_value(row[column.name])
                for column in table.columns
            }
        )
    return exported_rows


def main():
    app = create_app()

    with app.app_context():
        inspector = inspect(db.engine)
        existing_tables = set(inspector.get_table_names())
        exported_tables = []

        for table in sorted_metadata_tables():
            if table.name not in existing_tables:
                print(f"{table.name}: skipped (table does not exist)")
                continue

            rows = table_rows(table)
            exported_tables.append(
                {
                    "name": table.name,
                    "columns": [column.name for column in table.columns],
                    "rows": rows,
                }
            )
            print(f"{table.name}: exported {len(rows)} rows")

        payload = {
            "format": "gatherly-sqlalchemy-json-v1",
            "tables": exported_tables,
        }
        EXPORT_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Export complete: {EXPORT_PATH}")


if __name__ == "__main__":
    main()
