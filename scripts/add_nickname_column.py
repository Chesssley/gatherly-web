from pathlib import Path
import sys

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app
from app.models import db


def user_columns():
    inspector = inspect(db.engine)
    return [column["name"] for column in inspector.get_columns("user")]


def main():
    app = create_app()

    with app.app_context():
        before = user_columns()
        print(f"before: {before}")

        if "nickname" not in before:
            db.session.execute(text('ALTER TABLE "user" ADD COLUMN nickname VARCHAR(80)'))
            db.session.commit()
            print("added nickname column")
        else:
            print("nickname column already exists")

        db.session.execute(
            text('UPDATE "user" SET nickname = username WHERE nickname IS NULL OR nickname = ""')
        )
        db.session.commit()

        after = user_columns()
        print(f"after: {after}")
        print("nickname backfill complete")


if __name__ == "__main__":
    main()
