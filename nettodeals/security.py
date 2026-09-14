"""Small, dependency-free admin session and input security helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit, urlunsplit

COOKIE_NAME = "nettodeals_admin"
_LOGIN_WINDOW_SECONDS = 300
_LOGIN_MAX_FAILURES = 5
_failed_logins: dict[str, deque[float]] = defaultdict(deque)


def constant_time_equal(left: str, right: str) -> bool:
    return bool(left) and bool(right) and secrets.compare_digest(left, right)


def normalize_external_url(value: object) -> str:
    """Return a safe HTTPS URL or an empty string.

    HTTP affiliate URLs are upgraded to HTTPS. URLs containing credentials,
    control characters, unsupported schemes, or an absent hostname are rejected.
    """
    raw = str(value or "").strip()
    if not raw or len(raw) > 2048 or any(ord(char) < 32 for char in raw):
        return ""
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return ""
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        return ""
    if parsed.username or parsed.password:
        return ""
    try:
        hostname = parsed.hostname.encode("idna").decode("ascii")
        port = f":{parsed.port}" if parsed.port else ""
    except (UnicodeError, ValueError):
        return ""
    return urlunsplit(("https", f"{hostname}{port}", parsed.path or "/", parsed.query, ""))


def _sign(secret: str, value: str) -> str:
    return hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def create_admin_session(secret: str, ttl_seconds: int) -> str:
    expiry = int(time.time()) + ttl_seconds
    nonce = secrets.token_urlsafe(18)
    payload = f"{expiry}.{nonce}"
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{encoded}.{_sign(secret, encoded)}"


def valid_admin_session(secret: str, cookie: str | None) -> bool:
    if not secret or not cookie or "." not in cookie:
        return False
    encoded, signature = cookie.rsplit(".", 1)
    if not secrets.compare_digest(signature, _sign(secret, encoded)):
        return False
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = base64.urlsafe_b64decode(padded).decode()
        expiry_text, _nonce = payload.split(".", 1)
        return int(expiry_text) >= int(time.time())
    except (ValueError, UnicodeDecodeError):
        return False


def csrf_token(secret: str, session_cookie: str) -> str:
    return _sign(secret, f"csrf:{session_cookie}")


def valid_csrf(secret: str, session_cookie: str | None, submitted: str) -> bool:
    if not session_cookie or not submitted:
        return False
    return secrets.compare_digest(csrf_token(secret, session_cookie), submitted)


def login_is_rate_limited(client_key: str) -> bool:
    now = time.monotonic()
    failures = _failed_logins[client_key]
    while failures and failures[0] < now - _LOGIN_WINDOW_SECONDS:
        failures.popleft()
    return len(failures) >= _LOGIN_MAX_FAILURES


def record_login_failure(client_key: str) -> None:
    _failed_logins[client_key].append(time.monotonic())


def clear_login_failures(client_key: str) -> None:
    _failed_logins.pop(client_key, None)


def redact_secrets(message: object, secrets_to_hide: tuple[str, ...]) -> str:
    text = str(message)
    for secret in secrets_to_hide:
        if secret:
            text = text.replace(secret, "[redacted]")
    # Query-string tokens often appear in requests' exception messages.
    parts = []
    for part in text.split("&"):
        if "token=" in part.casefold() or "accesstoken=" in part.casefold():
            key = part.split("=", 1)[0]
            parts.append(f"{key}=[redacted]")
        else:
            parts.append(part)
    return "&".join(parts)[:1000]
