from __future__ import annotations

from nettodeals.db import archive_unseen, connection, init_db, upsert_deal
from nettodeals.services import DealCandidate


def candidate(description="first"):
    return DealCandidate(
        title="Phone 1",
        category="Smartphones",
        base_price=800,
        shop_name="Shop",
        affiliate_link="https://example.test/phone",
        description=description,
        source="awin",
        source_id="awin-1",
    ).values()


def test_insert_and_external_change_returns_published_deal_to_draft(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    assert upsert_deal(db_path, candidate()) == "created"
    with connection(db_path) as conn:
        conn.execute("UPDATE deals SET status = 'published' WHERE source_id = 'awin-1'")
    assert upsert_deal(db_path, candidate("changed")) == "updated"
    with connection(db_path) as conn:
        row = conn.execute("SELECT status, description FROM deals").fetchone()
    assert row["status"] == "draft"
    assert row["description"] == "changed"


def test_archive_unseen(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    upsert_deal(db_path, candidate())
    assert archive_unseen(db_path, "awin", "9999-01-01T00:00:00+00:00") == 1
    with connection(db_path) as conn:
        assert conn.execute("SELECT status FROM deals").fetchone()[0] == "archived"


def test_unchanged_import_preserves_content_update_time(tmp_path):
    db_path = str(tmp_path / "test.db")
    init_db(db_path)
    values = candidate()
    upsert_deal(db_path, values)
    with connection(db_path) as conn:
        conn.execute("UPDATE deals SET updated_at = '2026-01-01T00:00:00+00:00'")

    assert upsert_deal(db_path, values) == "unchanged"
    with connection(db_path) as conn:
        row = conn.execute("SELECT updated_at, price_checked_at FROM deals").fetchone()
    assert row["updated_at"] == "2026-01-01T00:00:00+00:00"
    assert row["price_checked_at"]
