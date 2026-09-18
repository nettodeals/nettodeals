from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from nettodeals.db import connection, expire_due_deals, init_db, upsert_deal
from nettodeals.editorial import is_direct_merchant_url, product_similarity, publish_deal
from nettodeals.services import DealCandidate


def test_product_matching_rejects_different_model_numbers():
    assert product_similarity("Apple iPhone 17 Pro 256 GB", "Apple iPhone 17 Pro 256GB") > 0.72
    assert product_similarity("Samsung Galaxy S25", "Samsung Galaxy S24") == 0


def test_toppreise_link_cannot_be_published_without_merchant(client, settings):
    candidate = DealCandidate(
        title="Notebook Pro X15",
        category="Notebooks",
        base_price=999,
        shop_name="Preisvergleich",
        affiliate_link="https://www.toppreise.ch/preisvergleich/notebooks/x15-p1",
        source="toppreise",
        source_id="signal-1",
        source_url="https://www.toppreise.ch/preisvergleich/notebooks/x15-p1",
        link_type="editorial",
    )
    upsert_deal(settings.db_path, candidate.values())
    with connection(settings.db_path) as conn:
        deal_id = conn.execute("SELECT id FROM deals").fetchone()[0]
    with pytest.raises(ValueError, match="Händlerangebot"):
        publish_deal(settings.db_path, deal_id, settings)


def test_partner_offer_enriches_and_expires_toppreise_signal(settings):
    init_db(settings.db_path)
    signal = DealCandidate(
        title="Notebook Pro X15 512GB",
        category="Notebooks",
        base_price=1199,
        shop_name="Preisvergleich",
        affiliate_link="https://www.toppreise.ch/preisvergleich/notebooks/x15-p1",
        source="toppreise",
        source_id="signal-2",
        source_url="https://www.toppreise.ch/preisvergleich/notebooks/x15-p1",
        link_type="editorial",
    )
    offer = DealCandidate(
        title="Notebook Pro X15 512 GB",
        category="Notebooks",
        base_price=899,
        manufacturer_uvp=1099,
        shop_name="Swiss Shop",
        affiliate_link="https://shop.example.test/x15",
        source="tradedoubler_product",
        source_id="offer-2",
        image_url="https://images.example.test/x15.jpg",
        image_source="Swiss Shop feed",
    )
    upsert_deal(settings.db_path, signal.values())
    upsert_deal(settings.db_path, offer.values())
    with connection(settings.db_path) as conn:
        deal_id = conn.execute(
            "SELECT id FROM deals WHERE source = 'toppreise'"
        ).fetchone()[0]
        conn.execute("UPDATE deals SET image_rights_confirmed=1, uvp_source_url='https://maker.example/x15' WHERE id=?", (deal_id,))

    publish_deal(settings.db_path, deal_id, replace(settings, deal_lifetime_hours=48))
    with connection(settings.db_path) as conn:
        deal = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
    assert deal["status"] == "published"
    assert deal["shop_name"] == "Swiss Shop"
    assert deal["affiliate_link"] == "https://shop.example.test/x15"
    assert deal["image_url"].endswith("x15.jpg")
    lifetime = datetime.fromisoformat(deal["expires_at"]) - datetime.fromisoformat(
        deal["published_at"]
    )
    assert timedelta(hours=47, minutes=59) < lifetime <= timedelta(hours=48)

    with connection(settings.db_path) as conn:
        conn.execute(
            "UPDATE deals SET expires_at = ? WHERE id = ?",
            ((datetime.now(UTC) - timedelta(minutes=1)).isoformat(), deal_id),
        )
    assert expire_due_deals(settings.db_path) == 1
    with connection(settings.db_path) as conn:
        assert conn.execute("SELECT status FROM deals WHERE id = ?", (deal_id,)).fetchone()[0] == "expired"


def test_direct_merchant_url_rejects_toppreise():
    assert is_direct_merchant_url("https://shop.example/product")
    assert not is_direct_merchant_url("https://www.toppreise.ch/preisvergleich/product")
