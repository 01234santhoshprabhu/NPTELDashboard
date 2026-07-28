from flask import Blueprint, redirect, render_template_string, request, session, url_for

from app.models import User, utcnow
from app.extensions import db


auth_bp = Blueprint("auth", __name__)

LOGIN_TEMPLATE = """
<!doctype html><title>NECIP Login</title><h1>NPTEL Enterprise Login</h1>
<form method="post"><input name="email" placeholder="Email"><input name="password" placeholder="Password" type="password"><button>Login</button></form>
{% if error %}<p style="color:red">{{ error }}</p>{% endif %}
"""


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate a user and store the user id in the session."""
    error = None
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").lower()).first()
        if user and user.is_active and user.check_password(request.form.get("password", "")):
            user.last_login_at = utcnow()
            db.session.commit()
            session["user_id"] = user.id
            return redirect(url_for("dashboard.index"))
        error = "Invalid email or password"
    return render_template_string(LOGIN_TEMPLATE, error=error)


@auth_bp.route("/logout")
def logout():
    """Clear the current user session."""
    session.clear()
    return redirect(url_for("auth.login"))
