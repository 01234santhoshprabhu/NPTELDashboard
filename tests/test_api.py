import unittest
from datetime import date

from app import create_app
from app.config import Config
from app.database import init_database
from app.extensions import db
from app.models import Course, DailyEnrollmentHistory, Role, User


class ApiTestConfig(Config):
    """Test configuration for REST API routes."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret"


class RestApiTest(unittest.TestCase):
    """Coverage for authenticated REST API endpoints."""

    def setUp(self):
        """Create seeded API test data."""
        self.app = create_app(ApiTestConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        init_database("admin@example.com", "secret123")
        viewer = User(email="viewer@example.com", full_name="Viewer User")
        viewer.set_password("secret123")
        viewer.roles.append(Role.query.filter_by(name="Viewer").first())
        course = Course(course_id="noc26_cs01", course_url="https://example.test/noc26_cs01")
        db.session.add_all([viewer, course])
        db.session.flush()
        db.session.add(DailyEnrollmentHistory(course=course, snapshot_date=date(2026, 7, 28), learners_enrolled=100, exam_registration=25))
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up database and context."""
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def api_login(self, email="admin@example.com"):
        """Authenticate through the REST login endpoint."""
        return self.client.post("/api/v1/auth/login", json={"email": email, "password": "secret123"})

    def test_api_login_returns_permissions(self):
        """Verify API login returns permission data."""
        response = self.api_login()
        self.assertEqual(response.status_code, 200)
        self.assertIn("users.manage", response.get_json()["permissions"])

    def test_dashboard_summary_requires_login(self):
        """Verify dashboard API redirects unauthenticated clients."""
        response = self.client.get("/api/v1/dashboard")
        self.assertEqual(response.status_code, 302)

    def test_viewer_can_read_courses_but_not_users(self):
        """Verify RBAC protects management API routes."""
        self.api_login("viewer@example.com")
        self.assertEqual(self.client.get("/api/v1/courses").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/users").status_code, 403)

    def test_admin_can_create_user_via_api(self):
        """Verify admins can create users through REST API."""
        self.api_login()
        response = self.client.post(
            "/api/v1/users",
            json={"email": "operator@example.com", "full_name": "Ops User", "password": "secret123", "roles": ["Operator"]},
        )
        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(User.query.filter_by(email="operator@example.com").first())


if __name__ == "__main__":
    unittest.main()
