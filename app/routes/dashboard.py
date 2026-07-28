from flask import Blueprint, jsonify, redirect, url_for

from app.models import Course, DailyEnrollmentHistory
from app.security import login_required


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def root():
    """Redirect visitors to the enterprise dashboard."""
    return redirect(url_for("dashboard.index"))


@dashboard_bp.route("/enterprise")
@login_required
def index():
    """Return a simple enterprise dashboard status payload."""
    return jsonify(
        {
            "name": "NPTEL Enterprise Course Intelligence Platform",
            "courses": Course.query.count(),
            "history_rows": DailyEnrollmentHistory.query.count(),
        }
    )
