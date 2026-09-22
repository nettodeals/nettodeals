"""Opt-in publishing of approved, complete deals from a persistent queue."""
from datetime import UTC, datetime, timedelta

from .db import connection
from .editorial import publication_problems, publish_deal
from .studio import digest


def enqueue(db_path, deal_id):
    with connection(db_path) as conn:
        row = conn.execute("SELECT * FROM deals WHERE id=? AND status='draft'", (deal_id,)).fetchone()
        if not row:
            raise ValueError("Nur vorhandene Entwürfe können freigegeben werden.")
        problems = publication_problems(dict(row))
        pack = conn.execute("SELECT * FROM studio_packages WHERE deal_id=?", (deal_id,)).fetchone()
        if pack and (not pack["approved"] or pack["fingerprint"] != digest(dict(row))):
            problems.append("Aktuelle Deal- und Social-Texte zuerst im gemeinsamen Editor freigeben.")
        if problems:
            raise ValueError(" ".join(problems))
        conn.execute(
            """INSERT INTO deal_queue(deal_id, queued_at) VALUES (?,?)
               ON CONFLICT(deal_id) DO UPDATE SET status='queued', message='', queued_at=excluded.queued_at""",
            (deal_id, datetime.now(UTC).isoformat()),
        )


def configure(db_path, enabled, hours):
    if hours not in (6, 12, 24):
        raise ValueError("Erlaubte Intervalle: 6, 12 oder 24 Stunden.")
    with connection(db_path) as conn:
        conn.execute(
            "UPDATE deal_schedule SET enabled=?, interval_hours=? WHERE id=1",
            (int(enabled), hours),
        )


def tick(db_path, settings):
    now = datetime.now(UTC)
    # Claim before external YouTube enrichment; separate processes cannot claim twice.
    with connection(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        schedule = conn.execute("SELECT * FROM deal_schedule WHERE id=1").fetchone()
        if not schedule["enabled"] or (schedule["next_run_at"] and schedule["next_run_at"] > now.isoformat()):
            return
        conn.execute("UPDATE deal_queue SET status='done' WHERE status='queued' AND deal_id IN (SELECT id FROM deals WHERE status!='draft')")
        item = conn.execute("SELECT deal_id FROM deal_queue WHERE status='queued' ORDER BY queued_at, deal_id LIMIT 1").fetchone()
        if not item:
            return
        deal_id = item["deal_id"]
        conn.execute("UPDATE deal_queue SET status='processing' WHERE deal_id=?", (deal_id,))
        conn.execute("UPDATE deal_schedule SET next_run_at=? WHERE id=1", ((now + timedelta(hours=schedule["interval_hours"])).isoformat(),))
    try:
        publish_deal(db_path, deal_id, settings)
    except ValueError as exc:
        state, message = "failed", str(exc)
    else:
        state, message = "done", "Veröffentlicht"
    with connection(db_path) as conn:
        conn.execute("UPDATE deal_queue SET status=?, message=? WHERE deal_id=?", (state, message, deal_id))
