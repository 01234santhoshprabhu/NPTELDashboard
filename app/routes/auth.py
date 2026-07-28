from flask import Blueprint, redirect, render_template_string, request, session, url_for

from app.extensions import db
from app.models import User, utcnow
from app.security import current_user


auth_bp = Blueprint("auth", __name__)

LOGIN_TEMPLATE = """
<!doctype html>
<title>NECIP Login</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;background:#f4f7fb;margin:0;display:grid;place-items:center;min-height:100vh;color:#172033}.card{width:min(420px,92vw);background:#fff;border:1px solid #d9dee8;border-radius:8px;padding:28px;box-shadow:0 18px 40px rgba(15,35,65,.09)}input{width:100%;padding:11px;margin:8px 0 14px;border:1px solid #ccd4e0;border-radius:6px}button{width:100%;padding:11px;border:0;border-radius:6px;background:#1f6fd1;color:white;font-weight:700}.error{color:#b42318}.muted{color:#667085;font-size:13px}
</style>
<div class="card"><h1>NECIP Login</h1><p class="muted">NPTEL Enterprise Course Intelligence Platform</p>
<form method="post"><input name="email" placeholder="Email" autocomplete="email"><input name="password" placeholder="Password" type="password" autocomplete="current-password"><button>Login</button></form>
{% if error %}<p class="error">{{ error }}</p>{% endif %}</div>
"""


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticate a user and store the user id in the session."""
    if current_user():
        return redirect(request.args.get("next") or url_for("dashboard.index"))
    error = None
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").lower()).first()
        if user and user.is_active and user.check_password(request.form.get("password", "")):
            user.last_login_at = utcnow()
            db.session.commit()
            session.clear()
            session["user_id"] = user.id
            return redirect(request.args.get("next") or url_for("dashboard.index"))
        error = "Invalid email or password"
    return render_template_string(LOGIN_TEMPLATE, error=error)


@auth_bp.route("/logout")
def logout():
    """Clear the current user session."""
    session.clear()
    return redirect(url_for("auth.login"))
