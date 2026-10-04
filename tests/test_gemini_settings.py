import json
from dataclasses import replace
from pathlib import Path

import pytest
import requests
from fastapi.testclient import TestClient

from nettodeals.app import create_app
from nettodeals.db import connection, init_db
from nettodeals.gemini_settings import effective_settings, forget, save, status
from nettodeals.studio import gemini_copy
from tests.test_app import login

KEY = "test-only-key-012345678901234567890"
MODEL = "gemini-3.1-flash-lite"
URL = "/admin/settings/gemini"


def configure(client, settings):
    csrf = login(client, settings)
    result = client.post(URL + "/save", data=dict(csrf=csrf, api_key=KEY, model=MODEL, enabled="yes"))
    assert result.status_code == 200
    assert "Einstellungen gespeichert" in result.text
    return csrf


def test_auth_and_csrf(client, settings):
    assert client.get(URL).status_code == 401
    for route in ("save", "delete", "test"):
        assert client.post(URL + "/" + route, data={"csrf": "bad"}).status_code == 401
    login(client, settings)
    for route in ("save", "delete", "test"):
        assert client.post(URL + "/" + route, data={"csrf": "bad"}).status_code == 403


def test_encryption_no_reflection_and_restart(client, settings):
    configure(client, settings)
    for path in (URL, "/admin", "/api/status", "/", "/datenschutz"):
        assert KEY not in client.get(path).text
    response = client.get(URL)
    assert response.headers["cache-control"] == "no-store"
    assert "googletagmanager" not in response.headers["content-security-policy"]
    assert "/static/analytics.js" not in response.text
    with connection(settings.db_path) as conn:
        encrypted = conn.execute("SELECT encrypted FROM gemini_settings").fetchone()[0]
    assert KEY not in encrypted and encrypted.startswith("gAAAA")
    assert KEY.encode() not in Path(settings.db_path).read_bytes()
    assert effective_settings(settings).gemini_api_key == KEY
    with TestClient(create_app(settings)) as restarted:
        login(restarted, settings)
        assert "Schlüssel verfügbar" in restarted.get(URL).text
        assert effective_settings(settings).gemini_api_key == KEY


def test_settings_precedence_disable_and_forget(settings):
    init_db(settings.db_path)
    env = replace(settings, gemini_api_key="env-secret")
    assert effective_settings(env).gemini_api_key == "env-secret"
    save(env, KEY, MODEL, True)
    assert effective_settings(env).gemini_api_key == KEY
    save(env, "", MODEL, False)
    assert effective_settings(env).gemini_api_key == ""
    save(env, "", MODEL, True)
    assert effective_settings(env).gemini_api_key == KEY
    forget(env)
    assert effective_settings(env).gemini_api_key == ""
    with pytest.raises(ValueError, match="zuerst"):
        save(settings, "", MODEL, True)


def test_token_rotation_requires_resave(settings):
    init_db(settings.db_path)
    save(settings, KEY, MODEL, True)
    rotated = replace(settings, admin_token="different-test-admin-token-with-entropy")
    assert status(rotated)["configured"] is False
    assert "erneut speichern" in status(rotated)["error"]
    save(rotated, KEY, MODEL, True)
    assert effective_settings(rotated).gemini_api_key == KEY


@pytest.mark.parametrize("key,model", [(KEY + '"', MODEL), (KEY, "../../bad"), (KEY, "https://bad.example")])
def test_invalid_values_not_reflected(client, settings, key, model):
    csrf = login(client, settings)
    result = client.post(URL + "/save", data=dict(csrf=csrf, api_key=key, model=model, enabled="yes"))
    assert "ungültig" in result.text or "gültige" in result.text
    assert key not in result.text
    assert not status(settings)["configured"]


class GoodReply:
    status_code = 200

    def json(self):
        return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "OK"}]}}]}


def test_generation_probe_and_shared_limit(client, settings, monkeypatch):
    csrf = configure(client, settings)
    calls = []

    def post(url, **kwargs):
        assert KEY not in url
        assert kwargs["headers"]["x-goog-api-key"] == KEY
        assert kwargs["allow_redirects"] is False
        calls.append(url)
        return GoodReply()

    monkeypatch.setattr("nettodeals.gemini_routes.requests.post", post)
    unconfirmed = client.post(URL + "/test", data={"csrf": csrf})
    assert "bestätigen" in unconfirmed.text and len(calls) == 0
    for _ in range(10):
        response = client.post(URL + "/test", data=dict(csrf=csrf, confirmed="yes"))
        assert "Verbindungstest erfolgreich" in response.text
        assert KEY not in response.text
    response = client.post(URL + "/test", data=dict(csrf=csrf, confirmed="yes"))
    assert "Pilotlimit" in response.text and len(calls) == 10
    with pytest.raises(ValueError, match="Pilotlimit"):
        gemini_copy(settings, {"title": "Monitor"})


@pytest.mark.parametrize("code", [400, 401, 403, 404, 429, 503])
def test_http_diagnostics_hide_provider_body(client, settings, monkeypatch, code):
    csrf = configure(client, settings)

    class ErrorReply:
        status_code = code
        text = KEY

        def json(self):
            return {"error": {"message": KEY}}

    monkeypatch.setattr("nettodeals.gemini_routes.requests.post", lambda *a, **k: ErrorReply())
    response = client.post(URL + "/test", data=dict(csrf=csrf, confirmed="yes"))
    assert f"HTTP {code}" in response.text
    assert KEY not in response.text


def test_network_exception_not_reflected(client, settings, monkeypatch):
    csrf = configure(client, settings)

    def fail(*args, **kwargs):
        raise requests.ConnectionError(KEY)

    monkeypatch.setattr("nettodeals.gemini_routes.requests.post", fail)
    response = client.post(URL + "/test", data=dict(csrf=csrf, confirmed="yes"))
    assert "Netzwerkfehler" in response.text and KEY not in response.text


def test_probe_200_without_text_not_success(client, settings, monkeypatch):
    csrf = configure(client, settings)

    class EmptyReply(GoodReply):
        def json(self):
            return {"candidates": []}

    monkeypatch.setattr("nettodeals.gemini_routes.requests.post", lambda *a, **k: EmptyReply())
    response = client.post(URL + "/test", data=dict(csrf=csrf, confirmed="yes"))
    assert "ohne Textantwort" in response.text
    assert "Verbindungstest erfolgreich" not in response.text


def test_deal_generation_uses_saved_key(client, settings, monkeypatch):
    configure(client, settings)
    texts = {name: "Geprüfte Produktfakten." for name in ("summary", "x", "instagram", "tiktok")}

    class DraftReply(GoodReply):
        def json(self):
            return {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(texts)}]}}]}

    def post(url, **kwargs):
        assert MODEL in url and KEY not in url
        assert kwargs["headers"]["x-goog-api-key"] == KEY
        return DraftReply()

    monkeypatch.setattr("nettodeals.studio.requests.post", post)
    assert gemini_copy(settings, {"title": "Test Monitor", "description": "IPS"}) == texts


def test_delete_confirmation(client, settings):
    csrf = configure(client, settings)
    client.post(URL + "/delete", data={"csrf": csrf})
    assert status(settings)["configured"]
    response = client.post(URL + "/delete", data=dict(csrf=csrf, confirmed="yes"))
    assert "Schlüssel entfernt" in response.text
    assert not status(settings)["configured"]
