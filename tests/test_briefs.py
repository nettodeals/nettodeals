from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from io import BytesIO
from zipfile import ZipFile

import pytest
from PIL import Image

from nettodeals.briefs import configure_schedule, run_schedule, save_brief
from nettodeals.db import connection, init_db, upsert_deal
from nettodeals.services import DealCandidate
from nettodeals.social_cards import render_card
from tests.test_app import login


def entry(settings, **overrides):
    values = dict(
        title="Kamera Alpha 7", category="Kameras", facts="Gewicht laut Hersteller: 500 g.",
        source_url="https://manufacturer.example/alpha7", source_name="Hersteller",
        source_at=datetime.now(UTC).isoformat(), mode="publish", site_url=settings.site_url,
    )
    values.update(overrides)
    return save_brief(settings.db_path, **values)


def test_free_publication_without_any_partner(client, settings):
    brief_id = entry(settings)
    home = client.get("/")
    assert "Kamera Alpha 7" in home.text
    detail = client.get(f"/steckbrief/{brief_id}/wrong")
    assert detail.status_code == 200
    assert "kein bestätigtes Rabattangebot" in detail.text
    assert "Gewicht laut Hersteller: 500 g." in detail.text
    assert "/go/" not in detail.text
    assert "CHF" not in detail.text.split("Vor dem Kauf prüfen")[0]
    assert "/steckbrief/" in client.get("/sitemap.xml").text
    assert "Kamera Alpha 7" not in client.get("/?q=fernseher").text
    assert "Kamera Alpha 7" in client.get("/steckbriefe").text
    with connection(settings.db_path) as conn:
        assert conn.execute("SELECT count(*) FROM social_exports").fetchone()[0] == 3


def test_admin_publication_and_private_export(client, settings):
    assert client.get("/admin/redaktion").status_code == 401
    csrf = login(client, settings)
    assert "Keine Affiliate-Mitgliedschaft" in client.get("/admin/redaktion").text
    response = client.post("/admin/redaktion/save", data={
        "csrf": csrf, "title": "Phone Beispiel", "category": "Smartphones",
        "source_url": "https://manufacturer.example/phone", "source_name": "Hersteller",
        "source_at": datetime.now(UTC).date().isoformat(), "approved": "yes", "mode": "publish",
    })
    assert response.status_code == 200
    assert "Vorbereitet, nicht gepostet" in response.text
    with connection(settings.db_path) as conn:
        export = conn.execute("SELECT * FROM social_exports WHERE platform='tiktok'").fetchone()
    download = client.get(f"/admin/social/{export['id']}/download")
    assert download.status_code == 200
    assert download.headers["cache-control"] == "no-store"
    with ZipFile(BytesIO(download.content)) as archive:
        assert set(archive.namelist()) == {"beitrag.txt", "grafik.png", "HINWEIS.txt"}
        assert "Phone Beispiel" in archive.read("beitrag.txt").decode()
        assert Image.open(BytesIO(archive.read("grafik.png"))).size == (1080, 1920)
    client.cookies.clear()
    assert client.get(f"/admin/social/{export['id']}/download").status_code == 401


def test_scheduler_is_atomic_persistent_and_no_catchup(client, settings):
    now = datetime.now(UTC)
    first = entry(settings, mode="queue", now=now)
    entry(settings, mode="queue", title="Zweites Produkt", now=now)
    assert run_schedule(settings.db_path, settings.site_url, now) is None
    configure_schedule(settings.db_path, True, 12)
    later = now + timedelta(minutes=1)
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(lambda _: run_schedule(settings.db_path, settings.site_url, later), range(4)))
    assert results.count(first) == 1
    init_db(settings.db_path)  # restart migration preserves queue and timer
    assert run_schedule(settings.db_path, settings.site_url, later) is None
    assert run_schedule(settings.db_path, settings.site_url, later + timedelta(hours=30)) is not None
    assert run_schedule(settings.db_path, settings.site_url, later + timedelta(hours=30)) is None
    with connection(settings.db_path) as conn:
        assert conn.execute("SELECT count(*) FROM social_exports").fetchone()[0] == 6


def test_stale_queue_is_skipped_and_published_brief_remains(client, settings):
    now = datetime.now(UTC)
    first = entry(settings, now=now)
    entry(settings, mode="queue", title="Alt", now=now)
    configure_schedule(settings.db_path, True, 12)
    assert run_schedule(settings.db_path, settings.site_url, now + timedelta(days=8)) is None
    with connection(settings.db_path) as conn:
        assert conn.execute("SELECT status FROM briefs WHERE title='Alt'").fetchone()[0] == "stale"
        assert conn.execute("SELECT status FROM briefs WHERE id=?", (first,)).fetchone()[0] == "published"
        assert "Kein frischer" in conn.execute("SELECT last_message FROM editorial_schedule").fetchone()[0]


@pytest.mark.parametrize("overrides", [
    {"source_at": "nicht-ein-datum"}, {"source_at": "2001-01-01"},
    {"source_at": "2099-01-01"}, {"source_url": "javascript:alert(1)"},
    {"title": ""}, {"mode": "surprise"},
])
def test_invalid_input_rejected(client, settings, overrides):
    with pytest.raises(ValueError):
        entry(settings, **overrides)


def test_repeat_publication_does_not_create_duplicates(client, settings):
    entry(settings)
    with pytest.raises(ValueError, match="bereits veröffentlicht"):
        entry(settings)
    with connection(settings.db_path) as conn:
        assert conn.execute("SELECT count(*) FROM briefs").fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM social_exports").fetchone()[0] == 3


def test_edit_keeps_queue_identity_and_historical_label(client, settings):
    brief_id = entry(settings, mode="queue")
    assert entry(settings, mode="queue", brief_id=brief_id, title="Neuer Titel") == brief_id
    with connection(settings.db_path) as conn:
        assert conn.execute("SELECT count(*) FROM briefs").fetchone()[0] == 1
    entry(settings, brief_id=brief_id, title="Neuer Titel")
    with connection(settings.db_path) as conn:
        conn.execute("UPDATE briefs SET source_at='2001-01-01T00:00:00+00:00' WHERE id=?", (brief_id,))
    assert "Historischer Steckbrief" in client.get(f"/steckbrief/{brief_id}/x").text


def test_preview_pagination_and_shared_status(client, settings):
    csrf = login(client, settings)
    for index in range(25):
        entry(settings, title=f"Produkt {index}")
    assert "Seite 1 von 2" in client.get("/steckbriefe").text
    assert "Seite 2 von 2" in client.get("/steckbriefe?page=2").text
    response = client.post("/admin/social/1/shared", data={"csrf": csrf})
    assert response.status_code == 200
    assert "Manuell als geteilt markiert" in response.text


def test_csrf_required_on_all_editorial_mutations(client, settings):
    login(client, settings)
    response = client.post("/admin/redaktion/schedule", data={"csrf": "bad", "interval_hours": "12"})
    assert response.status_code == 403
    assert client.post("/admin/redaktion/1/pause", data={"csrf": "bad"}).status_code == 403
    assert client.post("/admin/social/1/shared", data={"csrf": "bad"}).status_code == 403


def test_import_draft_can_be_published_as_brief_and_never_as_fake_deal(client, settings):
    candidate = DealCandidate(
        title="Produkt Test 42", category="Produkte", base_price=1.99, shop_name="Preisvergleich",
        affiliate_link="https://www.toppreise.ch/preisvergleich/test-p42", source="toppreise",
        source_id="42", source_url="https://www.toppreise.ch/preisvergleich/test-p42",
    )
    upsert_deal(settings.db_path, candidate.values())
    csrf = login(client, settings)
    with connection(settings.db_path) as conn:
        deal_id = conn.execute("SELECT id FROM deals").fetchone()[0]
    assert "Produkt Test 42" in client.get(f"/admin/redaktion?deal_id={deal_id}").text
    response = client.post("/admin/redaktion/batch", data={
        "csrf": csrf, "selected": [str(deal_id)], "approved": "yes",
        "source_at": datetime.now(UTC).date().isoformat(),
    })
    assert response.status_code == 200
    assert "1 Steckbriefe vorgemerkt" in response.text
    configure_schedule(settings.db_path, True, 12)
    brief_id = run_schedule(settings.db_path, settings.site_url, datetime.now(UTC) + timedelta(seconds=1))
    assert brief_id
    page = client.get(f"/steckbrief/{brief_id}/x")
    assert "1.99" not in page.text
    assert "Preisvergleich" in page.text
    assert client.get("/go/1").status_code == 404


def test_unpublish_and_escape(client, settings):
    brief_id = entry(settings, title='<script>alert("x")</script>')
    csrf = login(client, settings)
    assert '<script>alert("x")</script>' not in client.get(f"/steckbrief/{brief_id}/x").text
    assert client.get(f"/steckbrief-bild/{brief_id}.png").status_code == 200
    assert client.get("/steckbrief-bild/999.png").status_code == 404
    client.post(f"/admin/redaktion/{brief_id}/pause", data={"csrf": csrf})
    assert client.get(f"/steckbrief/{brief_id}/x").status_code == 404
    assert client.get(f"/steckbrief-bild/{brief_id}.png").status_code == 404
    assert client.get("/admin/social/1/download").status_code == 404


def test_cards_and_caption_bounds(client, settings):
    entry(settings, title="長" * 300, facts="A" * 1600, source_name="B" * 120)
    with connection(settings.db_path) as conn:
        rows = conn.execute("SELECT platform,caption FROM social_exports").fetchall()
    for row in rows:
        if row["platform"] != "x":
            assert len(row["caption"]) <= 2200
    assert Image.open(BytesIO(render_card("Titel" * 60, "Kategorie" * 8, "18.09.2026"))).size == (1080, 1350)


def test_pause_schedule_and_invalid_interval(client, settings):
    entry(settings, mode="queue")
    configure_schedule(settings.db_path, True, 12)
    configure_schedule(settings.db_path, False, 12)
    assert run_schedule(settings.db_path, settings.site_url) is None
    with pytest.raises(ValueError):
        configure_schedule(settings.db_path, True, 0)


def test_published_brief_survives_source_reimport_and_migration(client, settings):
    candidate = DealCandidate(
        title="Signal", category="Produkte", base_price=100, shop_name="Preisvergleich",
        affiliate_link="https://www.toppreise.ch/preisvergleich/signal-p9", source="toppreise", source_id="9",
    )
    upsert_deal(settings.db_path, candidate.values())
    brief_id = entry(settings, source_deal_id=1)
    upsert_deal(settings.db_path, candidate.values())
    init_db(settings.db_path)
    with connection(settings.db_path) as conn:
        assert conn.execute("SELECT status FROM briefs WHERE id=?", (brief_id,)).fetchone()[0] == "published"
        assert conn.execute("SELECT count(*) FROM social_exports").fetchone()[0] == 3
