"""FastAPI application factory and HTTP routes."""

from __future__ import annotations

import asyncio
import sqlite3
from contextlib import asynccontextmanager, suppress
from html import escape
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import Settings
from .db import connection, init_db, log_import, now_iso, upsert_deal
from .security import (
    COOKIE_NAME,
    clear_login_failures,
    constant_time_equal,
    create_admin_session,
    csrf_token,
    login_is_rate_limited,
    normalize_external_url,
    record_login_failure,
    valid_admin_session,
    valid_csrf,
)
from .seo import deal_path, display_datetime, slugify
from .services import DealCandidate, SyncService, safe_money, source_id
from .toppreise import (
    MAX_SNAPSHOT_BYTES,
    MIN_NEW48_ITEMS,
    MIN_TOP100_ITEMS,
    SnapshotError,
    parse_snapshot,
)
from .trends import trend_cache_age_seconds

PACKAGE_DIR = Path(__file__).resolve().parent

HOME_PAGE_QUERY = """
    SELECT deals.*,
           COALESCE((
               SELECT SUM(clicks) FROM deal_interest_daily
               WHERE deal_id = deals.id AND day >= date('now', '-13 days')
           ), 0) AS recent_interest,
           (trend_score + MIN(COALESCE((
               SELECT SUM(clicks) FROM deal_interest_daily
               WHERE deal_id = deals.id AND day >= date('now', '-13 days')
           ), 0), 50) * 2.0) AS demand_score
    FROM deals
    WHERE status = 'published' AND affiliate_link != ''
      AND (? = '' OR title LIKE ? OR shop_name LIKE ? OR description LIKE ?)
      AND (? = '' OR category = ?)
    ORDER BY demand_score DESC, updated_at DESC, effective_price ASC
    LIMIT ? OFFSET ?
"""
HOME_COUNT_QUERY = """
    SELECT COUNT(*) FROM deals
    WHERE status = 'published' AND affiliate_link != ''
      AND (? = '' OR title LIKE ? OR shop_name LIKE ? OR description LIKE ?)
      AND (? = '' OR category = ?)
"""
PAGE_SIZE = 24
TEMPLATE_ENV = Environment(
    loader=FileSystemLoader(PACKAGE_DIR / "templates"),
    autoescape=select_autoescape(("html", "xml"), default_for_string=True),
    enable_async=False,
)


def _render(name: str, **context: Any) -> HTMLResponse:
    return HTMLResponse(TEMPLATE_ENV.get_template(name).render(**context))


def _deal_dict(row: sqlite3.Row) -> dict[str, Any]:
    deal = dict(row)
    deal["savings"] = round(max(0.0, deal["base_price"] - deal["effective_price"]), 2)
    deal["path"] = deal_path(deal["id"], deal["title"])
    deal["checked_display"] = display_datetime(
        deal.get("price_checked_at") or deal.get("updated_at")
    )
    deal["display_source"] = deal.get("source_name") or deal.get("shop_name")
    return deal


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _session_cookie(request: Request, settings: Settings) -> str:
    cookie = request.cookies.get(COOKIE_NAME)
    if not valid_admin_session(settings.admin_token, cookie):
        raise HTTPException(status_code=401, detail="Admin-Anmeldung erforderlich.")
    return cookie or ""


def _verify_csrf(request: Request, settings: Settings, submitted: str) -> str:
    cookie = _session_cookie(request, settings)
    if not valid_csrf(settings.admin_token, cookie, submitted):
        raise HTTPException(status_code=403, detail="Ungültiges CSRF-Token.")
    return cookie


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    if settings.admin_token and len(settings.admin_token) < 32:
        raise ValueError("ADMIN_TOKEN must contain at least 32 characters")
    sync_service = SyncService(settings)

    async def auto_sync_loop() -> None:
        if settings.auto_sync_on_start:
            await asyncio.sleep(settings.auto_sync_initial_delay)
        else:
            await asyncio.sleep(settings.auto_sync_interval)
        while True:
            await asyncio.to_thread(sync_service.sync_all)
            await asyncio.sleep(settings.auto_sync_interval)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        init_db(settings.db_path)
        task = asyncio.create_task(auto_sync_loop()) if settings.auto_sync_enabled else None
        yield
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    docs_url = "/docs" if settings.enable_api_docs else None
    app = FastAPI(
        title="NettoDeals",
        version="3.1.1",
        docs_url=docs_url,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.enable_api_docs else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.sync_service = sync_service
    if settings.allowed_hosts != ("*",):
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: https:; style-src 'self'; "
            "script-src 'self'; connect-src 'self'; font-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith(("/admin", "/go/", "/api/", "/health")):
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        if request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "public, max-age=604800"
        elif request.url.path.startswith("/admin"):
            response.headers["Cache-Control"] = "no-store"
        if settings.cookie_secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    @app.get("/", response_class=HTMLResponse)
    def home(
        q: Annotated[str, Query(max_length=100)] = "",
        category: Annotated[str, Query(max_length=80)] = "",
        page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    ):
        query_text = q.strip()
        category_text = category.strip()
        needle = f"%{query_text}%" if query_text else ""
        filter_params: list[Any] = [
            query_text,
            needle,
            needle,
            needle,
            category_text,
            category_text,
        ]
        with connection(settings.db_path) as conn:
            total_matches = int(conn.execute(HOME_COUNT_QUERY, filter_params).fetchone()[0])
            page_count = max(1, (total_matches + PAGE_SIZE - 1) // PAGE_SIZE)
            page = min(page, page_count)
            rows = conn.execute(
                HOME_PAGE_QUERY,
                [*filter_params, PAGE_SIZE, (page - 1) * PAGE_SIZE],
            ).fetchall()
            categories = conn.execute(
                """
                SELECT category, COUNT(*) AS count FROM deals
                WHERE status = 'published' AND affiliate_link != ''
                GROUP BY category ORDER BY count DESC, category ASC LIMIT 12
                """
            ).fetchall()
            totals = conn.execute(
                """
                SELECT COUNT(*) AS deals,
                       COALESCE(SUM(click_count), 0) AS clicks,
                       COALESCE(MAX(updated_at), '') AS updated_at
                FROM deals WHERE status = 'published'
                """
            ).fetchone()
        deals = [_deal_dict(row) for row in rows]
        filtered = bool(query_text or category_text or page > 1)
        return _render(
            "home.html",
            deals=deals,
            categories=[dict(row) for row in categories],
            totals=dict(totals) if totals else {"deals": 0, "clicks": 0, "updated_at": ""},
            q=q.strip(),
            selected_category=category.strip(),
            trend_age=trend_cache_age_seconds(settings.db_path),
            page=page,
            page_count=page_count,
            total_matches=total_matches,
            canonical_url=f"{settings.site_url}/",
            robots="noindex, follow" if filtered else "index, follow",
            site_url=settings.site_url,
        )

    @app.get("/deal/{deal_id}/{slug}", response_class=HTMLResponse)
    def deal_detail(deal_id: int, slug: str):
        with connection(settings.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM deals WHERE id = ? AND status = 'published'", (deal_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Deal nicht gefunden.")
            canonical_path = deal_path(deal_id, row["title"])
            if slug != slugify(row["title"]):
                return RedirectResponse(canonical_path, status_code=301)
            related_rows = conn.execute(
                """
                SELECT * FROM deals
                WHERE status = 'published' AND category = ? AND id != ?
                ORDER BY trend_score DESC, updated_at DESC LIMIT 3
                """,
                (row["category"], deal_id),
            ).fetchall()
        deal = _deal_dict(row)
        description = deal["description"] or (
            f"{deal['title']} aktuell für die Schweiz vergleichen. Preis und "
            "Verfügbarkeit wurden von NettoDeals transparent dokumentiert."
        )
        return _render(
            "deal.html",
            deal=deal,
            related=[_deal_dict(item) for item in related_rows],
            canonical_url=f"{settings.site_url}{canonical_path}",
            meta_description=description[:155],
            site_url=settings.site_url,
        )

    @app.get("/robots.txt", response_class=PlainTextResponse)
    def robots():
        return PlainTextResponse(
            "User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /go/\n"
            f"Disallow: /api/\nDisallow: /health\n\nSitemap: {settings.site_url}/sitemap.xml\n"
        )

    @app.get("/sitemap.xml")
    def sitemap():
        static_paths = ("/", "/ueber-nettodeals", "/redaktion", "/datenschutz", "/impressum")
        urls = [f"  <url><loc>{escape(settings.site_url + path)}</loc></url>" for path in static_paths]
        with connection(settings.db_path) as conn:
            rows = conn.execute(
                "SELECT id, title, updated_at FROM deals WHERE status = 'published' ORDER BY id"
            ).fetchall()
        for row in rows:
            location = escape(settings.site_url + deal_path(row["id"], row["title"]))
            last_modified = escape(str(row["updated_at"])[:10])
            urls.append(f"  <url><loc>{location}</loc><lastmod>{last_modified}</lastmod></url>")
        body = '<?xml version="1.0" encoding="UTF-8"?>\n'
        body += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        body += "\n".join(urls)
        body += "\n</urlset>\n"
        return Response(content=body, media_type="application/xml")

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon():
        return FileResponse(PACKAGE_DIR / "static" / "favicon.svg", media_type="image/svg+xml")

    @app.get("/ueber-nettodeals", response_class=HTMLResponse)
    @app.get("/redaktion", response_class=HTMLResponse)
    @app.get("/datenschutz", response_class=HTMLResponse)
    @app.get("/impressum", response_class=HTMLResponse)
    def information_page(request: Request):
        page_name = request.url.path.lstrip("/")
        pages = {
            "ueber-nettodeals": ("Über NettoDeals", "So arbeitet der Schweizer Deal-Radar."),
            "redaktion": ("Redaktion & Transparenz", "Auswahl, Preise und Finanzierung erklärt."),
            "datenschutz": ("Datenschutz", "Welche technischen Daten verarbeitet werden."),
            "impressum": ("Impressum", "Anbieterkennzeichnung von NettoDeals.ch."),
        }
        title, description = pages[page_name]
        return _render(
            "info.html",
            page_name=page_name,
            title=title,
            meta_description=description,
            canonical_url=f"{settings.site_url}/{page_name}",
            site_url=settings.site_url,
        )

    @app.get("/go/{deal_id}")
    def outbound(deal_id: int):
        with connection(settings.db_path) as conn:
            row = conn.execute(
                "SELECT affiliate_link FROM deals WHERE id = ? AND status = 'published'",
                (deal_id,),
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Deal nicht gefunden.")
            target = normalize_external_url(row["affiliate_link"])
            if not target:
                raise HTTPException(status_code=410, detail="Deal-Link ist nicht mehr verfügbar.")
            conn.execute(
                "UPDATE deals SET click_count = click_count + 1, last_clicked_at = ? WHERE id = ?",
                (now_iso(), deal_id),
            )
            conn.execute(
                """
                INSERT INTO deal_interest_daily(deal_id, day, clicks)
                VALUES (?, date('now'), 1)
                ON CONFLICT(deal_id, day) DO UPDATE SET clicks = clicks + 1
                """,
                (deal_id,),
            )
            conn.execute("DELETE FROM deal_interest_daily WHERE day < date('now', '-13 days')")
        return RedirectResponse(target, status_code=302)

    @app.get("/health")
    def health():
        try:
            with connection(settings.db_path) as conn:
                conn.execute("SELECT 1").fetchone()
            return {"status": "healthy", "database": "connected"}
        except sqlite3.Error:
            return JSONResponse(
                status_code=503,
                content={"status": "unhealthy", "database": "unavailable"},
            )

    @app.get("/api/status")
    def api_status():
        with connection(settings.db_path) as conn:
            last_sync = conn.execute(
                "SELECT MAX(created_at) AS at FROM import_logs WHERE status = 'success'"
            ).fetchone()
        return {
            "app": "NettoDeals",
            "version": "3.1.1",
            "sources": sync_service.configured_sources(),
            "automatic_sync": settings.auto_sync_enabled,
            "last_successful_sync": last_sync["at"] if last_sync else None,
        }

    @app.get("/admin/login", response_class=HTMLResponse)
    def admin_login_page(request: Request):
        if valid_admin_session(settings.admin_token, request.cookies.get(COOKIE_NAME)):
            return RedirectResponse("/admin", status_code=303)
        return _render(
            "admin_login.html",
            error=None,
            configured=bool(settings.admin_token),
        )

    @app.post("/admin/login", response_class=HTMLResponse)
    def admin_login(request: Request, admin_token: Annotated[str, Form()]):
        client = _client_key(request)
        if login_is_rate_limited(client):
            return _render(
                "admin_login.html",
                error="Zu viele Versuche. Bitte in fünf Minuten erneut versuchen.",
                configured=bool(settings.admin_token),
            )
        if not constant_time_equal(admin_token, settings.admin_token):
            record_login_failure(client)
            return HTMLResponse(
                TEMPLATE_ENV.get_template("admin_login.html").render(
                    error="Token ungültig.", configured=bool(settings.admin_token)
                ),
                status_code=403,
            )
        clear_login_failures(client)
        cookie = create_admin_session(settings.admin_token, settings.admin_session_seconds)
        response = RedirectResponse("/admin", status_code=303)
        response.set_cookie(
            COOKIE_NAME,
            cookie,
            max_age=settings.admin_session_seconds,
            httponly=True,
            secure=settings.cookie_secure,
            samesite="strict",
            path="/admin",
        )
        return response

    def admin_context(request: Request, **extra: Any) -> dict[str, Any]:
        cookie = _session_cookie(request, settings)
        with connection(settings.db_path) as conn:
            drafts = conn.execute(
                "SELECT * FROM deals WHERE status = 'draft' ORDER BY updated_at DESC LIMIT 500"
            ).fetchall()
            logs = conn.execute("SELECT * FROM import_logs ORDER BY id DESC LIMIT 25").fetchall()
            counts = conn.execute(
                "SELECT status, COUNT(*) AS count FROM deals GROUP BY status"
            ).fetchall()
        return {
            "drafts": [dict(row) for row in drafts],
            "logs": [dict(row) for row in logs],
            "counts": {row["status"]: row["count"] for row in counts},
            "sources": sync_service.configured_sources(),
            "csrf_token": csrf_token(settings.admin_token, cookie),
            **extra,
        }

    @app.get("/admin", response_class=HTMLResponse)
    def admin_page(request: Request):
        if not valid_admin_session(settings.admin_token, request.cookies.get(COOKIE_NAME)):
            return RedirectResponse("/admin/login", status_code=303)
        return _render("admin.html", **admin_context(request, result=None, error=None))

    @app.post("/admin/sync", response_class=HTMLResponse)
    async def admin_sync(request: Request, csrf: Annotated[str, Form()]):
        _verify_csrf(request, settings, csrf)
        result = await asyncio.to_thread(sync_service.sync_all)
        return _render("admin.html", **admin_context(request, result=result, error=None))

    @app.post("/admin/toppreise/import", response_class=HTMLResponse)
    async def import_toppreise_snapshots(
        request: Request,
        csrf: Annotated[str, Form()],
        top100_file: Annotated[UploadFile, File()],
        new48_file: Annotated[UploadFile, File()],
        confirm_48: Annotated[str, Form()],
    ):
        _verify_csrf(request, settings, csrf)
        if confirm_48 != "yes":
            raise HTTPException(status_code=422, detail="48-Stunden-Auswahl nicht bestätigt.")
        try:
            uploads = []
            for upload, collection, label in (
                (top100_file, "top100", "Top 100"),
                (new48_file, "new48", "Neue Toppreise (48 Stunden)"),
            ):
                raw = await upload.read(MAX_SNAPSHOT_BYTES + 1)
                if len(raw) > MAX_SNAPSHOT_BYTES:
                    raise SnapshotError(f"Die Datei «{label}» ist grösser als 5 MB.")
                if not raw:
                    raise SnapshotError(f"Die Datei «{label}» ist leer.")
                minimum_items = MIN_TOP100_ITEMS if collection == "top100" else MIN_NEW48_ITEMS
                parsed = parse_snapshot(
                    raw.decode("utf-8", errors="replace"),
                    collection=collection,
                    minimum_items=minimum_items,
                )
                uploads.append((label, parsed))
        except SnapshotError as exc:
            return HTMLResponse(
                TEMPLATE_ENV.get_template("admin.html").render(
                    **admin_context(request, result=None, error=str(exc))
                ),
                status_code=422,
            )
        finally:
            await top100_file.close()
            await new48_file.close()

        unique_products: dict[str, DealCandidate] = {}
        changes = {"created": 0, "updated": 0, "unchanged": 0}
        for label, parsed in uploads:
            for candidate in parsed.candidates:
                unique_products[candidate.source_id] = candidate
            log_import(
                settings.db_path,
                "toppreise",
                "success",
                f"{label}: {len(parsed.candidates)} erkannt, {parsed.skipped} übersprungen",
                len(parsed.candidates),
            )
        for candidate in unique_products.values():
            outcome = upsert_deal(settings.db_path, candidate.values(status="draft"))
            changes[outcome] += 1
        message = (
            f"{len(unique_products)} eindeutige Produkte übernommen: "
            f"{changes['created']} neu, {changes['updated']} aktualisiert, "
            f"{changes['unchanged']} unverändert. Neue und geänderte Einträge müssen geprüft werden."
        )
        return _render(
            "admin.html",
            **admin_context(request, result=None, error=None, import_result=message),
        )

    @app.post("/admin/logout")
    def admin_logout(request: Request, csrf: Annotated[str, Form()]):
        _verify_csrf(request, settings, csrf)
        response = RedirectResponse("/admin/login", status_code=303)
        response.delete_cookie(COOKIE_NAME, path="/admin")
        return response

    @app.post("/admin/deals/{deal_id}/publish")
    def publish_deal(request: Request, deal_id: int, csrf: Annotated[str, Form()]):
        _verify_csrf(request, settings, csrf)
        with connection(settings.db_path) as conn:
            row = conn.execute(
                "SELECT affiliate_link FROM deals WHERE id = ?", (deal_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Deal nicht gefunden.")
            if not normalize_external_url(row["affiliate_link"]):
                raise HTTPException(
                    status_code=422, detail="Ein sicherer HTTPS-Link ist erforderlich."
                )
            conn.execute(
                "UPDATE deals SET status = 'published', updated_at = ? WHERE id = ?",
                (now_iso(), deal_id),
            )
        return RedirectResponse("/admin", status_code=303)

    @app.post("/admin/deals/{deal_id}/delete")
    def delete_deal(request: Request, deal_id: int, csrf: Annotated[str, Form()]):
        _verify_csrf(request, settings, csrf)
        with connection(settings.db_path) as conn:
            conn.execute("DELETE FROM deals WHERE id = ?", (deal_id,))
        return RedirectResponse("/admin", status_code=303)

    @app.post("/admin/deals/create", response_class=HTMLResponse)
    def create_manual_deal(
        request: Request,
        csrf: Annotated[str, Form()],
        title: Annotated[str, Form()],
        shop_name: Annotated[str, Form()],
        affiliate_link: Annotated[str, Form()],
        link_type: Annotated[str, Form()] = "affiliate",
        category: Annotated[str, Form()] = "Deals",
        base_price: Annotated[float, Form()] = 0.0,
        coupon_discount: Annotated[float, Form()] = 0.0,
        payment_bonus: Annotated[float, Form()] = 0.0,
        coupon_code: Annotated[str, Form()] = "",
        description: Annotated[str, Form()] = "",
    ):
        _verify_csrf(request, settings, csrf)
        safe_link = normalize_external_url(affiliate_link)
        if not title.strip() or not shop_name.strip() or not safe_link:
            return HTMLResponse(
                TEMPLATE_ENV.get_template("admin.html").render(
                    **admin_context(
                        request,
                        result=None,
                        error="Titel, Shop und ein gültiger HTTPS-Link sind erforderlich.",
                    )
                ),
                status_code=422,
            )
        candidate = DealCandidate(
            title=title,
            category=category,
            base_price=safe_money(base_price),
            coupon_discount=safe_money(coupon_discount),
            payment_bonus=safe_money(payment_bonus),
            shop_name=shop_name,
            affiliate_link=safe_link,
            coupon_code=coupon_code,
            description=description,
            source="manual",
            source_id=source_id("manual", title, safe_link),
            link_type=link_type,
        )
        upsert_deal(settings.db_path, candidate.values(status="published"))
        return RedirectResponse("/", status_code=303)

    return app


app = create_app()
