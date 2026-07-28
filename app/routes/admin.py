from flask import Blueprint, jsonify

from app.models import Role, User


admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/")
def index():
    """Return admin dashboard summary data."""
    return jsonify({"users": User.query.count(), "roles": Role.query.count()})
