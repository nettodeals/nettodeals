"""Admin-only AI pilot, using the existing session and CSRF controls."""
import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from .ai_editor import FIELDS, LIMIT, approve, fingerprint, generate
from .db import connection
from .security import csrf_token


def register_ai_routes(app, settings, render, session_cookie, verify_csrf):
    def page(request, deal_id, message="", error="", submitted_facts=None):
        cookie = session_cookie(request, settings)
        with connection(settings.db_path) as conn:
            row = conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
            ai = conn.execute("SELECT * FROM ai_drafts WHERE deal_id=?", (deal_id,)).fetchone()
            count = conn.execute("SELECT count(*) FROM ai_attempts WHERE started_at>=?", (datetime.now(UTC).date().isoformat(),)).fetchone()[0]
        if not row:
            raise HTTPException(404, "Deal nicht gefunden")
        ai = dict(ai) if ai else None
        if ai:
            ai["texts"] = json.loads(ai["payload"])
            ai["stale"] = fingerprint(dict(row), ai["facts"]) != ai["fingerprint"]
        return render("ai_editor.html", deal=dict(row), ai=ai, fields=FIELDS,
                      used=count, limit=LIMIT, configured=bool(settings.groq_api_key),
                      model=settings.groq_model, message=message, error=error,
                      facts_value=submitted_facts if submitted_facts is not None else (ai["facts"] if ai else ""),
                      csrf_token=csrf_token(settings.admin_token, cookie))

    @app.get("/admin/deals/{deal_id}/ai")
    def editor(request: Request, deal_id: int):
        return page(request, deal_id)

    @app.post("/admin/deals/{deal_id}/ai/generate")
    def prepare(request: Request, deal_id: int, csrf: Annotated[str, Form()], facts: Annotated[str, Form()], confirmed: Annotated[str, Form()] = "no"):
        verify_csrf(request, settings, csrf)
        try:
            if confirmed != "yes":
                raise ValueError("Bitte Quellenprüfung und Übermittlung der Produktfakten bestätigen.")
            message = generate(settings, deal_id, facts)
        except ValueError as exc:
            response = page(request, deal_id, error=str(exc), submitted_facts=facts)
            response.status_code = 422
            return response
        return page(request, deal_id, message=message)

    @app.post("/admin/deals/{deal_id}/ai/approve")
    def accept(request: Request, deal_id: int, csrf: Annotated[str, Form()], expected: Annotated[str, Form()], summary: Annotated[str, Form()], x: Annotated[str, Form()], instagram: Annotated[str, Form()], tiktok: Annotated[str, Form()], confirmed: Annotated[str, Form()] = "no"):
        verify_csrf(request, settings, csrf)
        try:
            if confirmed != "yes":
                raise ValueError("Bitte den Faktenabgleich bestätigen.")
            approve(settings.db_path, deal_id, expected, dict(summary=summary, x=x, instagram=instagram, tiktok=tiktok))
        except ValueError as exc:
            response = page(request, deal_id, error=str(exc))
            response.status_code = 422
            return response
        return page(request, deal_id, message="Text freigegeben. Jetzt im Deal-Kontrollzentrum veröffentlichen oder für den Zeitplan freigeben.")

    @app.post("/admin/deals/{deal_id}/ai/discard")
    def discard(request: Request, deal_id: int, csrf: Annotated[str, Form()]):
        verify_csrf(request, settings, csrf)
        with connection(settings.db_path) as conn:
            conn.execute("DELETE FROM ai_drafts WHERE deal_id=?", (deal_id,))
        return RedirectResponse(f"/admin/deals/{deal_id}/ai", 303)
