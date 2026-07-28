import unittest

from app import create_app
from app.config import Config
from app.database import init_database
from app.extensions import db


class DashboardAssetTestConfig(Config):
    """Test configuration for dashboard asset routes."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret"


class DashboardAssetRouteTest(unittest.TestCase):
    """Coverage for serving the existing GitHub Pages dashboard after login."""

    def setUp(self):
        """Create app, seed admin, and authenticate a client."""
        self.app = create_app(DashboardAssetTestConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        init_database("admin@example.com", "secret123")
        self.client = self.app.test_client()
        self.client.post("/login", data={"email": "admin@example.com", "password": "secret123"})

    def tearDown(self):
        """Clean up database and context."""
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_enterprise_serves_existing_dashboard_html(self):
        """Verify /enterprise serves docs/index.html instead of JSON."""
        response = self.client.get("/enterprise")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"NPTEL Enrollment and Member Live Dashboard", response.data)
        self.assertIn(b"Logout", response.data)
        self.assertIn(b"Tools", response.data)

    def test_dashboard_assets_are_available_after_login(self):
        """Verify existing dashboard data files are served from Flask."""
        response = self.client.get("/summary.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        csv_response = self.client.get("/enrollment_report.csv")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn(b"Course_ID", csv_response.data)


if __name__ == "__main__":
    unittest.main()
