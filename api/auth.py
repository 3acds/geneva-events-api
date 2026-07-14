"""Server-side Firebase Authentication helpers."""

from functools import wraps

from flask import g, jsonify, request

from api.config.database.db import initialize_firebase_admin


def verify_firebase_token(token):
    initialize_firebase_admin()
    from firebase_admin import auth
    return auth.verify_id_token(token, check_revoked=True)


def require_auth(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        authorization = request.headers.get("Authorization", "")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            return jsonify({"error": "Authentication required."}), 401
        try:
            claims = verify_firebase_token(token.strip())
        except Exception:
            # Token verification failures deliberately share one generic response.
            return jsonify({"error": "Invalid or expired authentication token."}), 401
        uid = claims.get("uid") or claims.get("sub")
        if not isinstance(uid, str) or not uid:
            return jsonify({"error": "Invalid or expired authentication token."}), 401
        g.current_user = {"uid": uid, "claims": claims}
        return view(*args, **kwargs)
    return wrapped
