"""Authenticated Gemini setup and a bounded generation probe from the server."""
import hashlib
import socket
from typing import Annotated

import requests
from fastapi import Form, Request

from .db import connection, now_iso
from .gemini_settings import effective_settings, forget, save, status
from .security import csrf_token
from .studio import gemini_http_error, reserve_gemini_attempt


def register_gemini_routes(app, settings, render, session_cookie, verify_csrf):
    def page(request, message="", error=""):
        cookie = session_cookie(request, settings)
        with connection(settings.db_path) as conn:
            used = conn.execute("SELECT count(*) FROM studio_attempts WHERE created_at>=?",
                                (now_iso()[:10],)).fetchone()[0]
        return render("gemini_settings.html", gemini=status(settings), used=used,
                      instance=hashlib.sha256(socket.gethostname().encode()).hexdigest()[:10],
                      message=message, error=error,
                      csrf_token=csrf_token(settings.admin_token, cookie))

    @app.get("/admin/settings/gemini")
    def settings_page(request: Request):
        return page(request)

    @app.post("/admin/settings/gemini/save")
    def save_settings(request: Request, csrf: Annotated[str, Form()],
                      api_key: Annotated[str, Form()] = "",
                      model: Annotated[str, Form()] = "",
                      enabled: Annotated[str, Form()] = "no"):
        verify_csrf(request, settings, csrf)
        try:
            save(settings, api_key, model, enabled == "yes")
        except ValueError as exc:
            return page(request, error=str(exc))
        return page(request, message="Einstellungen gespeichert. Sie gelten sofort auf dieser Instanz. "
                    "Mit dem Verbindungstest den tatsächlichen API-Zugriff prüfen.")

    @app.post("/admin/settings/gemini/delete")
    def delete_settings(request: Request, csrf: Annotated[str, Form()],
                        confirmed: Annotated[str, Form()] = "no"):
        verify_csrf(request, settings, csrf)
        if confirmed != "yes":
            return page(request, error="Bitte das Entfernen des gespeicherten Schlüssels bestätigen.")
        forget(settings)
        return page(request, message="Gespeicherter Schlüssel entfernt und Gemini deaktiviert. "
                    "Ein eventuell vorhandener Orbit-Schlüssel bleibt übersteuert. "
                    "Alte Sicherungen sind davon nicht betroffen; einen kompromittierten Schlüssel bei Google widerrufen.")

    @app.post("/admin/settings/gemini/test")
    def test_settings(request: Request, csrf: Annotated[str, Form()],
                      confirmed: Annotated[str, Form()] = "no"):
        verify_csrf(request, settings, csrf)
        if confirmed != "yes":
            return page(request, error="Bitte den API-Test bestätigen.")
        try:
            active = effective_settings(settings)
            reserve_gemini_attempt(active)
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{active.gemini_model}:generateContent",
                headers={"x-goog-api-key": active.gemini_api_key},
                json={"contents": [{"parts": [{"text": "Antworte nur mit OK."}]}],
                      "generationConfig": {"maxOutputTokens": 256}},
                timeout=(5, 35), allow_redirects=False)
            if response.status_code != 200:
                raise ValueError(gemini_http_error(response.status_code))
            payload = response.json()
            candidates = payload.get("candidates", []) if isinstance(payload, dict) else []
            if not candidates or not isinstance(candidates[0], dict):
                raise ValueError("Gemini erreichbar, aber ohne Textantwort. Modell und Projektfreigabe prüfen.")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not any(isinstance(part, dict) and part.get("text") and not part.get("thought") for part in parts):
                raise ValueError("Gemini erreichbar, aber ohne nutzbare Textantwort. Modell oder Ausgabelimit prüfen.")
        except requests.exceptions.JSONDecodeError:
            return page(request, error="Gemini-Antwort war kein gültiges JSON.")
        except requests.Timeout:
            return page(request, error="Gemini-Zeitüberschreitung. Verbindung vom Hosting zu Google prüfen.")
        except requests.RequestException:
            return page(request, error="Gemini-Netzwerkfehler. DNS, TLS oder ausgehende Verbindung zu Google prüfen.")
        except (KeyError, IndexError, TypeError, AttributeError):
            return page(request, error="Gemini-Antwort unlesbar. Es wurden keine Zugangsdaten ausgegeben.")
        except ValueError as exc:
            return page(request, error=str(exc))
        return page(request, message="Verbindungstest erfolgreich: Google hat vom Server aus eine Textantwort geliefert. "
                    "Jetzt im Deal-Editor „Gemini verwenden“ wählen. Der Test bestätigt keinen kostenlosen Tarif.")
