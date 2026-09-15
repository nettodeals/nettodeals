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
                UNIQUE(source, source_id)
            )
            """
        )
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(deals)")}
        migrations = {
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
        }
        for name, definition in migrations.items():
            if name not in existing:
                conn.execute(f'ALTER TABLE deals ADD COLUMN "{name}" {definition}')

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
        )
    }
    digest = content_hash(material)
    with connection(db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM deals WHERE source = ? AND source_id = ?",
            (values["source"], values["source_id"]),
        ).fetchone()
        if existing:
            previous_digest = existing["content_hash"] or content_hash(
                {key: existing[key] for key in material}
            )
            changed = previous_digest != digest
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
                    "UPDATE deals SET last_seen_at = ?, price_checked_at = ? WHERE id = ?",
                    (timestamp, values.get("price_checked_at", timestamp), existing["id"]),
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
            return "updated"

        conn.execute(
            """
            INSERT INTO deals (
                title, category, base_price, coupon_discount, payment_bonus,
                effective_price, shop_name, affiliate_link, coupon_code,
                description, link_type, source_name, price_type, price_checked_at, source,
                source_id, status, created_at, updated_at, expires_at, source_url,
                last_seen_at, content_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            ),
        )
        return "created"


def archive_unseen(db_path: str, source: str, sync_started_at: str) -> int:
    with connection(db_path) as conn:
        cursor = conn.execute(
            """
            UPDATE deals SET status = 'archived', updated_at = ?
            WHERE source = ? AND status != 'archived'
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
