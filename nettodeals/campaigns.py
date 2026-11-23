"""Admin CRUD and public listing for homepage campaigns."""
from fastapi import Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from typing import Annotated
from .db import connection, now_iso
from .security import normalize_external_url
from .merchant import fetch_public, parse_product
from .services import DealCandidate, source_id


def list_campaigns(db_path, active_only=False):
    with connection(db_path) as conn:
        query = "SELECT * FROM campaigns"
        if active_only:
            query += " WHERE active=1 AND (ends_at='' OR datetime(ends_at) > datetime('now'))"
        query += " ORDER BY sort_order ASC, id ASC"
        return [dict(row) for row in conn.execute(query).fetchall()]


def register_campaign_routes(app, settings, render, session_cookie, verify_csrf):
    @app.post("/admin/merchant/import")
    def import_affiliate_link(request: Request, csrf: Annotated[str, Form()], url: Annotated[str, Form()]):
        verify_csrf(request, settings, csrf)
        safe = normalize_external_url(url)
        if not safe:
            raise HTTPException(422, "Bitte einen gültigen öffentlichen HTTPS-Affiliate-Link eingeben.")
        data, final_url = fetch_public(safe)
        parsed = parse_product(data, final_url)
        title = parsed.get("title", "").strip()
        if not title or title == "Händlerangebot prüfen":
            raise HTTPException(422, "Kein eindeutiger Produktname erkannt. Bitte Produktdaten manuell erfassen.")
        candidate = DealCandidate(
            title=title, category="Deals", base_price=parsed.get("base_price", 0),
            shop_name=parsed.get("shop_name", "Unbekannter Händler"),
            affiliate_link=safe, source="manual", source_id=source_id("manual", title, safe),
            description=parsed.get("description", ""), image_url=parsed.get("image_url", ""),
            image_source=final_url, source_url=final_url, link_type="affiliate",
            enrichment_notes=parsed.get("notes", ""), price_type="exact",
        )
        upsert_deal(settings.db_path, candidate.values(status="draft"))
        with connection(settings.db_path) as conn:
            row=conn.execute("SELECT id FROM deals WHERE source='manual' AND source_id=?",(candidate.source_id,)).fetchone()
        if not row:
            raise HTTPException(500,"Deal konnte nicht angelegt werden.")
        return RedirectResponse(f"/admin/deals/{row['id']}/ai",303)

    @app.post("/admin/campaigns/save")
    def save_campaign(request: Request, csrf: Annotated[str, Form()],
                      brand: Annotated[str, Form()] = "",
                      title: Annotated[str, Form()] = "",
                      subtitle: Annotated[str, Form()] = "",
                      detail: Annotated[str, Form()] = "",
                      affiliate_url: Annotated[str, Form()] = "",
                      starts_at: Annotated[str, Form()] = "",
                      ends_at: Annotated[str, Form()] = "",
                      active: Annotated[str, Form()] = "no",
                      sort_order: Annotated[int, Form()] = 10,
                      campaign_id: Annotated[int | None, Form()] = None):
        verify_csrf(request, settings, csrf)
        safe = normalize_external_url(affiliate_url)
        if not title.strip() or not subtitle.strip() or not safe:
            raise HTTPException(422, "Titel, Kurztext und gültiger HTTPS-Affiliate-Link sind erforderlich.")
        for value in (starts_at, ends_at):
            if value and len(value) > 32:
                raise HTTPException(422, "Ungültiges Datum.")
        if starts_at and ends_at and starts_at > ends_at:
            raise HTTPException(422, "Das Enddatum muss nach dem Startdatum liegen.")
        now = now_iso()
        with connection(settings.db_path) as conn:
            if campaign_id:
                if not conn.execute("SELECT id FROM campaigns WHERE id=?", (campaign_id,)).fetchone():
                    raise HTTPException(404, "Kampagne nicht gefunden.")
                conn.execute("""UPDATE campaigns SET brand=?,title=?,subtitle=?,detail=?,affiliate_url=?,starts_at=?,ends_at=?,active=?,sort_order=?,updated_at=? WHERE id=?""",
                    (brand.strip()[:80],title.strip()[:160],subtitle.strip()[:240],detail.strip()[:300],safe,starts_at.strip(),ends_at.strip(),int(active=="yes"),max(0,min(999,sort_order)),now,campaign_id))
            else:
                conn.execute("""INSERT INTO campaigns(brand,title,subtitle,detail,affiliate_url,starts_at,ends_at,active,sort_order,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (brand.strip()[:80],title.strip()[:160],subtitle.strip()[:240],detail.strip()[:300],safe,starts_at.strip(),ends_at.strip(),int(active=="yes"),max(0,min(999,sort_order)),now,now))
        return RedirectResponse("/admin#campaigns",303)

    @app.post("/admin/campaigns/toggle/{campaign_id}")
    def toggle_campaign(request: Request, campaign_id: int, csrf: Annotated[str, Form()]):
        verify_csrf(request, settings, csrf)
        with connection(settings.db_path) as conn:
            row=conn.execute("SELECT active FROM campaigns WHERE id=?",(campaign_id,)).fetchone()
            if not row: raise HTTPException(404,"Kampagne nicht gefunden.")
            conn.execute("UPDATE campaigns SET active=?,updated_at=? WHERE id=?",(0 if row["active"] else 1,now_iso(),campaign_id))
        return RedirectResponse("/admin#campaigns",303)

    @app.post("/admin/campaigns/delete/{campaign_id}")
    def delete_campaign(request: Request, campaign_id: int, csrf: Annotated[str, Form()]):
        verify_csrf(request, settings, csrf)
        with connection(settings.db_path) as conn:
            conn.execute("DELETE FROM campaigns WHERE id=?",(campaign_id,))
        return RedirectResponse("/admin#campaigns",303)
