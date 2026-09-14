from __future__ import annotations

from dataclasses import replace

import pytest

from nettodeals.app import create_app
from nettodeals.db import connection, upsert_deal
from nettodeals.security import COOKIE_NAME, csrf_token
from nettodeals.services import DealCandidate


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
