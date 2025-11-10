from flask import jsonify, g

from . import api_bp
from ..core.auth import require_jwt, require_admin


@api_bp.get('/auth/me')
def auth_me():
    """Return current user info if JWT is valid."""
    err = require_jwt()
    if err:
        return err
    sub = getattr(g, 'jwt', {}).get('sub')
    try:
        from ..core.logging import append_log
        append_log(f'토큰 검증 성공(auth/me): {sub}', True)
    except Exception:
        pass
    return jsonify({"email": sub})


@api_bp.get('/verify-jwt')
def verify_jwt():
    """Alias endpoint for quick token verification.

    Returns 200 with email on success, or 401/502 error JSON from require_jwt().
    """
    err = require_jwt()
    if err:
        return err
    sub = getattr(g, 'jwt', {}).get('sub')
    try:
        from ..core.logging import append_log
        append_log(f'토큰 검증 성공(verify-jwt): {sub}', True)
    except Exception:
        pass
    return jsonify({"ok": True, "email": sub})


@api_bp.get('/verify-admin')
def verify_admin():
    """Verify token and admin privileges."""
    err = require_jwt()
    if err:
        return err
    err2 = require_admin()
    if err2:
        return err2
    sub = getattr(g, 'jwt', {}).get('sub')
    return jsonify({"ok": True, "email": sub, "role": "admin"})
