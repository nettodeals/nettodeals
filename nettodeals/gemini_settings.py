"""Encrypted, database-backed Gemini settings; never expose stored credentials."""
import base64
import hashlib
import json
import re
from dataclasses import replace

from cryptography.fernet import Fernet, InvalidToken

from .db import connection, now_iso

DEFAULT_MODEL = "gemini-3.1-flash-lite"


def _cipher(settings):
    if len(settings.admin_token) < 32:
        raise ValueError("Zum Speichern ist ein gültiger Admin-Zugang erforderlich.")
    # Domain-separated key derived from the existing server-side admin secret.
    key = hashlib.sha256(b"nettodeals:gemini-settings:v1\0" + settings.admin_token.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _stored(settings):
    with connection(settings.db_path) as conn:
        row = conn.execute("SELECT encrypted FROM gemini_settings WHERE id=1").fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(_cipher(settings).decrypt(row["encrypted"].encode()))
        if not isinstance(payload, dict) or not isinstance(payload.get("key"), str):
            raise ValueError("invalid payload")
        if not isinstance(payload.get("enabled"), bool) or not isinstance(payload.get("model"), str):
            raise ValueError("invalid payload")
        return payload
    except (InvalidToken, ValueError, TypeError, UnicodeError):
        raise ValueError(
            "Gespeicherte Gemini-Einstellungen nicht lesbar. Nach einem Admin-Token-Wechsel "
            "den API-Schlüssel erneut speichern oder die Einstellungen löschen."
        ) from None


def effective_settings(settings):
    saved = _stored(settings)
    if saved is None:
        return settings
    return replace(settings, gemini_api_key=saved["key"] if saved["enabled"] else "",
                   gemini_model=saved["model"])


def status(settings):
    """Only this non-secret projection may be passed into templates or JSON."""
    with connection(settings.db_path) as conn:
        row = conn.execute("SELECT updated_at FROM gemini_settings WHERE id=1").fetchone()
    try:
        effective = effective_settings(settings)
        return dict(configured=bool(effective.gemini_api_key), model=effective.gemini_model,
                    source="Adminbereich" if row else "Orbit-Umgebung",
                    error="", updated_at=row["updated_at"] if row else "")
    except ValueError as exc:
        return dict(configured=False, model=DEFAULT_MODEL, source="Adminbereich",
                    error=str(exc), updated_at=row["updated_at"] if row else "")


def normalize_api_key(value):
    """Treat credentials as opaque header values, not a frozen Google key format."""
    value = value.strip()
    # Remove one pair of enclosing copy/paste quotes, never internal characters.
    pairs = {'"': '"', "'": "'", '“': '”', '‘': '’'}
    if len(value) > 1 and value[0] in pairs and value[-1] == pairs[value[0]]:
        value = value[1:-1].strip()
    if not value:
        return ""
    if len(value) > 4096 or len(value) < 20:
        raise ValueError("API-Schlüssel muss vollständig sein (20 bis 4096 Zeichen).")
    if any(ord(c) < 33 or ord(c) > 126 or c in '\"\'' for c in value):
        raise ValueError("API-Schlüssel enthält Leerzeichen, Zeilenumbrüche oder ungültige Zeichen. Bitte vollständig neu kopieren.")
    if value.startswith(("{", "[", "http:", "https:")) or value.startswith(("GEMINI_API_KEY=", "Bearer ")):
        raise ValueError("Bitte nur den Schlüsselwert einfügen, keine Datei, URL oder Variablenzuweisung.")
    return value


def save(settings, api_key, model, enabled):
    api_key = normalize_api_key(api_key)
    model = model.strip()
    if not re.fullmatch(r"gemini-[a-zA-Z0-9.-]{1,74}", model):
        raise ValueError("Bitte eine gültige Gemini-Modell-ID eingeben, ohne models/ oder URL.")
    if not api_key:
        try:
            old = _stored(settings)
        except ValueError:
            old = None
        api_key = old["key"] if old else settings.gemini_api_key
    if enabled and not api_key:
        raise ValueError("Bitte zuerst einen Gemini-API-Schlüssel einfügen.")
    _write(settings, dict(key=api_key, model=model, enabled=enabled))


def _write(settings, payload):
    encrypted = _cipher(settings).encrypt(json.dumps(payload).encode()).decode()
    with connection(settings.db_path) as conn:
        conn.execute("""INSERT INTO gemini_settings(id,encrypted,updated_at) VALUES(1,?,?)
            ON CONFLICT(id) DO UPDATE SET encrypted=excluded.encrypted,updated_at=excluded.updated_at""",
                     (encrypted, now_iso()))


def forget(settings):
    # An explicit disabled record prevents an old environment key silently taking over.
    _write(settings, dict(key="", model=DEFAULT_MODEL, enabled=False))
