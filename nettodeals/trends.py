"""Free Swiss demand signals from Google Trends RSS and local clicks."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import requests
from defusedxml import ElementTree

from .db import connection, now_iso

HT_NS = "https://trends.google.com/trending/rss"
TOKEN_RE = re.compile(r"[a-z0-9äöüéèà]{3,}", re.IGNORECASE)
STOPWORDS = {
    "der",
    "die",
    "das",
    "und",
    "oder",
    "für",
    "mit",
    "von",
    "the",
    "bei",
    "eine",
    "einer",
    "eines",
    "neue",
    "new",
    "schweiz",
    "switzerland",
}


@dataclass(frozen=True, slots=True)
class TrendTerm:
    term: str
    traffic: int
    published_at: str | None = None


def parse_traffic(value: str | None) -> int:
    text = (value or "0").strip().upper().replace(",", ".").rstrip("+")
    multiplier = 1
    if text.endswith("K"):
        multiplier, text = 1_000, text[:-1]
    elif text.endswith("M"):
        multiplier, text = 1_000_000, text[:-1]
    try:
        return max(0, int(float(text) * multiplier))
    except ValueError:
        return 0


def parse_google_trends_rss(xml_text: str) -> list[TrendTerm]:
    root = ElementTree.fromstring(xml_text)
    terms: list[TrendTerm] = []
    seen: set[str] = set()
    for item in root.findall("./channel/item"):
        title = " ".join((item.findtext("title") or "").split())[:200]
        key = title.casefold()
        if not title or key in seen:
            continue
        seen.add(key)
        terms.append(
            TrendTerm(
                term=title,
                traffic=parse_traffic(item.findtext(f"{{{HT_NS}}}approx_traffic")),
                published_at=item.findtext("pubDate"),
            )
        )
    return terms


def fetch_google_trends(url: str, timeout: int) -> list[TrendTerm]:
    response = requests.get(
        url,
        headers={"User-Agent": "NettoDeals/3.0 (+https://nettodeals.ch)"},
        timeout=timeout,
    )
    response.raise_for_status()
    return parse_google_trends_rss(response.text)


def _tokens(value: str) -> set[str]:
    return {
        token.casefold() for token in TOKEN_RE.findall(value) if token.casefold() not in STOPWORDS
    }


def match_quality(product_title: str, trend_term: str) -> float:
    product = product_title.casefold()
    trend = trend_term.casefold()
    if trend in product or product in trend:
        return 1.0
    left, right = _tokens(product), _tokens(trend)
    if not left or not right:
        return 0.0
    overlap = left & right
    if not overlap:
        return 0.0
    return min(0.9, len(overlap) / max(1, min(len(left), len(right))))


def store_and_apply_trends(db_path: str, terms: list[TrendTerm]) -> int:
    fetched_at = now_iso()
    with connection(db_path) as conn:
        if terms:
            conn.execute("DELETE FROM trend_terms WHERE source = 'google_ch'")
            conn.executemany(
                "INSERT INTO trend_terms(source, term, traffic, published_at, fetched_at) VALUES ('google_ch', ?, ?, ?, ?)",
                [(term.term, term.traffic, term.published_at, fetched_at) for term in terms],
            )

        active_terms = conn.execute(
            "SELECT term, traffic FROM trend_terms WHERE source = 'google_ch'"
        ).fetchall()
        deals = conn.execute(
            "SELECT id, title FROM deals WHERE status IN ('draft', 'published')"
        ).fetchall()
        updates: list[tuple[float, int]] = []
        for deal in deals:
            score = 0.0
            for term in active_terms:
                quality = match_quality(deal["title"], term["term"])
                if quality:
                    score = max(score, quality * (20 + 18 * math.log10(term["traffic"] + 1)))
            updates.append((round(score, 2), deal["id"]))
        conn.executemany("UPDATE deals SET trend_score = ? WHERE id = ?", updates)
    return len(terms)


def trend_cache_age_seconds(db_path: str) -> int | None:
    with connection(db_path) as conn:
        row = conn.execute("SELECT MAX(fetched_at) AS fetched_at FROM trend_terms").fetchone()
    if not row or not row["fetched_at"]:
        return None
    try:
        fetched = datetime.fromisoformat(row["fetched_at"])
        return max(0, int((datetime.now(UTC) - fetched).total_seconds()))
    except ValueError:
        return None
