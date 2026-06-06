import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import create_app
from app.models import User, db
from app.routes.profile import _current_request_ip_region, _profile_ip_region_label
from app.utils.location_utils import format_ip_region


class ProfileIpRegionTestCase(unittest.TestCase):
    def test_profile_ip_region_uses_current_detection_when_provided(self):
        user = SimpleNamespace(detected_city=None, detected_region="Stored Region")
        current_region = {"city": "Current Region", "region": None, "country": None}

        self.assertEqual(_profile_ip_region_label(user, current_region), "Current Region")

    def test_profile_ip_region_uses_target_user_stored_region(self):
        user = SimpleNamespace(detected_city=None, detected_region="Stored Region")

        self.assertEqual(_profile_ip_region_label(user), format_ip_region(user))
        self.assertEqual(_profile_ip_region_label(user), "Stored Region")

    def test_profile_ip_region_uses_same_unknown_fallback_as_nearby(self):
        user = SimpleNamespace(detected_city=None, detected_region=None)

        self.assertEqual(_profile_ip_region_label(user), format_ip_region(user))

    def test_non_owner_profile_does_not_detect_viewer_request_region(self):
        with patch("app.routes.profile.detect_current_request_location") as detect:
            self.assertIsNone(_current_request_ip_region(None))

        detect.assert_not_called()


class ProfileIpRegionRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.client = self.app.test_client()

        self.owner = User(
            username="owner",
            email="owner@example.com",
            password_hash="scrypt:test",
            nearby_enabled=True,
            detected_region="Stored Owner Region",
        )
        self.other = User(
            username="other",
            email="other@example.com",
            password_hash="scrypt:test",
            detected_region="Target Region",
        )
        db.session.add_all([self.owner, self.other])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login_owner(self):
        with self.client.session_transaction() as session:
            session["user_id"] = self.owner.id

    def test_owner_profile_matches_nearby_current_ip_region(self):
        self._login_owner()
        current_region = {"city": "Current Region", "region": None, "country": None}

        with patch("app.routes.profile.update_user_detected_location", return_value=current_region):
            profile_html = self.client.get(f"/profile/{self.owner.id}").get_data(as_text=True)
            nearby_html = self.client.get("/profile/nearby").get_data(as_text=True)

        self.assertIn("Current Region", profile_html)
        self.assertIn("Current Region", nearby_html)

    def test_other_profile_uses_target_user_latest_ip_region(self):
        self._login_owner()

        with patch("app.routes.profile.detect_current_request_location") as detect:
            profile_html = self.client.get(f"/profile/{self.other.id}").get_data(as_text=True)

        self.assertIn("Target Region", profile_html)
        self.assertNotIn("Current Region", profile_html)
        detect.assert_not_called()


if __name__ == "__main__":
    unittest.main()
