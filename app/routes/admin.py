from flask import Blueprint, redirect, render_template_string, request, url_for

from app.models import Role, User
from app.security import current_user, permission_required
from app.services.user_service import UserService


admin_bp = Blueprint("admin", __name__)

ADMIN_TEMPLATE = """
<!doctype html><title>NECIP Admin</title><style>body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f7fb;color:#172033}.top{background:#111d2f;color:white;padding:18px 24px}.wrap{max-width:1180px;margin:auto;padding:22px}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.card{background:white;border:1px solid #d9dee8;border-radius:8px;padding:16px}.value{font-size:30px;font-weight:800}a.button,button{display:inline-block;background:#1f6fd1;color:white;text-decoration:none;border:0;border-radius:6px;padding:9px 12px;font-weight:700}table{width:100%;border-collapse:collapse;background:white}th,td{padding:9px;border-bottom:1px solid #eef1f5;text-align:left}input,select{padding:9px;border:1px solid #ccd4e0;border-radius:6px;margin:4px}</style><div class="top"><strong>NECIP Admin</strong> <span style="float:right">{{ user.full_name }} | <a style="color:white" href="/logout">Logout</a></span></div><div class="wrap">{{ body|safe }}</div>
"""


def page(body):
    """Render a small shared admin shell."""
    return render_template_string(ADMIN_TEMPLATE, body=body, user=current_user())


@admin_bp.route("/")
@permission_required("dashboard.view")
def index():
    """Render the admin dashboard summary."""
    body = f"""
    <h1>Admin Dashboard</h1><div class='grid'>
      <div class='card'><div>Users</div><div class='value'>{User.query.count()}</div></div>
      <div class='card'><div>Roles</div><div class='value'>{Role.query.count()}</div></div>
      <div class='card'><div>Active Users</div><div class='value'>{User.query.filter_by(is_active=True).count()}</div></div>
      <div class='card'><div>Access</div><div class='value'>RBAC</div></div>
    </div><p><a class='button' href='{url_for('admin.users')}'>Manage Users</a></p>
    """
    return page(body)


@admin_bp.route("/users", methods=["GET", "POST"])
@permission_required("users.manage")
def users():
    """List and create application users."""
    service = UserService()
    if request.method == "POST":
        service.create_user(
            email=request.form["email"],
            full_name=request.form["full_name"],
            password=request.form["password"],
            role_names=request.form.getlist("roles"),
        )
        return redirect(url_for("admin.users"))

    roles = Role.query.order_by(Role.name.asc()).all()
    rows = "".join(
        f"<tr><td>{user.email}</td><td>{user.full_name}</td><td>{', '.join(role.name for role in user.roles)}</td><td>{'Active' if user.is_active else 'Disabled'}</td></tr>"
        for user in User.query.order_by(User.email.asc()).all()
    )
    options = "".join(f"<option value='{role.name}'>{role.name}</option>" for role in roles)
    body = f"""
    <h1>User Management</h1>
    <form method='post' class='card'><input name='email' placeholder='Email' required><input name='full_name' placeholder='Full name' required><input name='password' placeholder='Temporary password' type='password' required><select name='roles' multiple>{options}</select><button>Create User</button></form>
    <h2>Users</h2><table><thead><tr><th>Email</th><th>Name</th><th>Roles</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>
    """
    return page(body)
