from functools import wraps

from flask import abort, redirect, request, session, url_for

from app.extensions import db
from app.models import User


def current_user():
    """Return the currently authenticated user or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


def login_required(view):
    """Require an authenticated active user for a route."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None or not user.is_active:
            return redirect(url_for("auth.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def permission_required(permission_name):
    """Require a specific RBAC permission for a route."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None or not user.is_active:
                return redirect(url_for("auth.login", next=request.path))
            if not user.has_permission(permission_name):
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator

