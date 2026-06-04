import unittest
from datetime import datetime, timedelta

from app import create_app
from app.models import Activity, AdminLog, User, db


class ActivityAdminTimeManagementTestCase(unittest.TestCase):
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

        self.admin = User(
            username="admin_user",
            email="admin@example.com",
            password_hash="scrypt:test",
            role="admin",
        )
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
        db.session.add_all([self.admin, self.organizer, self.user])
        db.session.commit()

        self.original_start = datetime(2030, 5, 1, 10, 0)
        self.original_end = self.original_start + timedelta(hours=2)
        self.activity = Activity(
            title="管理员时间测试活动",
            description="活动简介",
            detail="活动详情",
            city="上海",
            location="活动地点",
            start_time=self.original_start,
            end_time=self.original_end,
            organizer_id=self.organizer.id,
            status="open",
        )
        db.session.add(self.activity)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self, user):
        with self.client.session_transaction() as session:
            session["user_id"] = user.id

    def _post_update_time(self, start_time, end_time, follow_redirects=False):
        return self.client.post(
            f"/activity/{self.activity.id}/admin/update-time",
            data={
                "start_time": start_time.strftime("%Y-%m-%dT%H:%M"),
                "end_time": end_time.strftime("%Y-%m-%dT%H:%M"),
            },
            follow_redirects=follow_redirects,
        )

    def test_admin_time_management_visibility_is_limited_to_system_admin(self):
        self._login(self.user)
        response = self.client.get(f"/activity/{self.activity.id}")
        html = response.get_data(as_text=True)
        self.assertNotIn("保存活动时间", html)
        self.assertNotIn(f"/activity/{self.activity.id}/admin/update-time", html)

        self._login(self.organizer)
        response = self.client.get(f"/activity/{self.activity.id}")
        html = response.get_data(as_text=True)
        self.assertNotIn("保存活动时间", html)
        self.assertNotIn(f"/activity/{self.activity.id}/admin/update-time", html)

        self._login(self.admin)
        response = self.client.get(f"/activity/{self.activity.id}")
        html = response.get_data(as_text=True)
        self.assertIn("活动管理", html)
        self.assertIn("保存活动时间", html)
        self.assertIn(f"/activity/{self.activity.id}/admin/update-time", html)

    def test_regular_user_direct_post_is_rejected(self):
        self._login(self.user)
        new_start = datetime(2030, 5, 2, 14, 0)
        new_end = new_start + timedelta(hours=3)

        response = self._post_update_time(new_start, new_end)

        self.assertEqual(response.status_code, 403)
        db.session.refresh(self.activity)
        self.assertEqual(self.activity.start_time, self.original_start)
        self.assertEqual(self.activity.end_time, self.original_end)

    def test_end_time_must_be_later_than_start_time(self):
        self._login(self.admin)
        invalid_start = datetime(2030, 5, 2, 14, 0)
        invalid_end = datetime(2030, 5, 2, 13, 0)

        response = self._post_update_time(invalid_start, invalid_end, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        db.session.refresh(self.activity)
        self.assertEqual(self.activity.start_time, self.original_start)
        self.assertEqual(self.activity.end_time, self.original_end)
        self.assertEqual(AdminLog.query.count(), 0)

    def test_system_admin_can_update_activity_time_and_log_action(self):
        self._login(self.admin)
        new_start = datetime(2030, 5, 3, 9, 30)
        new_end = datetime(2030, 5, 3, 12, 0)

        response = self._post_update_time(new_start, new_end, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        db.session.refresh(self.activity)
        self.assertEqual(self.activity.start_time, new_start)
        self.assertEqual(self.activity.end_time, new_end)
        self.assertIn(new_start.strftime("%Y-%m-%d %H:%M"), response.get_data(as_text=True))

        log = AdminLog.query.filter_by(
            admin_id=self.admin.id,
            action="update_activity_time",
            target_type="activity",
            target_id=self.activity.id,
        ).one()
        self.assertIn(f"activity_id: {self.activity.id}", log.detail)
        self.assertIn(self.original_start.strftime("%Y-%m-%d %H:%M"), log.detail)
        self.assertIn(new_start.strftime("%Y-%m-%d %H:%M"), log.detail)

    def test_system_admin_can_update_closed_activity_time(self):
        self.activity.status = "closed"
        self.activity.start_time = datetime(2029, 5, 1, 10, 0)
        self.activity.end_time = datetime(2029, 5, 1, 12, 0)
        db.session.commit()
        self._login(self.admin)
        new_start = datetime(2029, 5, 2, 10, 0)
        new_end = datetime(2029, 5, 2, 12, 0)

        response = self._post_update_time(new_start, new_end)

        self.assertEqual(response.status_code, 302)
        db.session.refresh(self.activity)
        self.assertEqual(self.activity.status, "closed")
        self.assertEqual(self.activity.start_time, new_start)
        self.assertEqual(self.activity.end_time, new_end)


if __name__ == "__main__":
    unittest.main()
