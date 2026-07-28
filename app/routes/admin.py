from pathlib import Path

from flask import Blueprint, redirect, render_template_string, request, url_for

from app.models import Course, DailyEnrollmentHistory, Role, SchedulerLog, User
from app.security import current_user, permission_required
from app.services.enrollment_service import EnrollmentImportService
from app.services.refresh_service import DailyRefreshService
from app.services.user_service import UserService


admin_bp = Blueprint("admin", __name__)
BASE_DIR = Path(__file__).resolve().parents[2]

ADMIN_TEMPLATE = """
<!doctype html><title>NECIP Admin</title><style>body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f7fb;color:#172033}.top{background:#111d2f;color:white;padding:18px 24px}.top a{color:white}.wrap{max-width:1180px;margin:auto;padding:22px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}.card{background:white;border:1px solid #d9dee8;border-radius:8px;padding:16px;box-shadow:0 10px 26px rgba(25,45,75,.05)}.value{font-size:30px;font-weight:800}a.button,button{display:inline-block;background:#1f6fd1;color:white;text-decoration:none;border:0;border-radius:6px;padding:9px 12px;font-weight:700;margin:3px;cursor:pointer}.danger{background:#b42318!important}.muted{color:#667085}table{width:100%;border-collapse:collapse;background:white}th,td{padding:9px;border-bottom:1px solid #eef1f5;text-align:left}input,select{padding:9px;border:1px solid #ccd4e0;border-radius:6px;margin:4px}.notice{background:#e9f8f1;border:1px solid #a8e0c4;padding:10px;border-radius:6px;margin:10px 0}.warn{background:#fff5df;border-color:#f4d68a}</style><div class="top"><strong>NECIP Admin</strong> <span style="float:right"><a href="/enterprise">Dashboard</a> | <a href="/admin/tools">Tools</a> | <a href="/admin/users">Users</a> | {{ user.full_name }} | <a href="/logout">Logout</a></span></div><div class="wrap">{{ body|safe }}</div>
"""


def page(body):
    """Render a shared admin shell."""
    return render_template_string(ADMIN_TEMPLATE, body=body, user=current_user())


@admin_bp.route("/")
@permission_required("dashboard.view")
def index():
    """Render the admin dashboard summary."""
    latest_date = DailyEnrollmentHistory.query.order_by(DailyEnrollmentHistory.snapshot_date.desc()).first()
    body = f"""
    <h1>Admin Dashboard</h1><div class='grid'>
      <div class='card'><div>Users</div><div class='value'>{User.query.count()}</div></div>
      <div class='card'><div>Roles</div><div class='value'>{Role.query.count()}</div></div>
      <div class='card'><div>Courses</div><div class='value'>{Course.query.count()}</div></div>
      <div class='card'><div>History Rows</div><div class='value'>{DailyEnrollmentHistory.query.count()}</div></div>
    </div>
    <p class='muted'>Latest DB snapshot: {latest_date.snapshot_date if latest_date else 'Not imported yet'}</p>
    <p><a class='button' href='{url_for('dashboard.index')}'>Open Count Dashboard</a><a class='button' href='{url_for('admin.users')}'>Manage Users</a><a class='button' href='{url_for('admin.tools')}'>Tools</a></p>
    """
    return page(body)


@admin_bp.route("/users", methods=["GET", "POST"])
@permission_required("users.manage")
def users():
    """List and create application users."""
    message = ""
    service = UserService()
    if request.method == "POST":
        try:
            service.create_user(
                email=request.form["email"],
                full_name=request.form["full_name"],
                password=request.form["password"],
                role_names=request.form.getlist("roles"),
            )
            message = "<div class='notice'>User created successfully.</div>"
        except ValueError as exc:
            message = f"<div class='notice warn'>{exc}</div>"

    roles = Role.query.order_by(Role.name.asc()).all()
    rows = "".join(
        f"<tr><td>{user.email}</td><td>{user.full_name}</td><td>{', '.join(role.name for role in user.roles)}</td><td>{'Active' if user.is_active else 'Disabled'}</td></tr>"
        for user in User.query.order_by(User.email.asc()).all()
    )
    options = "".join(f"<option value='{role.name}'>{role.name}</option>" for role in roles)
    body = f"""
    <h1>User Management</h1>{message}
    <div class='card'><h2>Add Admin / Operator / Viewer Email</h2><form method='post'><input name='email' placeholder='Email ID' required><input name='full_name' placeholder='Full name' required><input name='password' placeholder='Temporary password' type='password' required><select name='roles' multiple size='4'>{options}</select><button>Create User</button></form><p class='muted'>Select Super Admin/Admin/Operator/Viewer. Use Ctrl+click for multiple roles.</p></div>
    <h2>Users</h2><table><thead><tr><th>Email</th><th>Name</th><th>Roles</th><th>Status</th></tr></thead><tbody>{rows}</tbody></table>
    """
    return page(body)


@admin_bp.route("/tools")
@permission_required("scheduler.manage")
def tools():
    """Render operational tools for reports, APIs, scheduler, and data refresh."""
    summary_path = BASE_DIR / "docs" / "summary.json"
    report_path = BASE_DIR / "docs" / "enrollment_report.csv"
    summary_mtime = summary_path.stat().st_mtime if summary_path.exists() else None
    report_status = "Available" if report_path.exists() else "Missing"
    logs = "".join(
        f"<tr><td>{log.started_at}</td><td>{log.job_name}</td><td>{log.status}</td><td>{log.message[:180]}</td></tr>"
        for log in SchedulerLog.query.order_by(SchedulerLog.started_at.desc()).limit(10).all()
    )
    body = f"""
    <h1>Application Tools</h1>
    <div class='grid'>
      <div class='card'><h3>Count Dashboard</h3><p class='muted'>Authenticated version of the GitHub Pages dashboard.</p><a class='button' href='/enterprise'>Open</a></div>
      <div class='card'><h3>User Management</h3><p class='muted'>Add admin/operator/viewer email IDs.</p><a class='button' href='/admin/users'>Open</a></div>
      <div class='card'><h3>REST APIs</h3><p class='muted'>Dashboard, courses, history, reports, users.</p><a class='button' href='/api/v1/dashboard'>Dashboard API</a></div>
      <div class='card'><h3>Scheduler</h3><p class='muted'>Daily 9:00 AM refresh job. Current report: {report_status}</p><form method='post' action='/admin/import-current'><button>Import Current CSV to DB</button></form></div>
      <div class='card'><h3>Live Count Refresh</h3><p class='muted'>Runs the NPTEL API refresh. It may take several minutes for all courses.</p><form method='post' action='/admin/run-refresh'><button class='danger'>Refresh Counts Now</button></form></div>
      <div class='card'><h3>Exports</h3><p><a class='button' href='/enrollment_report.csv'>Enrollment CSV</a><a class='button' href='/member_counts.csv'>Member CSV</a></p></div>
    </div>
    <h2>Recent Scheduler Logs</h2><table><thead><tr><th>Started</th><th>Job</th><th>Status</th><th>Message</th></tr></thead><tbody>{logs or '<tr><td colspan="4">No logs yet.</td></tr>'}</tbody></table>
    """
    return page(body)


@admin_bp.route("/admin-dashboard")
def legacy_admin_dashboard():
    """Compatibility redirect for older admin-dashboard bookmarks."""
    return redirect(url_for("admin.index"))


@admin_bp.route("/import-current", methods=["POST"])
@permission_required("scheduler.manage")
def import_current():
    """Import the currently displayed CSV report into the database."""
    result = EnrollmentImportService().import_report(BASE_DIR / "docs" / "enrollment_report.csv", source="manual_import")
    return page(f"<h1>Import Complete</h1><div class='notice'>Imported {result['imported']} rows for {result['snapshot_date']}.</div><p><a class='button' href='/admin/tools'>Back to Tools</a></p>")


@admin_bp.route("/run-refresh", methods=["POST"])
@permission_required("scheduler.manage")
def run_refresh():
    """Run the full NPTEL refresh synchronously and import the result."""
    try:
        result = DailyRefreshService().run()
        return page(f"<h1>Refresh Complete</h1><div class='notice'>Imported {result['imported']} rows for {result['snapshot_date']}.</div><p><a class='button' href='/enterprise'>Open Count Dashboard</a></p>")
    except Exception as exc:
        return page(f"<h1>Refresh Failed</h1><div class='notice warn'>{exc}</div><p><a class='button' href='/admin/tools'>Back to Tools</a></p>")
