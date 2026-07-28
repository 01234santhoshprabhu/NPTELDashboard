from app.extensions import db
from app.models import Permission, Role, User

DEFAULT_PERMISSIONS = {
    "dashboard.view": "View dashboards and analytics",
    "users.manage": "Create and manage users",
    "roles.manage": "Create and manage roles",
    "reports.export": "Export reports",
    "scheduler.manage": "Run and configure scheduled jobs",
    "api.read": "Read REST API resources",
}

DEFAULT_ROLES = {
    "Super Admin": list(DEFAULT_PERMISSIONS),
    "Admin": ["dashboard.view", "users.manage", "reports.export", "scheduler.manage", "api.read"],
    "Operator": ["dashboard.view", "reports.export", "scheduler.manage", "api.read"],
    "Viewer": ["dashboard.view", "api.read"],
}


def init_database(admin_email=None, admin_password=None):
    """Create schema, seed permissions and roles, and ensure an admin user exists."""
    db.create_all()
    permissions = {}
    for name, description in DEFAULT_PERMISSIONS.items():
        permission = Permission.query.filter_by(name=name).first()
        if permission is None:
            permission = Permission(name=name, description=description)
            db.session.add(permission)
        permissions[name] = permission

    for role_name, permission_names in DEFAULT_ROLES.items():
        role = Role.query.filter_by(name=role_name).first()
        if role is None:
            role = Role(name=role_name, description=f"Built-in {role_name} role")
            db.session.add(role)
        role.permissions = [permissions[name] for name in permission_names]

    if admin_email and admin_password:
        user = User.query.filter_by(email=admin_email.lower()).first()
        if user is None:
            user = User(email=admin_email.lower(), full_name="System Administrator")
            user.set_password(admin_password)
            db.session.add(user)
        super_admin = Role.query.filter_by(name="Super Admin").first()
        if super_admin and super_admin not in user.roles:
            user.roles.append(super_admin)

    db.session.commit()
