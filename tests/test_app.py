from __future__ import annotations

from dataclasses import replace

import pytest

from nettodeals.app import create_app
from nettodeals.db import connection, upsert_deal
from nettodeals.security import COOKIE_NAME, csrf_token
from nettodeals.services import DealCandidate
from tests.test_toppreise import snapshot


def login(client, settings):
    response = client.post(
        "/admin/login",
        data={"admin_token": settings.admin_token},
        follow_redirects=False,
    )
    assert response.status_code == 303
    cookie = client.cookies.get(COOKIE_NAME)
    assert cookie
    return csrf_token(settings.admin_token, cookie)


def test_admin_requires_authentication(client):
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"


def test_invalid_admin_login_is_rejected(client):
    response = client.post("/admin/login", data={"admin_token": "wrong"})
    assert response.status_code == 403
    assert "Token ungültig" in response.text


def test_manual_deal_insert_xss_escape_and_click_tracking(client, settings):
    csrf = login(client, settings)
    payload = "<script>globalThis.xss = true</script> Kamera"
    response = client.post(
        "/admin/deals/create",
        data={
            "csrf": csrf,
            "title": payload,
            "shop_name": "Beispiel-Shop",
            "affiliate_link": "http://example.test/product?ref=1",
            "category": "Kameras",
            "base_price": "999.00",
            "coupon_discount": "100.00",
            "payment_bonus": "20.00",
            "coupon_code": "SAVE100",
            "description": payload,
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    home = client.get("/")
    assert home.status_code == 200
    assert payload not in home.text
    assert "&lt;script&gt;" in home.text
    assert "CHF 879.00" in home.text
    assert "cdn.tailwindcss.com" not in home.text
    assert "default-src &#39;self&#39;" not in home.text
    assert "default-src 'self'" in home.headers["content-security-policy"]

    with connection(settings.db_path) as conn:
        deal = conn.execute("SELECT id, affiliate_link, click_count FROM deals").fetchone()
    assert deal["affiliate_link"].startswith("https://")
    outbound = client.get(f"/go/{deal['id']}", follow_redirects=False)
    assert outbound.status_code == 302
    assert outbound.headers["location"].startswith("https://example.test/")
    with connection(settings.db_path) as conn:
        clicks = conn.execute(
            "SELECT click_count FROM deals WHERE id = ?", (deal["id"],)
        ).fetchone()[0]
        recent = conn.execute(
            "SELECT clicks FROM deal_interest_daily WHERE deal_id = ?", (deal["id"],)
        ).fetchone()[0]
    assert clicks == 1
    assert recent == 1


def test_csrf_is_required(client, settings):
    login(client, settings)
    response = client.post("/admin/sync", data={"csrf": "wrong"})
    assert response.status_code == 403


def test_public_status_does_not_disclose_database_path(client, settings):
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert "database" not in body
    assert settings.db_path not in response.text
    assert body["automatic_sync"] is False


def test_health_is_generic(client):
    assert client.get("/health").json() == {"status": "healthy", "database": "connected"}


def test_home_links_official_social_channels_safely(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="https://x.com/nettodeals"' in response.text
    assert 'href="https://www.instagram.com/nettodeals.ch/"' in response.text
    assert 'href="https://www.tiktok.com/@nettodealsschweiz?lang=de-DE"' in response.text
    assert response.text.count('rel="me noopener noreferrer"') == 3
    assert response.text.count('target="_blank"') == 3


def test_home_paginates_results(client, settings):
    for index in range(25):
        deal = DealCandidate(
            title=f"Deal {index:02d}",
            category="Elektronik",
            base_price=100 + index,
            shop_name="Shop",
            affiliate_link=f"https://example.test/{index}",
            source="manual",
            source_id=f"pagination-{index}",
        )
        upsert_deal(settings.db_path, deal.values(status="published"))

    first_page = client.get("/")
    assert first_page.text.count('class="deal-card"') == 24
    assert "Seite 1 von 2" in first_page.text
    assert 'rel="next"' in first_page.text

    second_page = client.get("/?page=2")
    assert second_page.text.count('class="deal-card"') == 1
    assert "Seite 2 von 2" in second_page.text
    assert 'rel="prev"' in second_page.text


def test_short_admin_secret_is_rejected(settings):
    with pytest.raises(ValueError, match="at least 32"):
        create_app(replace(settings, admin_token="too-short"))


def test_admin_imports_toppreise_snapshots_as_unique_drafts(client, settings):
    csrf = login(client, settings)
    top100 = snapshot(
        *((str(index), f"Produkt {index}", "99.90", "Elektronik") for index in range(1, 51))
    )
    new48 = snapshot(
        *((str(index), f"Produkt {index}", "99.90", "Elektronik") for index in range(46, 56)),
        period=48,
    )
    response = client.post(
        "/admin/toppreise/import",
        data={"csrf": csrf, "confirm_48": "yes"},
        files={
            "top100_file": ("top100.html", top100, "text/html"),
            "new48_file": ("new48.html", new48, "text/html"),
        },
    )

    assert response.status_code == 200
    assert "55 eindeutige Produkte übernommen" in response.text
    with connection(settings.db_path) as conn:
        deals = conn.execute(
            "SELECT source_id, status, link_type FROM deals ORDER BY source_id"
        ).fetchall()
    assert len(deals) == 55
    assert all(row["status"] == "draft" for row in deals)
    assert all(row["link_type"] == "editorial" for row in deals)


def test_editorial_deal_is_disclosed_without_sponsored_rel(client, settings):
    candidate = DealCandidate(
        title="Redaktionelles Produkt",
        category="Produkte",
        base_price=50,
        shop_name="Toppreise.ch",
        affiliate_link="https://www.toppreise.ch/preisvergleich/Produkt/test-p1",
        source="toppreise",
        source_id="1",
        link_type="editorial",
    )
    upsert_deal(settings.db_path, candidate.values(status="published"))

    response = client.get("/")
    assert "Zum Preisvergleich" in response.text
    assert "NettoDeals erhält keine Provision" in response.text
    assert 'rel="nofollow sponsored"' not in response.text


def test_product_detail_has_canonical_metadata_and_redirects_slug(client, settings):
    candidate = DealCandidate(
        title="Kamera für die Schweiz",
        category="Kameras",
        base_price=799,
        shop_name="Preisvergleich",
        affiliate_link="https://www.toppreise.ch/preisvergleich/Kameras/test-p7",
        source="toppreise",
        source_id="7",
        source_name="Toppreise.ch",
        link_type="editorial",
        price_type="from",
    )
    upsert_deal(settings.db_path, candidate.values(status="published"))
    with connection(settings.db_path) as conn:
        deal_id = conn.execute("SELECT id FROM deals").fetchone()[0]

    wrong = client.get(f"/deal/{deal_id}/falsch", follow_redirects=False)
    assert wrong.status_code == 301
    detail = client.get(wrong.headers["location"])
    assert detail.status_code == 200
    assert f'<link rel="canonical" href="{settings.site_url}{wrong.headers["location"]}">' in detail.text
    assert "ab CHF 799.00" in detail.text
    assert "Toppreise.ch" in detail.text


def test_seo_endpoints_and_private_noindex_headers(client, settings):
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert f"Sitemap: {settings.site_url}/sitemap.xml" in robots.text
    assert "Disallow: /admin" in robots.text

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert f"{settings.site_url}/ueber-nettodeals" in sitemap.text
    assert sitemap.headers["content-type"].startswith("application/xml")

    assert client.get("/favicon.ico").status_code == 200
    admin = client.get("/admin", follow_redirects=False)
    assert admin.headers["x-robots-tag"] == "noindex, nofollow"
    filtered = client.get("/?q=kamera")
    assert '<meta name="robots" content="noindex, follow">' in filtered.text
