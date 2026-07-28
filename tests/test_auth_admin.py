import unittest

from app import create_app
from app.config import Config
from app.database import init_database
from app.extensions import db
from app.models import Role, User


class AuthAdminTestConfig(Config):
    """Test configuration for auth and admin routes."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test-secret"
    WTF_CSRF_ENABLED = False


class AuthAdminRouteTest(unittest.TestCase):
    """Coverage for login, RBAC, and user management."""

    def setUp(self):
        """Create seeded app and test client."""
        self.app = create_app(AuthAdminTestConfig)
        self.context = self.app.app_context()
        self.context.push()
        db.drop_all()
        db.create_all()
        init_database("admin@example.com", "secret123")
        viewer = User(email="viewer@example.com", full_name="Viewer User")
        viewer.set_password("secret123")
        viewer.roles.append(Role.query.filter_by(name="Viewer").first())
        db.session.add(viewer)
        db.session.commit()
        self.client = self.app.test_client()

    def tearDown(self):
        """Clean up database and context."""
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def login(self, email):
        """Authenticate a test user."""
        return self.client.post("/login", data={"email": email, "password": "secret123"}, follow_redirects=False)

    def test_login_sets_session(self):
        """Verify valid credentials redirect into the application."""
        response = self.login("admin@example.com")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), "/enterprise")
        with self.client.session_transaction() as session:
            self.assertIn("user_id", session)

    def test_login_follow_redirects_shows_admin_dashboard(self):
        """Verify login lands on a usable HTML admin page."""
        response = self.client.post("/login", data={"email": "admin@example.com", "password": "secret123"}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"NPTEL Enrollment and Member Live Dashboard", response.data)

    def test_admin_requires_users_manage_permission(self):
        """Verify viewers cannot access user administration."""
        self.login("viewer@example.com")
        response = self.client.get("/admin/users")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_user(self):
        """Verify admins can create users through the management route."""
        self.login("admin@example.com")
        response = self.client.post(
            "/admin/users",
            data={"email": "operator@example.com", "full_name": "Ops User", "password": "secret123", "roles": ["Operator"]},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        created = User.query.filter_by(email="operator@example.com").first()
        self.assertIsNotNone(created)
        self.assertEqual(created.roles[0].name, "Operator")


if __name__ == "__main__":
    unittest.main()
