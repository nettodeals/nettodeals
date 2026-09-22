"""SQLite schema, migrations, and deal persistence."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

HASH_FIELDS = (
    "title", "category", "base_price", "coupon_discount", "payment_bonus",
    "effective_price", "shop_name", "affiliate_link", "link_type", "source_name",
    "price_type", "coupon_code", "description", "expires_at", "source_url",
)


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _ensure_parent(db_path: str) -> None:
    parent = os.path.dirname(os.path.abspath(db_path))
    if parent:
        os.makedirs(parent, exist_ok=True)


@contextmanager
def connection(db_path: str) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    _ensure_parent(db_path)
    with connection(db_path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Deals',
                base_price REAL NOT NULL DEFAULT 0,
                coupon_discount REAL NOT NULL DEFAULT 0,
                payment_bonus REAL NOT NULL DEFAULT 0,
                effective_price REAL NOT NULL DEFAULT 0,
                shop_name TEXT NOT NULL,
                affiliate_link TEXT NOT NULL,
                link_type TEXT NOT NULL DEFAULT 'affiliate',
                source_name TEXT NOT NULL DEFAULT '',
                price_type TEXT NOT NULL DEFAULT 'exact',
                price_checked_at TEXT,
                coupon_code TEXT,
                description TEXT,
                source TEXT NOT NULL DEFAULT 'manual',
                source_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT,
                source_url TEXT,
                last_seen_at TEXT,
                content_hash TEXT,
                trend_score REAL NOT NULL DEFAULT 0,
                click_count INTEGER NOT NULL DEFAULT 0,
                last_clicked_at TEXT,
                manufacturer_uvp REAL NOT NULL DEFAULT 0,
                image_url TEXT NOT NULL DEFAULT '',
                image_source TEXT NOT NULL DEFAULT '',
                review_summary TEXT NOT NULL DEFAULT '',
                youtube_reviews TEXT NOT NULL DEFAULT '[]',
                coupon_terms TEXT NOT NULL DEFAULT '',
                coupon_expires_at TEXT,
                published_at TEXT,
                expired_at TEXT,
                enrichment_status TEXT NOT NULL DEFAULT 'pending',
                enrichment_notes TEXT NOT NULL DEFAULT '',
                gtin TEXT NOT NULL DEFAULT '',
                UNIQUE(source, source_id)
            )
            """
        )
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(deals)")}
        migrations = {
            "comparison_price": "REAL NOT NULL DEFAULT 0",
            "comparison_source": "TEXT NOT NULL DEFAULT ''",
            "expires_at": "TEXT",
            "source_url": "TEXT",
            "last_seen_at": "TEXT",
            "content_hash": "TEXT",
            "trend_score": "REAL NOT NULL DEFAULT 0",
            "click_count": "INTEGER NOT NULL DEFAULT 0",
            "last_clicked_at": "TEXT",
            "link_type": "TEXT NOT NULL DEFAULT 'affiliate'",
            "source_name": "TEXT NOT NULL DEFAULT ''",
            "price_type": "TEXT NOT NULL DEFAULT 'exact'",
            "price_checked_at": "TEXT",
            "manufacturer_uvp": "REAL NOT NULL DEFAULT 0",
            "uvp_source_url": "TEXT NOT NULL DEFAULT ''",
            "image_rights_confirmed": "INTEGER NOT NULL DEFAULT 0",
            "image_url": "TEXT NOT NULL DEFAULT ''",
            "image_source": "TEXT NOT NULL DEFAULT ''",
            "review_summary": "TEXT NOT NULL DEFAULT ''",
            "youtube_reviews": "TEXT NOT NULL DEFAULT '[]'",
            "coupon_terms": "TEXT NOT NULL DEFAULT ''",
            "coupon_expires_at": "TEXT",
            "published_at": "TEXT",
            "expired_at": "TEXT",
            "enrichment_status": "TEXT NOT NULL DEFAULT 'pending'",
            "enrichment_notes": "TEXT NOT NULL DEFAULT ''",
            "gtin": "TEXT NOT NULL DEFAULT ''",
        }
        for name, definition in migrations.items():
            if name not in existing:
                conn.execute(f'ALTER TABLE deals ADD COLUMN "{name}" {definition}')

        conn.executescript("""
            CREATE TABLE IF NOT EXISTS studio_packages (
                deal_id INTEGER PRIMARY KEY REFERENCES deals(id) ON DELETE CASCADE,
                fingerprint TEXT NOT NULL, texts TEXT NOT NULL, provider TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '', feed BLOB, story BLOB,
                created_at TEXT NOT NULL, approved INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS studio_attempts (id INTEGER PRIMARY KEY, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ai_drafts (
                deal_id INTEGER PRIMARY KEY REFERENCES deals(id) ON DELETE CASCADE,
                fingerprint TEXT NOT NULL, facts TEXT NOT NULL, payload TEXT NOT NULL,
                model TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS ai_attempts (
                id INTEGER PRIMARY KEY, deal_id INTEGER NOT NULL,
                started_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'running'
            );
            CREATE TABLE IF NOT EXISTS deal_schedule (
                id INTEGER PRIMARY KEY CHECK(id=1), enabled INTEGER NOT NULL DEFAULT 0,
                interval_hours INTEGER NOT NULL DEFAULT 12, next_run_at TEXT
            );
            INSERT OR IGNORE INTO deal_schedule(id) VALUES (1);
            CREATE TABLE IF NOT EXISTS deal_queue (
                deal_id INTEGER PRIMARY KEY REFERENCES deals(id) ON DELETE CASCADE,
                status TEXT NOT NULL DEFAULT 'queued', message TEXT NOT NULL DEFAULT '',
                queued_at TEXT NOT NULL
            );
        """)

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS import_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT NOT NULL DEFAULT '',
                imported_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS trend_terms (
                source TEXT NOT NULL,
                term TEXT NOT NULL,
                traffic INTEGER NOT NULL DEFAULT 0,
                published_at TEXT,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY(source, term)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deal_interest_daily (
                deal_id INTEGER NOT NULL REFERENCES deals(id) ON DELETE CASCADE,
                day TEXT NOT NULL,
                clicks INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(deal_id, day)
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deals_status ON deals(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deals_source ON deals(source)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_deals_rank ON deals(status, trend_score DESC, click_count DESC)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_deal_interest_day ON deal_interest_daily(day)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_deals_expiry ON deals(status, expires_at)"
        )
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS briefs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_deal_id INTEGER UNIQUE REFERENCES deals(id) ON DELETE SET NULL,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                facts TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                created_at TEXT NOT NULL,
                published_at TEXT,
                summary TEXT NOT NULL DEFAULT '',
                fingerprint TEXT NOT NULL UNIQUE
            );
            CREATE INDEX IF NOT EXISTS idx_briefs_queue ON briefs(status, id);
            CREATE TABLE IF NOT EXISTS editorial_schedule (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                enabled INTEGER NOT NULL DEFAULT 0,
                interval_hours INTEGER NOT NULL DEFAULT 12,
                next_run_at TEXT,
                last_run_at TEXT,
                last_message TEXT NOT NULL DEFAULT 'Noch nicht aktiviert.'
            );
            INSERT OR IGNORE INTO editorial_schedule(id) VALUES (1);
            CREATE TABLE IF NOT EXISTS social_exports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brief_id INTEGER NOT NULL REFERENCES briefs(id) ON DELETE CASCADE,
                platform TEXT NOT NULL,
                caption TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'prepared',
                created_at TEXT NOT NULL,
                shared_at TEXT,
                UNIQUE(brief_id, platform)
            );
        """)
        # Releases before 3.2 could publish a Toppreise research URL directly.
        # These records must be reviewed and assigned to a merchant before going live again.
        conn.execute(
            """
            UPDATE deals SET status = 'draft', enrichment_status = 'needs_input',
                enrichment_notes = 'Direkter Händlerlink erforderlich.'
            WHERE status = 'published'
              AND (affiliate_link LIKE 'https://toppreise.ch/%'
                   OR affiliate_link LIKE 'https://www.toppreise.ch/%')
            """
        )


def content_hash(values: dict[str, Any]) -> str:
    payload = json.dumps(values, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def upsert_deal(db_path: str, values: dict[str, Any]) -> str:
    """Insert or update a deal and return created, updated, or unchanged."""
    timestamp = now_iso()
    material = {
        key: values.get(key)
        for key in (
            "title",
            "category",
            "base_price",
            "coupon_discount",
            "payment_bonus",
            "effective_price",
            "shop_name",
            "affiliate_link",
            "link_type",
            "source_name",
            "price_type",
            "coupon_code",
            "description",
            "expires_at",
            "source_url",
            "manufacturer_uvp",
            "image_url",
            "image_source",
            "review_summary",
            "youtube_reviews",
            "coupon_terms",
            "coupon_expires_at",
            "enrichment_status",
            "enrichment_notes",
            "gtin",
        )
    }
    digest = content_hash({key: material[key] for key in HASH_FIELDS})
    with connection(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM deals WHERE source = ? AND source_id = ?",
            (values["source"], values["source_id"]),
        ).fetchone()
        if existing:
            if values["source"] == "toppreise" and "toppreise.ch/" not in str(
                existing["affiliate_link"]
            ):
                # The snapshot remains a research signal. Never replace a reviewed
                # merchant destination or licensed enrichment with Toppreise data.
                conn.execute(
                    "UPDATE deals SET last_seen_at = ? WHERE id = ?",
                    (timestamp, existing["id"]),
                )
                return "unchanged"
            previous_digest = existing["content_hash"] or content_hash(
                {key: existing[key] for key in HASH_FIELDS}
            )
            changed = previous_digest != digest
            image_changed = (existing["image_url"] or "") != (material["image_url"] or "") or (existing["image_source"] or "") != (material["image_source"] or "")
            uvp_changed = (existing["manufacturer_uvp"] or 0) != (material["manufacturer_uvp"] or 0)
            if changed or image_changed or uvp_changed:
                conn.execute("DELETE FROM deal_queue WHERE deal_id=? AND status!='processing'", (existing["id"],))
            if image_changed:
                conn.execute("UPDATE deals SET image_rights_confirmed=0 WHERE id=?", (existing["id"],))
            if uvp_changed:
                conn.execute("UPDATE deals SET uvp_source_url='' WHERE id=?", (existing["id"],))
            changed = changed or image_changed or uvp_changed
            status = existing["status"]
            if values["source"] == "manual":
                status = values.get("status", status)
            elif status == "archived":
                status = "draft"
            elif changed and status == "published":
                # External content changes require another explicit review.
                status = "draft"
            if not changed and status == existing["status"]:
                conn.execute(
                    """
                    UPDATE deals SET last_seen_at = ?, price_checked_at = ?,
                        manufacturer_uvp = ?, image_url = ?, image_source = ?, gtin = ?
                    WHERE id = ?
                    """,
                    (
                        timestamp, values.get("price_checked_at", timestamp),
                        material["manufacturer_uvp"] or 0, material["image_url"] or "",
                        material["image_source"] or "", material["gtin"] or "", existing["id"],
                    ),
                )
                return "unchanged"
            conn.execute(
                """
                UPDATE deals SET
                    title = ?, category = ?, base_price = ?, coupon_discount = ?,
                    payment_bonus = ?, effective_price = ?, shop_name = ?,
                    affiliate_link = ?, coupon_code = ?, description = ?,
                    link_type = ?, source_name = ?, price_type = ?, price_checked_at = ?,
                    status = ?, updated_at = ?, expires_at = ?, source_url = ?, last_seen_at = ?,
                    content_hash = ?
                WHERE id = ?
                """,
                (
                    material["title"],
                    material["category"],
                    material["base_price"],
                    material["coupon_discount"],
                    material["payment_bonus"],
                    material["effective_price"],
                    material["shop_name"],
                    material["affiliate_link"],
                    material["coupon_code"],
                    material["description"],
                    material["link_type"],
                    material["source_name"],
                    material["price_type"],
                    values.get("price_checked_at", timestamp),
                    status,
                    timestamp,
                    material["expires_at"],
                    material["source_url"],
                    timestamp,
                    digest,
                    existing["id"],
                ),
            )
            conn.execute(
                """
                UPDATE deals SET manufacturer_uvp = ?, image_url = ?, image_source = ?,
                    review_summary = ?, youtube_reviews = ?, coupon_terms = ?,
                    coupon_expires_at = ?, enrichment_status = ?, enrichment_notes = ?, gtin = ?
                WHERE id = ?
                """,
                (
                    material["manufacturer_uvp"], material["image_url"],
                    material["image_source"], material["review_summary"],
                    material["youtube_reviews"], material["coupon_terms"],
                    material["coupon_expires_at"], material["enrichment_status"],
                    material["enrichment_notes"], material["gtin"], existing["id"],
                ),
            )
            return "updated"

        conn.execute(
            """
            INSERT INTO deals (
                title, category, base_price, coupon_discount, payment_bonus,
                effective_price, shop_name, affiliate_link, coupon_code,
                description, link_type, source_name, price_type, price_checked_at, source,
                source_id, status, created_at, updated_at, expires_at, source_url,
                last_seen_at, content_hash, manufacturer_uvp, image_url, image_source,
                review_summary, youtube_reviews, coupon_terms, coupon_expires_at,
                enrichment_status, enrichment_notes, gtin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                material["title"],
                material["category"],
                material["base_price"],
                material["coupon_discount"],
                material["payment_bonus"],
                material["effective_price"],
                material["shop_name"],
                material["affiliate_link"],
                material["coupon_code"],
                material["description"],
                material["link_type"],
                material["source_name"],
                material["price_type"],
                values.get("price_checked_at", timestamp),
                values["source"],
                values["source_id"],
                values.get("status", "draft"),
                timestamp,
                timestamp,
                material["expires_at"],
                material["source_url"],
                timestamp,
                digest,
                material["manufacturer_uvp"] or 0,
                material["image_url"] or "",
                material["image_source"] or "",
                material["review_summary"] or "",
                material["youtube_reviews"] or "[]",
                material["coupon_terms"] or "",
                material["coupon_expires_at"],
                material["enrichment_status"] or "pending",
                material["enrichment_notes"] or "",
                material["gtin"] or "",
            ),
        )
        return "created"


def expire_due_deals(db_path: str) -> int:
    """Move elapsed public deals to the visible expired collection."""
    timestamp = now_iso()
    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE deals SET status = 'expired', expired_at = ?, updated_at = ?
            WHERE status = 'published' AND expires_at IS NOT NULL AND expires_at <= ?
            """,
            (timestamp, timestamp, timestamp),
        )
        return cursor.rowcount


def archive_unseen(db_path: str, source: str, sync_started_at: str) -> int:
    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE deals SET status = 'archived', updated_at = ?
            WHERE source = ? AND status IN ('draft', 'published')
              AND (last_seen_at IS NULL OR last_seen_at < ?)
            """,
            (now_iso(), source, sync_started_at),
        )
        return cursor.rowcount


def log_import(db_path: str, source: str, status: str, message: str, count: int = 0) -> None:
    with connection(db_path) as conn:
        conn.execute(
            "INSERT INTO import_logs(source, status, message, imported_count, created_at) VALUES (?, ?, ?, ?, ?)",
            (source, status, message[:1000], count, now_iso()),
        )
