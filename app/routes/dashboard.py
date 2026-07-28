from pathlib import Path

from flask import Blueprint, Response, redirect, send_from_directory, url_for

from app.security import current_user, login_required


dashboard_bp = Blueprint("dashboard", __name__)
BASE_DIR = Path(__file__).resolve().parents[2]
DOCS_DIR = BASE_DIR / "docs"
DASHBOARD_ASSETS = {
    "summary.json",
    "enrollment_report.csv",
    "member_summary.json",
    "member_counts.csv",
    "daily_log.json",
}

APP_TOOLBAR = """
<div class="necip-toolbar">
  <strong>NECIP</strong>
  <a href="/enterprise">Count Dashboard</a>
  <a href="/admin/">Admin</a>
  <a href="/admin/users">Users</a>
  <a href="/admin/tools">Tools</a>
  <a href="/api/v1/dashboard">API</a>
  <a class="logout" href="/logout">Logout</a>
</div>
<style>
  body { padding-top: 52px; }
  .necip-toolbar{position:fixed;top:0;left:0;right:0;height:52px;background:#111d2f;color:#fff;z-index:99999;display:flex;align-items:center;gap:10px;padding:0 18px;font-family:Segoe UI,Arial,sans-serif;box-shadow:0 8px 20px rgba(0,0,0,.18)}
  .necip-toolbar strong{margin-right:8px;font-weight:800}.necip-toolbar a{color:#fff;text-decoration:none;background:rgba(255,255,255,.1);padding:8px 10px;border-radius:6px;font-weight:700;font-size:13px}.necip-toolbar a:hover{background:rgba(255,255,255,.2)}.necip-toolbar .logout{margin-left:auto;background:#b42318}
  @media(max-width:760px){body{padding-top:96px}.necip-toolbar{height:auto;min-height:52px;flex-wrap:wrap;padding:8px 12px}.necip-toolbar .logout{margin-left:0}}
</style>
"""


@dashboard_bp.route("/")
def root():
    """Redirect visitors to the authenticated GitHub-style dashboard."""
    return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/enterprise")
@login_required
def index():
    """Render the existing GitHub Pages dashboard inside the authenticated app shell."""
    html = (DOCS_DIR / "index.html").read_text(encoding="utf-8")
    marker = "<body>"
    if marker in html:
        html = html.replace(marker, marker + APP_TOOLBAR, 1)
    else:
        html = APP_TOOLBAR + html
    response = Response(html, mimetype="text/html")
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@dashboard_bp.route("/<path:filename>")
@login_required
def docs_asset(filename):
    """Serve dashboard data assets required by docs/index.html."""
    if filename not in DASHBOARD_ASSETS:
        return redirect(url_for("dashboard.index"))
    response = send_from_directory(DOCS_DIR, filename)
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response
