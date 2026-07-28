import unittest
from unittest.mock import Mock, patch

from app import create_app
from app.config import Config
from app.database import init_database
from app.extensions import db


class DashboardAssetTestConfig(Config):
    """Test configuration for dashboard asset routes."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret"
    USE_REMOTE_DASHBOARD_ASSETS = False


class RemoteDashboardAssetTestConfig(DashboardAssetTestConfig):
    """Test configuration for public hosted dashboard asset proxying."""

    USE_REMOTE_DASHBOARD_ASSETS = True
    PUBLIC_DASHBOARD_BASE_URL = "https://example.invalid/dashboard"


class DashboardAssetRouteTest(unittest.TestCase):
    """Coverage for serving the existing GitHub Pages dashboard after login."""

    def setUp(self):
        """Create app, seed admin, and authenticate a client."""
        self.app = create_app(self.config_class)
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


class LocalDashboardAssetRouteTest(DashboardAssetRouteTest):
    config_class = DashboardAssetTestConfig

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


class RemoteDashboardAssetRouteTest(DashboardAssetRouteTest):
    config_class = RemoteDashboardAssetTestConfig

    @patch("app.routes.dashboard.requests.get")
    def test_dashboard_asset_can_proxy_from_public_pages(self, mocked_get):
        """Verify hosted Flask can use the live Pages dashboard data."""
        mocked_response = Mock()
        mocked_response.content = b'{"total_enrollment": 123}'
        mocked_response.headers = {"Content-Type": "application/json"}
        mocked_response.raise_for_status.return_value = None
        mocked_get.return_value = mocked_response

        response = self.client.get("/summary.json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/json")
        self.assertIn(b"123", response.data)
        mocked_get.assert_called_once_with(
            "https://example.invalid/dashboard/summary.json", timeout=20
        )


if __name__ == "__main__":
    unittest.main()
