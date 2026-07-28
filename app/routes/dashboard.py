from pathlib import Path

from flask import Blueprint, redirect, send_from_directory, url_for

from app.security import login_required


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


@dashboard_bp.route("/")
def root():
    """Redirect visitors to the authenticated GitHub-style dashboard."""
    return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/enterprise")
@login_required
def index():
    """Render the existing GitHub Pages dashboard after login."""
    return send_from_directory(DOCS_DIR, "index.html")


@dashboard_bp.route("/<path:filename>")
@login_required
def docs_asset(filename):
    """Serve dashboard data assets required by docs/index.html."""
    if filename not in DASHBOARD_ASSETS:
        return redirect(url_for("dashboard.index"))
    return send_from_directory(DOCS_DIR, filename)
