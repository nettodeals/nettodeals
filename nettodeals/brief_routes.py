"""Public brief pages and authenticated editorial/social tools."""

from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from typing import Annotated, Any
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from .briefs import (
    brief_dict,
    configure_schedule,
    parse_date,
    save_brief,
)
from .db import connection
from .security import csrf_token
from .seo import slugify
from .social_cards import render_card


def register_brief_routes(app, settings, render, session_cookie, verify_csrf) -> None:
    def context(request: Request, **extra: Any) -> dict[str, Any]:
        cookie = session_cookie(request, settings)
        with connection(settings.db_path) as conn:
            drafts = conn.execute(
                """SELECT deals.* FROM deals WHERE status='draft'
                   AND NOT EXISTS (SELECT 1 FROM briefs WHERE source_deal_id=deals.id)
                   ORDER BY updated_at DESC LIMIT 100"""
            ).fetchall()
            briefs = conn.execute("SELECT * FROM briefs ORDER BY id DESC LIMIT 100").fetchall()
            exports = conn.execute(
                """SELECT social_exports.*, briefs.title, briefs.status AS brief_status
                   FROM social_exports JOIN briefs ON briefs.id=social_exports.brief_id
                   ORDER BY social_exports.id DESC LIMIT 90"""
            ).fetchall()
            schedule = conn.execute("SELECT * FROM editorial_schedule WHERE id=1").fetchone()
            counts = dict(conn.execute("SELECT status, count(*) FROM briefs GROUP BY status").fetchall())
        return {
            "drafts": [dict(row) for row in drafts],
            "briefs": [brief_dict(row) for row in briefs],
            "exports": [dict(row) for row in exports],
            "schedule": dict(schedule), "counts": counts,
            "csrf_token": csrf_token(settings.admin_token, cookie),
            "today": datetime.now(UTC).date().isoformat(), **extra,
        }

    @app.get("/steckbriefe", response_class=HTMLResponse)
    def brief_index(page: Annotated[int, Query(ge=1, le=10000)] = 1):
        with connection(settings.db_path) as conn:
            count = conn.execute("SELECT count(*) FROM briefs WHERE status='published'").fetchone()[0]
            pages = max(1, (count + 23) // 24)
            page = min(page, pages)
            rows = conn.execute(
                "SELECT * FROM briefs WHERE status='published' ORDER BY published_at DESC, id DESC LIMIT 24 OFFSET ?",
                ((page - 1) * 24,),
            ).fetchall()
        return render(
            "brief_index.html", briefs=[brief_dict(row) for row in rows], page=page, pages=pages,
            canonical_url=settings.site_url + "/steckbriefe" + (f"?page={page}" if page > 1 else ""),
        )

    @app.get("/steckbrief/{brief_id}/{slug}", response_class=HTMLResponse)
    def brief_detail(brief_id: int, slug: str):
        with connection(settings.db_path) as conn:
            row = conn.execute("SELECT * FROM briefs WHERE id=? AND status='published'", (brief_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Steckbrief nicht gefunden.")
        brief = brief_dict(row)
        if slug != slugify(brief["title"]):
            return RedirectResponse(brief["path"], status_code=301)
        return render(
            "brief.html", brief=brief, canonical_url=settings.site_url + brief["path"],
            image_url=f"{settings.site_url}/steckbrief-bild/{brief_id}.png",
        )

    @app.get("/steckbrief-bild/{brief_id}.png")
    def brief_image(brief_id: int):
        with connection(settings.db_path) as conn:
            row = conn.execute("SELECT * FROM briefs WHERE id=? AND status='published'", (brief_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Steckbrief nicht gefunden.")
        brief = brief_dict(row)
        return Response(
            render_card(brief["title"], brief["category"], brief["source_display"]),
            media_type="image/png", headers={"Cache-Control": "public, max-age=3600"},
        )

    @app.get("/admin/redaktion", response_class=HTMLResponse)
    def editorial_dashboard(request: Request, deal_id: int | None = None):
        data = context(request)
        selected = None
        if deal_id is not None:
            with connection(settings.db_path) as conn:
                row = conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
            if row:
                selected = {
                    "title": row["title"], "category": row["category"],
                    "source_url": row["source_url"] or row["affiliate_link"],
                    "source_name": row["source_name"] or row["shop_name"],
                    "source_deal_id": row["id"], "facts": "", "source_at": "",
                }
        return render("editorial.html", **data, selected=selected)

    @app.post("/admin/redaktion/schedule")
    def update_schedule(
        request: Request, csrf: Annotated[str, Form()],
        interval_hours: Annotated[int, Form()], enabled: Annotated[str, Form()] = "no",
    ):
        verify_csrf(request, settings, csrf)
        try:
            configure_schedule(settings.db_path, enabled == "yes", interval_hours)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return RedirectResponse("/admin/redaktion", 303)

    @app.post("/admin/redaktion/save")
    def create_or_update_brief(
        request: Request, csrf: Annotated[str, Form()], title: Annotated[str, Form()],
        category: Annotated[str, Form()], source_url: Annotated[str, Form()],
        source_name: Annotated[str, Form()], source_at: Annotated[str, Form()],
        approved: Annotated[str, Form()], mode: Annotated[str, Form()] = "queue",
        facts: Annotated[str, Form()] = "", source_deal_id: Annotated[int | None, Form()] = None,
        brief_id: Annotated[int | None, Form()] = None,
    ):
        verify_csrf(request, settings, csrf)
        if approved != "yes":
            raise HTTPException(422, "Inhalte und Nutzungsrechte müssen bestätigt werden.")
        if source_deal_id is not None:
            with connection(settings.db_path) as conn:
                if not conn.execute("SELECT 1 FROM deals WHERE id=?", (source_deal_id,)).fetchone():
                    raise HTTPException(404, "Ursprungsentwurf nicht gefunden.")
        try:
            save_brief(
                settings.db_path, title=title, category=category, facts=facts,
                source_url=source_url, source_name=source_name, source_at=source_at,
                mode=mode, site_url=settings.site_url, source_deal_id=source_deal_id,
                brief_id=brief_id,
            )
        except ValueError as exc:
            return HTMLResponse(render("editorial.html", **context(request, error=str(exc))).body, 422)
        return RedirectResponse("/admin/redaktion", 303)

    @app.post("/admin/redaktion/batch")
    def queue_imports(
        request: Request, csrf: Annotated[str, Form()], selected: Annotated[list[int], Form()],
        source_at: Annotated[str, Form()], approved: Annotated[str, Form()],
    ):
        verify_csrf(request, settings, csrf)
        if approved != "yes" or len(selected) > 100:
            raise HTTPException(422, "Auswahl und Rechte bestätigen; maximal 100 Einträge.")
        try:
            parse_date(source_at)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        count, skipped = 0, 0
        for deal_id in dict.fromkeys(selected):
            with connection(settings.db_path) as conn:
                row = conn.execute("SELECT * FROM deals WHERE id=? AND status='draft'", (deal_id,)).fetchone()
            if not row:
                skipped += 1
                continue
            try:
                save_brief(
                    settings.db_path, title=row["title"], category=row["category"], facts="",
                    source_url=row["source_url"] or row["affiliate_link"],
                    source_name=row["source_name"] or row["shop_name"] or "Redaktionelle Quelle",
                    source_at=source_at, mode="queue", site_url=settings.site_url, source_deal_id=deal_id,
                )
                count += 1
            except ValueError:
                skipped += 1
        return render(
            "editorial.html", **context(request, message=f"{count} Steckbriefe vorgemerkt; {skipped} übersprungen (Duplikat, unvollständige oder alte Quelle).")
        )

    @app.post("/admin/redaktion/{brief_id}/pause")
    def pause_brief(request: Request, brief_id: int, csrf: Annotated[str, Form()]):
        verify_csrf(request, settings, csrf)
        with connection(settings.db_path) as conn:
            conn.execute("UPDATE briefs SET status='draft' WHERE id=?", (brief_id,))
        return RedirectResponse("/admin/redaktion", 303)

    @app.get("/admin/social/{export_id}/download")
    def download_social(request: Request, export_id: int):
        session_cookie(request, settings)
        with connection(settings.db_path) as conn:
            row = conn.execute(
                """SELECT social_exports.*, briefs.title, briefs.category, briefs.source_at,
                   briefs.status AS brief_status FROM social_exports JOIN briefs ON briefs.id=brief_id
                   WHERE social_exports.id=?""", (export_id,),
            ).fetchone()
        if not row or row["brief_status"] != "published":
            raise HTTPException(404, "Kein veröffentlichtes Social-Paket.")
        payload = BytesIO()
        stamp = parse_date(row["source_at"]).strftime("%d.%m.%Y")
        with ZipFile(payload, "w", ZIP_DEFLATED) as archive:
            archive.writestr("beitrag.txt", row["caption"])
            archive.writestr("grafik.png", render_card(row["title"], row["category"], stamp, row["platform"] == "tiktok"))
            archive.writestr(
                "HINWEIS.txt",
                "Noch NICHT gepostet. Grafik und Text manuell in der Plattform hochladen.\n"
                "TikTok: Fotobeitrag, kein erzeugtes Video. Instagram: Beitragslinks sind nicht anklickbar; Profil-Link selbst setzen.\n"
                "Prüfe vor dem Posten Aktualität, Text, Bild, Zielkonto sowie ggf. Werbekennzeichnung.\n"
                "Die Grafik ist eine eigene Textkarte und kein Produktfoto.\n",
            )
        return Response(
            payload.getvalue(), media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="nettodeals-{row["brief_id"]}-{row["platform"]}.zip"'},
        )

    @app.post("/admin/social/{export_id}/shared")
    def mark_shared(request: Request, export_id: int, csrf: Annotated[str, Form()]):
        verify_csrf(request, settings, csrf)
        with connection(settings.db_path) as conn:
            conn.execute(
                "UPDATE social_exports SET status='manually_shared', shared_at=? WHERE id=?",
                (datetime.now(UTC).isoformat(), export_id),
            )
        return RedirectResponse("/admin/redaktion#social", 303)
