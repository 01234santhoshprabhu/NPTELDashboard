from flask import Blueprint, redirect, render_template_string, url_for

from app.extensions import db
from app.models import Course, DailyEnrollmentHistory
from app.security import login_required


dashboard_bp = Blueprint("dashboard", __name__)

DASHBOARD_TEMPLATE = """
<!doctype html>
<title>NECIP Dashboard</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#f4f7fb;color:#172033}.top{background:#111d2f;color:white;padding:18px 24px}.wrap{max-width:1180px;margin:auto;padding:22px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px}.card{background:white;border:1px solid #d9dee8;border-radius:8px;padding:16px;box-shadow:0 10px 26px rgba(25,45,75,.05)}.value{font-size:32px;font-weight:800;margin-top:6px}.muted{color:#667085}a.button{display:inline-block;background:#1f6fd1;color:white;text-decoration:none;border-radius:6px;padding:9px 12px;font-weight:700;margin-right:8px}
</style>
<div class="top"><strong>NECIP Dashboard</strong><span style="float:right"><a style="color:white" href="/admin/">Admin</a> | <a style="color:white" href="/logout">Logout</a></span></div>
<div class="wrap">
<h1>NPTEL Enterprise Course Intelligence Platform</h1>
<p class="muted">Database-backed enrollment intelligence dashboard.</p>
<div class="grid">
  <div class="card"><div>Courses</div><div class="value">{{ course_count }}</div></div>
  <div class="card"><div>History Rows</div><div class="value">{{ history_rows }}</div></div>
  <div class="card"><div>Latest Snapshot</div><div class="value">{{ latest_date or '-' }}</div></div>
  <div class="card"><div>Total Enrollment</div><div class="value">{{ total_enrollment }}</div></div>
</div>
<p style="margin-top:18px"><a class="button" href="/admin/">Admin Dashboard</a><a class="button" href="/api/v1/dashboard">Dashboard API</a></p>
</div>
"""


@dashboard_bp.route("/")
def root():
    """Redirect visitors to the enterprise dashboard."""
    return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/enterprise")
@login_required
def index():
    """Render the enterprise dashboard page."""
    latest_date = db.session.query(db.func.max(DailyEnrollmentHistory.snapshot_date)).scalar()
    rows = DailyEnrollmentHistory.query.filter_by(snapshot_date=latest_date).all() if latest_date else []
    return render_template_string(
        DASHBOARD_TEMPLATE,
        course_count=Course.query.count(),
        history_rows=DailyEnrollmentHistory.query.count(),
        latest_date=latest_date.isoformat() if latest_date else None,
        total_enrollment=sum(row.learners_enrolled or 0 for row in rows),
    )
