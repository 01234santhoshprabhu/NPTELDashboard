import threading
from pathlib import Path

from flask import Blueprint, current_app, redirect, render_template_string, request, url_for

from app.extensions import db
from app.models import Course, DailyEnrollmentHistory, Role, SchedulerLog, User, utcnow
from app.security import current_user, permission_required
from app.services.enrollment_service import EnrollmentImportService
from app.services.refresh_service import DailyRefreshService
from app.services.user_service import UserService


admin_bp = Blueprint("admin", __name__)
BASE_DIR = Path(__file__).resolve().parents[2]

ADMIN_TEMPLATE = """
<!doctype html><title>NECIP Admin</title><style>body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f7fb;color:#172033}.top{background:#111d2f;color:white;padding:18px 24px}.top a{color:white}.wrap{max-width:1180px;margin:auto;padding:22px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}.card{background:white;border:1px solid #d9dee8;border-radius:8px;padding:16px;box-shadow:0 10px 26px rgba(25,45,75,.05)}.value{font-size:30px;font-weight:800}a.button,button{display:inline-block;background:#1f6fd1;color:white;text-decoration:none;border:0;border-radius:6px;padding:9px 12px;font-weight:700;margin:3px;cursor:pointer}.danger{background:#b42318!important}.muted{color:#667085}.small{font-size:12px;word-break:break-all}table{width:100%;border-collapse:collapse;background:white}th,td{padding:9px;border-bottom:1px solid #eef1f5;text-align:left;vertical-align:top}input,select{padding:9px;border:1px solid #ccd4e0;border-radius:6px;margin:4px}.notice{background:#e9f8f1;border:1px solid #a8e0c4;padding:10px;border-radius:6px;margin:10px 0}.warn{background:#fff5df;border-color:#f4d68a}.inline{display:inline}</style><div class="top"><strong>NECIP Admin</strong> <span style="float:right"><a href="/enterprise">Dashboard</a> | <a href="/admin/tools">Tools</a> | <a href="/admin/users">Users</a> | {{ user.full_name }} | <a href="/logout">Logout</a></span></div><div class="wrap">{{ body|safe }}</div>
"""


def page(body):
    """Render a shared admin shell."""
    return render_template_string(ADMIN_TEMPLATE, body=body, user=current_user())


def database_location():
    """Return a readable database location for the admin UI."""
    uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
    if uri.startswith("sqlite:///"):
        return uri.replace("sqlite:///", "")
    return uri


def start_background_job(app, log_id, action):
    """Run a refresh action in a daemon thread with app context."""
    def worker():
        with app.app_context():
            service = DailyRefreshService()
            if action == "refresh":
                service.run(log_id=log_id)
            elif action == "member_sync":
                service.sync_member_files(log_id=log_id)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()


@admin_bp.before_app_request
def repair_stale_scheduler_logs():
    """Repair stale running jobs opportunistically before admin pages render."""
    if request.path.startswith("/admin"):
        DailyRefreshService().mark_stale_running_jobs_failed(older_than_minutes=30)


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
    <p class='muted small'>Database: {database_location()}</p>
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
    rows = "".join(user_row(user) for user in User.query.order_by(User.email.asc()).all())
    options = "".join(f"<option value='{role.name}'>{role.name}</option>" for role in roles)
    body = f"""
    <h1>User Management</h1>{message}
    <div class='card'><h2>Add Admin / Operator / Viewer Email</h2><form method='post'><input name='email' placeholder='Email ID' required><input name='full_name' placeholder='Full name' required><input name='password' placeholder='Temporary password' type='password' required><select name='roles' multiple size='4'>{options}</select><button>Create User</button></form><p class='muted'>Select Super Admin/Admin/Operator/Viewer. Use Ctrl+click for multiple roles.</p></div>
    <h2>Users</h2><table><thead><tr><th>Email</th><th>Name</th><th>Roles</th><th>Status</th><th>Actions</th></tr></thead><tbody>{rows}</tbody></table>
    """
    return page(body)


def user_row(user):
    """Render one user management table row."""
    me = current_user()
    actions = ""
    if user.id != me.id:
        toggle_label = "Disable" if user.is_active else "Enable"
        actions += f"<form class='inline' method='post' action='/admin/users/{user.id}/toggle'><button>{toggle_label}</button></form>"
        actions += f"<form class='inline' method='post' action='/admin/users/{user.id}/delete' onsubmit=\"return confirm('Delete this user?')\"><button class='danger'>Delete</button></form>"
    else:
        actions = "<span class='muted'>Current user</span>"
    return f"<tr><td>{user.email}</td><td>{user.full_name}</td><td>{', '.join(role.name for role in user.roles)}</td><td>{'Active' if user.is_active else 'Disabled'}</td><td>{actions}</td></tr>"


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@permission_required("users.manage")
def toggle_user(user_id):
    """Enable or disable an existing user account."""
    user = db.get_or_404(User, user_id)
    if user.id != current_user().id:
        UserService().set_active(user, not user.is_active)
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@permission_required("users.manage")
def delete_user(user_id):
    """Delete an existing user account except the current user."""
    user = db.get_or_404(User, user_id)
    if user.id != current_user().id:
        UserService().delete_user(user)
    return redirect(url_for("admin.users"))


@admin_bp.route("/tools")
@permission_required("scheduler.manage")
def tools():
    """Render operational tools for reports, APIs, scheduler, and data refresh."""
    summary_path = BASE_DIR / "docs" / "summary.json"
    report_path = BASE_DIR / "docs" / "enrollment_report.csv"
    member_path = BASE_DIR / "docs" / "member_counts.csv"
    report_status = "Available" if report_path.exists() else "Missing"
    summary_time = summary_path.stat().st_mtime if summary_path.exists() else None
    member_time = member_path.stat().st_mtime if member_path.exists() else None
    active_refresh = SchedulerLog.query.filter(SchedulerLog.status.in_(["queued", "running"])).order_by(SchedulerLog.started_at.desc()).first()
    disabled = "disabled" if active_refresh else ""
    logs = "".join(
        f"<tr><td>{log.started_at}</td><td>{log.job_name}</td><td>{log.status}</td><td>{log.finished_at or ''}</td><td>{log.message[:220]}</td></tr>"
        for log in SchedulerLog.query.order_by(SchedulerLog.started_at.desc()).limit(10).all()
    )
    body = f"""
    <h1>Application Tools</h1>
    {'<div class="notice warn">A refresh/sync job is currently running. Reload this page after a minute to check status.</div>' if active_refresh else ''}
    <div class='grid'>
      <div class='card'><h3>Count Dashboard</h3><p class='muted'>Authenticated version of the GitHub Pages dashboard.</p><a class='button' href='/enterprise'>Open</a></div>
      <div class='card'><h3>User Management</h3><p class='muted'>Add, disable, or delete admin/operator/viewer email IDs.</p><a class='button' href='/admin/users'>Open</a></div>
      <div class='card'><h3>Database</h3><p class='muted'>SQLite local fallback / PostgreSQL via DATABASE_URL.</p><p class='small'>{database_location()}</p></div>
      <div class='card'><h3>REST APIs</h3><p class='muted'>Dashboard, courses, history, reports, users.</p><a class='button' href='/api/v1/dashboard'>Dashboard API</a></div>
      <div class='card'><h3>Scheduler</h3><p class='muted'>Daily 9:00 AM refresh job. Current report: {report_status}</p><form method='post' action='/admin/import-current'><button>Import Current CSV to DB</button></form></div>
      <div class='card'><h3>Enrollment/Register Refresh</h3><p class='muted'>Runs NPTEL enrollment and exam-registration refresh in background. It may take several minutes.</p><form method='post' action='/admin/run-refresh'><button class='danger' {disabled}>Start Refresh</button></form></div>
      <div class='card'><h3>Member Count Sync</h3><p class='muted'>Copies latest member_test output into this dashboard.</p><form method='post' action='/admin/sync-members'><button {disabled}>Sync Member Counts</button></form></div>
      <div class='card'><h3>Exports</h3><p><a class='button' href='/enrollment_report.csv'>Enrollment CSV</a><a class='button' href='/member_counts.csv'>Member CSV</a></p></div>
    </div>
    <p class='muted small'>Report file modified timestamp: {summary_time or 'missing'} | Member file modified timestamp: {member_time or 'missing'}</p>
    <h2>Recent Scheduler Logs</h2><table><thead><tr><th>Started</th><th>Job</th><th>Status</th><th>Finished</th><th>Message</th></tr></thead><tbody>{logs or '<tr><td colspan="5">No logs yet.</td></tr>'}</tbody></table>
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
    """Start the full NPTEL refresh in the background."""
    log = SchedulerLog(job_name="daily_enrollment_refresh", status="queued", started_at=utcnow(), message="Queued from Admin Tools")
    db.session.add(log)
    db.session.commit()
    if current_app.config.get("TESTING"):
        DailyRefreshService().run(log_id=log.id)
    else:
        start_background_job(current_app._get_current_object(), log.id, "refresh")
    return redirect(url_for("admin.tools"))


@admin_bp.route("/sync-members", methods=["POST"])
@permission_required("scheduler.manage")
def sync_members():
    """Start member count file sync in the background."""
    log = SchedulerLog(job_name="member_count_sync", status="queued", started_at=utcnow(), message="Queued from Admin Tools")
    db.session.add(log)
    db.session.commit()
    if current_app.config.get("TESTING"):
        DailyRefreshService().sync_member_files(log_id=log.id)
    else:
        start_background_job(current_app._get_current_object(), log.id, "member_sync")
    return redirect(url_for("admin.tools"))

