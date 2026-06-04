import unittest
from datetime import datetime, timedelta

from app import create_app
from app.models import Activity, Circle, CircleRating, Registration, User, db


class CircleRatingEligibilityTestCase(unittest.TestCase):
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

        self.user = User(
            username="rating_user",
            email="rating_user@example.com",
            password_hash="scrypt:test",
        )
        self.organizer = User(
            username="organizer",
            email="organizer@example.com",
            password_hash="scrypt:test",
        )
        self.circle = Circle(name="电影同好圈", tag="观影戏剧")
        db.session.add_all([self.user, self.organizer, self.circle])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def _login(self):
        with self.client.session_transaction() as session:
            session["user_id"] = self.user.id

    def _activity(self, title, start_time):
        activity = Activity(
            title=title,
            description="活动简介",
            city="上海",
            location="活动地点",
            start_time=start_time,
            end_time=start_time + timedelta(hours=2),
            circle_id=self.circle.id,
            organizer_id=self.organizer.id,
        )
        db.session.add(activity)
        db.session.commit()
        return activity

    def _register(self, activity):
        db.session.add(Registration(user_id=self.user.id, activity_id=activity.id))
        db.session.commit()

    def test_future_circle_activity_does_not_allow_rating(self):
        future_activity = self._activity("尚未开始的活动", datetime.now() + timedelta(days=1))
        self._register(future_activity)
        self._login()

        response = self.client.post(
            f"/circle/{self.circle.id}/ratings",
            data={"rating": "5", "comment": "期待活动"},
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIsNone(CircleRating.query.filter_by(user_id=self.user.id).first())

    def test_started_circle_activity_allows_rating_and_binds_activity(self):
        started_activity = self._activity("独立电影放映与交流夜", datetime.now() - timedelta(hours=1))
        self._register(started_activity)
        self._login()

        response = self.client.post(
            f"/circle/{self.circle.id}/ratings",
            data={
                "activity_id": str(started_activity.id),
                "rating": "4",
                "comment": "活动之后再评价，体验真实。",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        rating = CircleRating.query.filter_by(user_id=self.user.id, circle_id=self.circle.id).one()
        self.assertEqual(rating.activity_id, started_activity.id)
        self.assertEqual(rating.rating, 4)

    def test_rating_review_shows_bound_activity(self):
        started_activity = self._activity("独立电影放映与交流夜", datetime.now() - timedelta(days=1))
        self._register(started_activity)
        db.session.add(
            CircleRating(
                circle_id=self.circle.id,
                user_id=self.user.id,
                activity_id=started_activity.id,
                rating=5,
                comment="现场交流很顺畅。",
            )
        )
        db.session.commit()

        response = self.client.get(f"/circle/{self.circle.id}")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("独立电影放映与交流夜", html)
        self.assertIn(f"{started_activity.start_time.year}年{started_activity.start_time.month}月", html)


if __name__ == "__main__":
    unittest.main()
