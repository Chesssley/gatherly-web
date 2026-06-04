import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app import create_app
from app.models import Activity, Registration, User, db


class ActivityRegistrationStatusTestCase(unittest.TestCase):
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

        self.organizer = User(
            username="organizer_user",
            email="organizer@example.com",
            password_hash="scrypt:test",
        )
        self.user = User(
            username="regular_user",
            email="regular@example.com",
            password_hash="scrypt:test",
        )
        db.session.add_all([self.organizer, self.user])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _now(self):
        return datetime.now(ZoneInfo("Asia/Shanghai")).replace(tzinfo=None)

    def _login(self):
        with self.client.session_transaction() as session:
            session["user_id"] = self.user.id

    def _activity(self, start_delta, end_delta=None, max_participants=10, initial_participants=0):
        now = self._now()
        activity = Activity(
            title="报名状态测试活动",
            description="活动简介",
            detail="活动详情",
            city="上海",
            location="活动地点",
            start_time=now + start_delta,
            end_time=now + end_delta if end_delta is not None else None,
            max_participants=max_participants,
            initial_participants=initial_participants,
            organizer_id=self.organizer.id,
            status="open",
        )
        db.session.add(activity)
        db.session.commit()
        return activity

    def _detail_html(self, activity):
        response = self.client.get(f"/activity/{activity.id}")
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def test_upcoming_available_activity_shows_register_button(self):
        activity = self._activity(timedelta(days=1), timedelta(days=1, hours=2))
        self._login()

        html = self._detail_html(activity)

        self.assertIn("立即报名", html)
        self.assertNotIn("活动正在进行中", html)
        self.assertNotIn("人数已满", html)

    def test_started_activity_shows_ongoing_disabled_even_if_registered(self):
        activity = self._activity(-timedelta(hours=1), timedelta(hours=1))
        db.session.add(Registration(user_id=self.user.id, activity_id=activity.id))
        db.session.commit()
        self._login()

        html = self._detail_html(activity)

        self.assertIn("活动正在进行中", html)
        self.assertIn("disabled", html)
        self.assertNotIn("立即报名", html)

    def test_ended_activity_shows_ended_disabled(self):
        activity = self._activity(-timedelta(hours=3), -timedelta(hours=1))
        self._login()

        html = self._detail_html(activity)

        self.assertIn("活动已结束", html)
        self.assertIn("disabled", html)
        self.assertNotIn("立即报名", html)

    def test_full_activity_shows_full_disabled(self):
        activity = self._activity(
            timedelta(days=1),
            timedelta(days=1, hours=2),
            max_participants=1,
            initial_participants=1,
        )
        self._login()

        html = self._detail_html(activity)

        self.assertIn("人数已满", html)
        self.assertIn("disabled", html)
        self.assertNotIn("立即报名", html)

    def test_register_post_blocks_started_activity(self):
        activity = self._activity(-timedelta(hours=1), timedelta(hours=1))
        self._login()

        response = self.client.post(f"/activity/{activity.id}/register", follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("活动正在进行中，无法报名", response.get_data(as_text=True))
        self.assertEqual(Registration.query.filter_by(activity_id=activity.id).count(), 0)

    def test_register_post_blocks_ended_activity(self):
        activity = self._activity(-timedelta(hours=3), -timedelta(hours=1))
        self._login()

        response = self.client.post(f"/activity/{activity.id}/register", follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("活动已结束，无法报名", response.get_data(as_text=True))
        self.assertEqual(Registration.query.filter_by(activity_id=activity.id).count(), 0)

    def test_register_post_blocks_full_activity(self):
        activity = self._activity(
            timedelta(days=1),
            timedelta(days=1, hours=2),
            max_participants=1,
            initial_participants=1,
        )
        self._login()

        response = self.client.post(f"/activity/{activity.id}/register", follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("该活动已满员，无法报名", response.get_data(as_text=True))
        self.assertEqual(Registration.query.filter_by(activity_id=activity.id).count(), 0)

    def test_register_post_blocks_duplicate_registration(self):
        activity = self._activity(timedelta(days=1), timedelta(days=1, hours=2))
        db.session.add(Registration(user_id=self.user.id, activity_id=activity.id))
        db.session.commit()
        self._login()

        response = self.client.post(f"/activity/{activity.id}/register", follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("您已报名该活动，无需重复报名", response.get_data(as_text=True))
        self.assertEqual(Registration.query.filter_by(activity_id=activity.id).count(), 1)


if __name__ == "__main__":
    unittest.main()
