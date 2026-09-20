import json
from dataclasses import replace

import pytest
import requests

from nettodeals.ai_editor import approve, fingerprint, generate
from nettodeals.db import connection
from nettodeals.deal_schedule import configure, enqueue, tick
from nettodeals.editorial import publish_deal
from tests.test_app import login
from tests.test_deal_workflow import draft

COPY = {"summary": "Die Kamera eignet sich für die beschriebene Aufnahmefunktion.", "x": "Kamera im Überblick.", "instagram": "Die Kamera im kurzen Überblick.", "tiktok": "Ein Blick auf die Kamera."}
FACTS = "Kamera mit Aufnahmefunktion; Herstellerdaten geprüft."


class Reply:
    status_code = 200

    def json(self):
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(COPY)}}]}


def fake(monkeypatch, response=None):
    calls = []
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return response or Reply()
    monkeypatch.setattr("nettodeals.ai_editor.requests.post", post)
    return calls


def test_missing_key_no_network(settings, monkeypatch):
    calls = fake(monkeypatch)
    deal_id = draft(settings)
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        generate(settings, deal_id, FACTS)
    assert calls == []
    publish_deal(settings.db_path, deal_id, settings)


def test_generate_approve_and_schedule(client, settings, monkeypatch):
    settings = replace(settings, groq_api_key="SECRET-KEY")
    calls = fake(monkeypatch)
    deal_id = draft(settings)
    enqueue(settings.db_path, deal_id)
    generate(settings, deal_id, FACTS)
    with connection(settings.db_path) as conn:
        assert conn.execute("SELECT status FROM deals").fetchone()[0] == "draft"
        assert not conn.execute("SELECT * FROM deal_queue").fetchall()
        ai = conn.execute("SELECT * FROM ai_drafts").fetchone()
    assert ai["status"] == "pending"
    assert COPY["summary"] not in client.get("/").text
    assert "SECRET-KEY" not in json.dumps(calls[0][1]["json"])
    assert "299" not in calls[0][1]["json"]["messages"][1]["content"]
    assert calls[0][1]["allow_redirects"] is False
    approve(settings.db_path, deal_id, ai["fingerprint"], COPY.copy())
    enqueue(settings.db_path, deal_id)
    configure(settings.db_path, True, 6)
    tick(settings.db_path, settings)
    home = client.get("/").text
    assert COPY["summary"] in home and "CHF 299.00" in home
    assert "Kein eigener Produkttest" in home


def test_cache_and_ten_attempt_limit(settings, monkeypatch):
    settings = replace(settings, groq_api_key="test")
    calls = fake(monkeypatch)
    deal_id = draft(settings)
    generate(settings, deal_id, FACTS)
    generate(settings, deal_id, FACTS)
    assert len(calls) == 1
    for i in range(9):
        generate(settings, deal_id, FACTS + str(i))
    with pytest.raises(ValueError, match="10 API"):
        generate(settings, deal_id, FACTS + "new")
    assert len(calls) == 10


@pytest.mark.parametrize("status,match", [(401, "Schlüssel"), (403, "Zugriff"), (429, "Kontingent"), (500, "fehlgeschlagen"), (302, "fehlgeschlagen")])
def test_api_errors_are_safe(settings, monkeypatch, status, match):
    settings = replace(settings, groq_api_key="SECRET")
    response = Reply()
    response.status_code = status
    calls = fake(monkeypatch, response)
    deal_id = draft(settings)
    with pytest.raises(ValueError, match=match):
        generate(settings, deal_id, FACTS)
    assert len(calls) == 1
    with connection(settings.db_path) as conn:
        assert not conn.execute("SELECT * FROM ai_drafts").fetchall()
        assert conn.execute("SELECT status FROM ai_attempts").fetchone()[0] == "failed"


def test_timeout_no_retry(settings, monkeypatch):
    settings = replace(settings, groq_api_key="SECRET")
    deal_id = draft(settings)
    def fail(*args, **kwargs):
        raise requests.Timeout("SECRET")
    monkeypatch.setattr("nettodeals.ai_editor.requests.post", fail)
    with pytest.raises(ValueError) as exc:
        generate(settings, deal_id, FACTS)
    assert "SECRET" not in str(exc.value)


def test_stale_facts_cannot_be_approved(settings, monkeypatch):
    settings = replace(settings, groq_api_key="test")
    fake(monkeypatch)
    deal_id = draft(settings)
    generate(settings, deal_id, FACTS)
    with connection(settings.db_path) as conn:
        ai = conn.execute("SELECT * FROM ai_drafts").fetchone()
        conn.execute("UPDATE deals SET base_price=250 WHERE id=?", (deal_id,))
    with pytest.raises(ValueError, match="Veralteter"):
        approve(settings.db_path, deal_id, ai["fingerprint"], COPY.copy())


def test_unapproved_text_never_published(settings, monkeypatch):
    settings = replace(settings, groq_api_key="test")
    fake(monkeypatch)
    deal_id = draft(settings)
    generate(settings, deal_id, FACTS)
    publish_deal(settings.db_path, deal_id, settings)
    with connection(settings.db_path) as conn:
        assert COPY["summary"] not in conn.execute("SELECT review_summary FROM deals").fetchone()[0]


@pytest.mark.parametrize("content", ['{"summary":"only"}', '{bad', json.dumps(dict(COPY, summary='<script>bad</script>')), json.dumps(dict(COPY, summary='Preis CHF 1'))])
def test_invalid_outputs_rejected(settings, monkeypatch, content):
    settings = replace(settings, groq_api_key="test")
    response = Reply()
    response.json = lambda: {"choices": [{"finish_reason":"stop", "message":{"content":content}}]}
    fake(monkeypatch, response)
    deal_id = draft(settings)
    with pytest.raises(ValueError):
        generate(settings, deal_id, FACTS)
    with connection(settings.db_path) as conn:
        assert not conn.execute("SELECT * FROM ai_drafts").fetchall()


def test_ai_routes_auth_csrf_and_no_key(client, settings):
    deal_id = draft(settings)
    assert client.get(f"/admin/deals/{deal_id}/ai").status_code == 401
    csrf = login(client, settings)
    assert client.post(f"/admin/deals/{deal_id}/ai/generate", data={"csrf":"bad", "facts": FACTS}).status_code == 403
    response = client.post(f"/admin/deals/{deal_id}/ai/generate", data={"csrf":csrf, "facts":FACTS, "confirmed":"yes"})
    assert response.status_code == 422
    assert "GROQ_API_KEY" in response.text
    assert "no-store" in response.headers["cache-control"]


def test_editable_approval_via_http(client, settings):
    deal_id = draft(settings)
    with connection(settings.db_path) as conn:
        deal = dict(conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone())
        digest = fingerprint(deal, FACTS)
        conn.execute("INSERT INTO ai_drafts VALUES (?,?,?,?,?,?,?)", (deal_id, digest, FACTS, json.dumps(COPY), 'test', 'pending', '2026-09-20'))
    csrf = login(client, settings)
    response = client.post(f"/admin/deals/{deal_id}/ai/approve", data={"csrf":csrf, "expected":digest, "confirmed":"yes", **COPY, "summary":"Redaktionell korrigierte Beschreibung."})
    assert response.status_code == 200
    publish_deal(settings.db_path, deal_id, settings)
    with connection(settings.db_path) as conn:
        assert "Redaktionell korrigierte Beschreibung." in conn.execute("SELECT review_summary FROM deals").fetchone()[0]
