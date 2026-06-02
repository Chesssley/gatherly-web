"""Backfill system circle covers with the curated realistic cover set.

This script only updates system circles whose cover is empty or still points to
one of the built-in default/legacy cover assets. User-uploaded covers are left
unchanged.
"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.models import Circle, db
from app.routes.circle import (
    CIRCLE_OFFICIAL_TOPIC_TAGS,
    _is_official_default_cover,
    _legacy_official_circle_name,
    _official_circle_name,
    _official_cover_image,
)


def main():
    app = create_app()
    updated = []
    skipped = []

    with app.app_context():
        for index, tag in enumerate(CIRCLE_OFFICIAL_TOPIC_TAGS, start=1):
            name = _official_circle_name(tag)
            circle = (
                Circle.query.filter(
                    Circle.is_system.is_(True),
                    Circle.name.in_([name, _legacy_official_circle_name(tag)]),
                ).first()
            )
            if circle is None:
                continue

            target_cover = _official_cover_image(index)
            if _is_official_default_cover(circle.cover_image):
                if circle.cover_image != target_cover:
                    updated.append((circle.name, circle.cover_image, target_cover))
                circle.cover_image = target_cover
            else:
                skipped.append((circle.name, circle.cover_image))

        db.session.commit()

    print(f"Updated {len(updated)} system circle covers.")
    for name, old_cover, new_cover in updated:
        print(f"- {name}: {old_cover or '(empty)'} -> {new_cover}")

    if skipped:
        print(f"Skipped {len(skipped)} circles with custom covers.")
        for name, cover in skipped:
            print(f"- {name}: {cover}")


if __name__ == "__main__":
    main()
