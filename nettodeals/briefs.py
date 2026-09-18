"""Free editorial publishing: factual briefs, durable schedule and manual social exports.

No crawling, paid AI, social passwords, or remote posting. Every queued entry is
explicitly approved by the editor. Price claims are deliberately excluded.
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from .db import connection
from .security import normalize_external_url
from .seo import slugify

MAX_SOURCE_AGE = timedelta(days=7)
PLATFORMS = ("x", "instagram", "tiktok")


def parse_date(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValueError("Bitte einen gültigen Quellen-Datenstand angeben.") from exc
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result.astimezone(UTC)


def brief_path(brief_id: int, title: str) -> str:
    return f"/steckbrief/{brief_id}/{slugify(title)}"


def make_summary(title: str, category: str, facts: str) -> str:
    intro = f"Im Schweizer Einkaufsradar: {title}. Kategorie: {category}."
    if facts:
        intro += " " + " ".join(facts.splitlines())
    return intro + " Redaktioneller Steckbrief – kein eigener Produkttest und kein bestätigtes Rabattangebot."


def save_brief(
    db_path: str, *, title: str, category: str, facts: str, source_url: str,
    source_name: str, source_at: str, mode: str, site_url: str,
    source_deal_id: int | None = None, now: datetime | None = None,
    brief_id: int | None = None,
) -> int:
    now = now or datetime.now(UTC)
    title, category, facts = title.strip(), category.strip() or "Produkte", facts.strip()
    source_name = source_name.strip()
    safe_url = normalize_external_url(source_url)
    if not title or len(title) > 300 or len(category) > 80:
        raise ValueError("Titel (max. 300 Zeichen) und Kategorie (max. 80) prüfen.")
    if not safe_url or not source_name or len(source_name) > 120 or len(facts) > 1600:
        raise ValueError("HTTPS-Quelle, Quellenname und maximal 1600 Zeichen eigener Fakten sind erforderlich.")
    observed = parse_date(source_at)
    if observed > now + timedelta(minutes=5):
        raise ValueError("Der Quellen-Datenstand darf nicht in der Zukunft liegen.")
    if mode not in {"draft", "queue", "publish"}:
        raise ValueError("Ungültige Publikationsart.")
    if mode != "draft" and observed < now - MAX_SOURCE_AGE:
        raise ValueError("Die Quelle ist älter als sieben Tage. Erst erneut prüfen und Datenstand aktualisieren.")
    # Same product + same source cannot be repeatedly queued, even by double tap.
    digest = hashlib.sha256((title.casefold() + "|" + safe_url).encode()).hexdigest()
    with connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        if brief_id is not None:
            existing = conn.execute("SELECT id, status FROM briefs WHERE id=?", (brief_id,)).fetchone()
            if not existing:
                raise ValueError("Steckbrief nicht gefunden.")
        else:
            existing = conn.execute(
                "SELECT id, status FROM briefs WHERE fingerprint = ? OR source_deal_id = ?",
                (digest, source_deal_id),
            ).fetchone()
        if existing and existing["status"] == "published":
            raise ValueError("Dieser Steckbrief wurde bereits veröffentlicht. Keine doppelte Publikation.")
        if existing and conn.execute(
            "SELECT 1 FROM briefs WHERE fingerprint=? AND id!=?", (digest, existing["id"])
        ).fetchone():
            raise ValueError("Ein anderer Steckbrief verwendet bereits diesen Titel und diese Quelle.")
        values = (
            title, category, facts, safe_url, source_name, observed.isoformat(),
            "queued" if mode == "queue" else "draft", digest,
        )
        if existing:
            brief_id = int(existing["id"])
            conn.execute(
                """UPDATE briefs SET title=?, category=?, facts=?, source_url=?,
                   source_name=?, source_at=?, status=?, fingerprint=? WHERE id=?""",
                (*values, brief_id),
            )
        else:
            cursor = conn.execute(
                """INSERT INTO briefs(title, category, facts, source_url, source_name,
                   source_at, status, fingerprint, source_deal_id, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*values, source_deal_id, now.isoformat()),
            )
            brief_id = int(cursor.lastrowid)
        if mode == "publish":
            _publish(conn, brief_id, site_url, now)
        return brief_id


def _publish(conn: sqlite3.Connection, brief_id: int, site_url: str, now: datetime) -> None:
    brief = conn.execute("SELECT * FROM briefs WHERE id=?", (brief_id,)).fetchone()
    if not brief or brief["status"] == "published":
        return
    if parse_date(brief["source_at"]) < now - MAX_SOURCE_AGE:
        raise ValueError("Die Quelle ist zu alt; bitte erneut prüfen.")
    summary = make_summary(brief["title"], brief["category"], brief["facts"])
    conn.execute(
        "UPDATE briefs SET status='published', published_at=?, summary=? WHERE id=?",
        (now.isoformat(), summary, brief_id),
    )
    url = site_url.rstrip("/") + brief_path(brief_id, brief["title"])
    stamp = parse_date(brief["source_at"]).strftime("%d.%m.%Y")
    for platform in PLATFORMS:
        if platform == "x":
            # Budget below 280 weighted characters, including full-width characters.
            caption = f"Produkt-Steckbrief: {brief['title'][:65]}\nKein bestätigter Rabatt. Stand {stamp}.\n{url}\n#Schweiz"
        else:
            caption = (
                f"{brief['title']} – Produkt-Steckbrief für die Schweiz\n\n{summary[:950]}\n\n"
                f"Quelle: {brief['source_name']}. Datenstand: {stamp}.\n"
                f"Mehr auf nettodeals.ch (Steckbriefe).\n{url}\n"
                "#Schweiz #ProduktSteckbrief"
            )
        conn.execute(
            """INSERT INTO social_exports(brief_id, platform, caption, created_at)
               VALUES (?, ?, ?, ?) ON CONFLICT(brief_id, platform) DO UPDATE SET
               caption=excluded.caption, created_at=excluded.created_at,
               status='prepared', shared_at=NULL""",
            (brief_id, platform, caption, now.isoformat()),
        )


def configure_schedule(db_path: str, enabled: bool, interval_hours: int) -> None:
    if interval_hours not in {6, 12, 24}:
        raise ValueError("Intervall muss 6, 12 oder 24 Stunden sein.")
    with connection(db_path) as conn:
        # Toggling pause does not reset the persisted next slot or create a burst.
        conn.execute(
            """UPDATE editorial_schedule SET enabled=?, interval_hours=?,
               next_run_at=COALESCE(next_run_at, ?), last_message=? WHERE id=1""",
            (int(enabled), interval_hours, datetime.now(UTC).isoformat(),
             "Aktiviert; nächste Prüfung innerhalb einer Minute." if enabled else "Pausiert."),
        )


def run_schedule(db_path: str, site_url: str, now: datetime | None = None) -> int | None:
    """Publish at most one entry per interval, atomically, without catch-up bursts."""
    now = now or datetime.now(UTC)
    with connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        schedule = conn.execute("SELECT * FROM editorial_schedule WHERE id=1").fetchone()
        if not schedule["enabled"]:
            return None
        if schedule["next_run_at"] and parse_date(schedule["next_run_at"]) > now:
            return None
        cutoff = (now - MAX_SOURCE_AGE).isoformat()
        conn.execute("UPDATE briefs SET status='stale' WHERE status='queued' AND source_at < ?", (cutoff,))
        brief = conn.execute(
            "SELECT id FROM briefs WHERE status='queued' ORDER BY id LIMIT 1"
        ).fetchone()
        if brief:
            _publish(conn, brief["id"], site_url, now)
            next_run = now + timedelta(hours=schedule["interval_hours"])
            message = f"Steckbrief #{brief['id']} publiziert; drei Social-Entwürfe erstellt (nicht gepostet)."
        else:
            # A short retry notices a newly refilled queue without a manual restart.
            next_run = now + timedelta(minutes=10)
            message = "Kein frischer freigegebener Steckbrief. Vorrat ergänzen oder alte Quellen erneut prüfen."
        conn.execute(
            "UPDATE editorial_schedule SET next_run_at=?, last_run_at=?, last_message=? WHERE id=1",
            (next_run.isoformat(), now.isoformat(), message),
        )
        return brief["id"] if brief else None


def brief_dict(row: Any) -> dict[str, Any]:
    item = dict(row)
    item["path"] = brief_path(item["id"], item["title"])
    item["source_display"] = parse_date(item["source_at"]).strftime("%d.%m.%Y")
    item["outdated"] = parse_date(item["source_at"]) < datetime.now(UTC) - MAX_SOURCE_AGE
    item["fact_lines"] = [line.strip() for line in item["facts"].splitlines() if line.strip()]
    return item
