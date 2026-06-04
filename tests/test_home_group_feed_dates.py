import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from app.routes import activity as activity_routes


class HomeGroupFeedDateTestCase(unittest.TestCase):
    def test_today_group_uses_default_activity_timezone(self):
        class FrozenDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                current = datetime(2026, 6, 4, 18, 30, tzinfo=timezone.utc)
                if tz is not None:
                    return current.astimezone(tz)
                return current.replace(tzinfo=None)

        with patch.object(activity_routes, "datetime", FrozenDateTime):
            selected_date = activity_routes._parse_home_group_selected_date("")
            sections = activity_routes._build_home_group_feed_sections(
                [
                    {
                        "id": 1,
                        "start_datetime": datetime(2026, 6, 5, 9, 0),
                        "timezone": "Asia/Shanghai",
                    }
                ],
                selected_date,
            )

        self.assertEqual(selected_date, date(2026, 6, 5))
        self.assertEqual(len(sections), 1)
        self.assertTrue(sections[0]["is_selected"])
        self.assertEqual([activity["id"] for activity in sections[0]["activities"]], [1])


if __name__ == "__main__":
    unittest.main()
