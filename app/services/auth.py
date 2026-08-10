"""Minimal in-server session auth.

Deliberately not a real user system - the spec calls for "a temporary login
system which runs within the server," admin/admin, attributed to a fake
display name. Sessions live in a process-local dict, so they reset on
restart; that's the intended scope here, not an oversight.
"""
import secrets

from fastapi import Cookie, HTTPException

SESSION_COOKIE = "specter_session"

# username -> {password, display_name}
_USERS = {
    "admin": {"password": "admin", "display_name": "Tom"},
}

# token -> {username, display_name}
_SESSIONS: dict[str, dict] = {}


def create_session(username: str, password: str) -> tuple[str, dict]:
    user = _USERS.get(username)
    if not user or not secrets.compare_digest(user["password"], password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = secrets.token_hex(24)
    session = {"username": username, "display_name": user["display_name"]}
    _SESSIONS[token] = session
    return token, session


def destroy_session(token: str | None) -> None:
    if token:
        _SESSIONS.pop(token, None)


def require_auth(session_token: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict:
    session = _SESSIONS.get(session_token) if session_token else None
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session
