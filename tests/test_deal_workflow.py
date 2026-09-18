from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
import requests

from nettodeals.db import connection, init_db, upsert_deal
from nettodeals.deal_schedule import configure, enqueue, tick
from nettodeals.editorial import publish_deal
from nettodeals.services import DealCandidate
from tests.test_app import login


def draft(settings, **changes):
    init_db(settings.db_path)
    candidate = DealCandidate(title="Kamera Aurora X7", category="Kameras", shop_name="Schweizer Shop", affiliate_link="https://shop.example/x7", link_type="editorial", source="manual", source_id="x7", base_price=299, manufacturer_uvp=399, image_url="https://maker.example/x7.png", image_source="Hersteller-Pressebild")
    upsert_deal(settings.db_path, candidate.values())
    with connection(settings.db_path) as conn:
        deal_id = conn.execute("SELECT id FROM deals WHERE source_id='x7'").fetchone()[0]
        conn.execute("UPDATE deals SET uvp_source_url='https://maker.example/x7', image_rights_confirmed=1 WHERE id=?", (deal_id,))
        for key, value in changes.items():
            assert key in {"image_url", "image_rights_confirmed", "uvp_source_url", "manufacturer_uvp", "price_checked_at"}
            conn.execute(f"UPDATE deals SET {key}=? WHERE id=?", (value, deal_id))
    return deal_id


def test_free_deal_price_design_and_optional_youtube(client, settings, monkeypatch):
    def no_requests(*args, **kwargs):
        raise AssertionError("No API needed")
    monkeypatch.setattr("nettodeals.editorial.requests.get", no_requests)
    deal_id = draft(settings)
    publish_deal(settings.db_path, deal_id, settings)
    home = client.get("/").text
    assert "CHF 299.00" in home and "CHF 100.00 günstiger" in home
    assert "−25 %" in home and "<del>CHF 399.00</del>" in home
    assert 'src="https://maker.example/x7.png"' in home
    assert "/steckbriefe" not in home
    assert "Redaktioneller Direktlink" in home
    assert client.get(f"/go/{deal_id}", follow_redirects=False).headers["location"] == "https://shop.example/x7"


@pytest.mark.parametrize("changes,match", [
    ({"image_url": ""}, "Produktbild"),
    ({"image_rights_confirmed": 0}, "Nutzungsrecht"),
    ({"uvp_source_url": ""}, "Herstellerquelle"),
    ({"price_checked_at": (datetime.now(UTC)-timedelta(hours=49)).isoformat()}, "48 Stunden"),
])
def test_publication_requires_facts(settings, changes, match):
    deal_id = draft(settings, **changes)
    with pytest.raises(ValueError, match=match):
        publish_deal(settings.db_path, deal_id, settings)


def test_missing_uvp_is_honest_not_blocking(client, settings):
    deal_id = draft(settings, manufacturer_uvp=0, uvp_source_url="")
    publish_deal(settings.db_path, deal_id, settings)
    home = client.get("/").text
    assert "Keine belegte UVP verfügbar" in home
    assert "discount-pill" not in home


def test_youtube_failure_does_not_block(settings, monkeypatch):
    deal_id = draft(settings)
    def failure(*args, **kwargs):
        raise requests.Timeout()
    monkeypatch.setattr("nettodeals.editorial.requests.get", failure)
    publish_deal(settings.db_path, deal_id, replace(settings, youtube_api_key="test-key"))
    with connection(settings.db_path) as conn:
        row = conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
    assert row["status"] == "published"
    assert "YouTube-Suche vorübergehend" in row["enrichment_notes"]


def test_schedule_concurrent_restart_and_expiry(settings):
    deal_id = draft(settings)
    enqueue(settings.db_path, deal_id)
    configure(settings.db_path, True, 12)
    init_db(settings.db_path)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda _: tick(settings.db_path, settings), range(3)))
    with connection(settings.db_path) as conn:
        row = conn.execute("SELECT * FROM deals WHERE id=?", (deal_id,)).fetchone()
        assert conn.execute("SELECT status FROM deal_queue").fetchone()[0] == "done"
    assert row["status"] == "published"
    assert datetime.fromisoformat(row["expires_at"]) - datetime.fromisoformat(row["published_at"]) == timedelta(hours=48)
    publish_deal(settings.db_path, deal_id, settings)
    with connection(settings.db_path) as conn:
        assert conn.execute("SELECT published_at FROM deals WHERE id=?", (deal_id,)).fetchone()[0] == row["published_at"]


def test_scheduled_stale_price_remains_draft(settings):
    deal_id = draft(settings)
    enqueue(settings.db_path, deal_id)
    configure(settings.db_path, True, 6)
    with connection(settings.db_path) as conn:
        conn.execute("UPDATE deals SET price_checked_at=? WHERE id=?", ((datetime.now(UTC)-timedelta(hours=49)).isoformat(), deal_id))
    tick(settings.db_path, settings)
    with connection(settings.db_path) as conn:
        assert conn.execute("SELECT status FROM deals").fetchone()[0] == "draft"
        assert conn.execute("SELECT status FROM deal_queue").fetchone()[0] == "failed"


def test_admin_queue_csrf_and_update_invalidates_approval(client, settings):
    deal_id = draft(settings)
    assert client.post(f"/admin/deals/{deal_id}/queue", data={"csrf": "bad"}).status_code == 401
    csrf = login(client, settings)
    assert client.post(f"/admin/deals/{deal_id}/queue", data={"csrf": "bad"}).status_code == 403
    assert client.post(f"/admin/deals/{deal_id}/queue", data={"csrf": csrf}).status_code == 200
    response = client.post(f"/admin/deals/{deal_id}/update", data={"csrf": csrf, "shop_name": "Shop", "affiliate_link": "https://shop.example/x7", "base_price": 280, "image_url": "https://maker.example/new.png", "image_source": "Maker", "image_rights_confirmed": "yes"})
    assert response.status_code == 200
    with connection(settings.db_path) as conn:
        assert not conn.execute("SELECT * FROM deal_queue").fetchall()
