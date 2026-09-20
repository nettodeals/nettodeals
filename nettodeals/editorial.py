"""Safe editorial enrichment for review-ready deal drafts."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse

import requests

from .ai_editor import approved_summary
from .config import Settings
from .db import connection, now_iso
from .security import normalize_external_url
from .services import effective_price, safe_money

TOPPREISE_HOSTS = {"toppreise.ch", "www.toppreise.ch"}
STOPWORDS = {
    "ab", "bei", "der", "die", "das", "den", "des", "ein", "eine", "für", "mit",
    "ohne", "und", "von", "zu", "schwarz", "weiss", "white", "black", "neu",
}


def _tokens(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", value.casefold())
    expanded = set(words)
    for word in words:
        if any(char.isdigit() for char in word) and any(char.isalpha() for char in word):
            expanded.update(re.findall(r"[a-z]+|\d+", word))
    return {word for word in expanded if len(word) > 1 and word not in STOPWORDS}


def _model_tokens(value: str) -> set[str]:
    return {word for word in _tokens(value) if any(char.isdigit() for char in word)}


def _merchant_key(value: str) -> str:
    return "".join(re.findall(r"[a-z0-9]+", value.casefold()))


def product_similarity(left: str, right: str) -> float:
    first, second = _tokens(left), _tokens(right)
    if not first or not second:
        return 0.0
    left_models, right_models = _model_tokens(left), _model_tokens(right)
    if left_models and right_models and not left_models.intersection(right_models):
        return 0.0
    jaccard = len(first.intersection(second)) / len(first.union(second))
    sequence = SequenceMatcher(None, " ".join(sorted(first)), " ".join(sorted(second))).ratio()
    return round(jaccard * 0.7 + sequence * 0.3, 4)


def is_direct_merchant_url(value: str) -> bool:
    url = normalize_external_url(value)
    return bool(url and (urlparse(url).hostname or "").casefold() not in TOPPREISE_HOSTS)


def _youtube_reviews(title: str, settings: Settings) -> list[dict[str, str]]:
    if not settings.youtube_api_key:
        return []
    response = requests.get(
        "https://www.googleapis.com/youtube/v3/search",
        params={
            "part": "snippet",
            "q": f'"{title}" Test Review',
            "type": "video",
            "maxResults": 3,
            "order": "relevance",
            "regionCode": "CH",
            "relevanceLanguage": "de",
            "safeSearch": "moderate",
            "key": settings.youtube_api_key,
        },
        timeout=settings.http_timeout,
    )
    response.raise_for_status()
    reviews: list[dict[str, str]] = []
    for item in response.json().get("items", []):
        video_id = item.get("id", {}).get("videoId", "")
        snippet = item.get("snippet", {})
        if not re.fullmatch(r"[\w-]{6,20}", video_id):
            continue
        reviews.append(
            {
                "title": str(snippet.get("title", ""))[:200],
                "channel": str(snippet.get("channelTitle", ""))[:120],
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )
    return reviews


def _summary(row: dict[str, Any]) -> str:
    price = safe_money(row.get("effective_price"))
    uvp = safe_money(row.get("manufacturer_uvp"))
    parts = [
        f"{row['title']} gehört zur Kategorie "
        f"{row.get('category') or 'Produkte'}."
    ]
    if price and row.get("shop_name"):
        parts.append(f"Der hinterlegte Angebotspreis bei {row['shop_name']} beträgt CHF {price:.2f}.")
    if row.get("uvp_source_url") and uvp > price > 0:
        discount = round((uvp - price) / uvp * 100)
        parts.append(f"Das entspricht rund {discount}% unter der Hersteller-UVP von CHF {uvp:.2f}.")
    if row.get("coupon_code"):
        parts.append("Ein zusätzlicher Gutscheincode ist hinterlegt; die Bedingungen sind vor dem Kauf zu prüfen.")
    parts.append("Dieser Kurzcheck basiert auf Anbieter- und Herstellerdaten; NettoDeals hat das Produkt nicht selbst getestet.")
    return " ".join(parts)


def enrich_deal(db_path: str, deal_id: int, settings: Settings) -> dict[str, Any]:
    """Enrich a draft from joined partner data without scraping a price-comparison site."""
    with connection(db_path) as conn:
        source_row = conn.execute("SELECT * FROM deals WHERE id = ?", (deal_id,)).fetchone()
        if not source_row:
            raise ValueError("Deal nicht gefunden.")
        deal = dict(source_row)

        if not is_direct_merchant_url(deal.get("affiliate_link", "")):
            offers = conn.execute(
                """
                SELECT * FROM deals
                WHERE source IN ('tradedoubler_product', 'awin_product')
                  AND base_price > 0 AND affiliate_link != ''
                  AND (expires_at IS NULL OR expires_at > ?)
                """,
                (now_iso(),),
            ).fetchall()
            matches = [
                (product_similarity(deal["title"], offer["title"]), dict(offer))
                for offer in offers
            ]
            matches = [item for item in matches if item[0] >= 0.72]
            if matches:
                _, offer = min(matches, key=lambda item: (safe_money(item[1]["effective_price"]), -item[0]))
                for field in (
                    "shop_name", "affiliate_link", "base_price", "effective_price",
                    "price_checked_at", "manufacturer_uvp", "image_url", "image_source", "gtin",
                ):
                    if offer.get(field) not in (None, "", 0):
                        deal[field] = offer[field]
                deal["link_type"] = "affiliate"

        if deal.get("shop_name") and not deal.get("coupon_code"):
            vouchers = conn.execute(
                """
                SELECT * FROM deals
                WHERE source IN ('awin', 'tradedoubler_voucher') AND coupon_code != ''
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY updated_at DESC LIMIT 100
                """,
                (now_iso(),),
            ).fetchall()
            vouchers = next(
                (
                    row for row in vouchers
                    if _merchant_key(row["shop_name"]) == _merchant_key(deal["shop_name"])
                ),
                None,
            )
            if vouchers:
                voucher = dict(vouchers)
                deal["coupon_code"] = voucher["coupon_code"]
                deal["coupon_terms"] = voucher.get("description") or "Bedingungen beim Händler prüfen."
                deal["coupon_expires_at"] = voucher.get("expires_at")

        notes: list[str] = []
        direct = is_direct_merchant_url(deal.get("affiliate_link", ""))
        if not direct:
            notes.append("Händlerangebot ergänzen: Ein normaler direkter Shoplink genügt; Affiliate-Partner sind nicht nötig.")
        if not deal.get("image_url"):
            notes.append("Produktbild ergänzen und Nutzungsrecht bestätigen.")

        reviews: list[dict[str, str]] = []
        try:
            reviews = _youtube_reviews(deal["title"], settings)
        except (requests.RequestException, ValueError):
            notes.append("YouTube-Suche vorübergehend nicht verfügbar.")
        deal["youtube_reviews"] = json.dumps(reviews, ensure_ascii=False)
        deal["effective_price"] = effective_price(
            deal.get("base_price"), deal.get("coupon_discount"), deal.get("payment_bonus")
        )
        problems = publication_problems(deal)
        reviewed = approved_summary(db_path, deal)
        deal["review_summary"] = (reviewed + " Kein eigener Produkttest.") if reviewed else _summary(deal)
        deal["enrichment_status"] = "needs_input" if problems else "ready"
        deal["enrichment_notes"] = " ".join(dict.fromkeys(problems + notes))
        conn.execute(
            """
            UPDATE deals SET shop_name = ?, affiliate_link = ?, link_type = ?, base_price = ?,
                effective_price = ?, price_checked_at = ?, manufacturer_uvp = ?, image_url = ?,
                image_source = ?, gtin = ?, coupon_code = ?, coupon_terms = ?,
                coupon_expires_at = ?, youtube_reviews = ?, review_summary = ?,
                enrichment_status = ?, enrichment_notes = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                deal.get("shop_name", ""), deal.get("affiliate_link", ""), deal.get("link_type", "affiliate"),
                safe_money(deal.get("base_price")), safe_money(deal.get("effective_price")),
                deal.get("price_checked_at"), safe_money(deal.get("manufacturer_uvp")),
                normalize_external_url(deal.get("image_url", "")), deal.get("image_source", ""),
                deal.get("gtin", ""), deal.get("coupon_code", ""), deal.get("coupon_terms", ""),
                deal.get("coupon_expires_at"), deal["youtube_reviews"], deal["review_summary"],
                deal["enrichment_status"], deal["enrichment_notes"], now_iso(), deal_id,
            ),
        )
        return deal


def publication_problems(deal: dict[str, Any]) -> list[str]:
    problems = []
    if not is_direct_merchant_url(deal.get("affiliate_link", "")) or not deal.get("shop_name", "").strip():
        problems.append("Händlerangebot fehlt: Shopname und normaler HTTPS-Shoplink reichen aus.")
    if safe_money(deal.get("effective_price")) <= 0:
        problems.append("Ein positiver geprüfter Angebotspreis ist erforderlich.")
    if not normalize_external_url(deal.get("image_url", "")) or not deal.get("image_source", "").strip() or not deal.get("image_rights_confirmed"):
        problems.append("Produktbild, Bildquelle und bestätigtes Nutzungsrecht sind erforderlich.")
    if safe_money(deal.get("manufacturer_uvp")) > 0 and not normalize_external_url(deal.get("uvp_source_url", "")):
        problems.append("Bitte die Herstellerquelle zur UVP angeben oder die unbelegte UVP auf 0 setzen.")
    try:
        checked = datetime.fromisoformat(str(deal.get("price_checked_at") or "").replace("Z", "+00:00"))
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=UTC)
        age = datetime.now(UTC) - checked
        if age > timedelta(hours=48) or age < -timedelta(minutes=5):
            problems.append("Preisprüfung ist älter als 48 Stunden oder liegt in der Zukunft; bitte erneut prüfen und speichern.")
    except ValueError:
        problems.append("Preisprüfung fehlt; Händlerdaten prüfen und speichern.")
    return problems


def publish_deal(db_path: str, deal_id: int, settings: Settings) -> None:
    with connection(db_path) as conn:
        current = conn.execute("SELECT status FROM deals WHERE id=?", (deal_id,)).fetchone()
        if current and current["status"] == "published":
            return
    deal = enrich_deal(db_path, deal_id, settings)
    if deal["enrichment_status"] != "ready":
        raise ValueError(deal["enrichment_notes"] or "Händlerlink, Shop und Preis fehlen.")
    published = datetime.now(UTC)
    expires = published + timedelta(hours=settings.deal_lifetime_hours)
    for value in (deal.get("expires_at"), deal.get("coupon_expires_at")):
        if not value:
            continue
        try:
            candidate = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if candidate.tzinfo is None:
                candidate = candidate.replace(tzinfo=UTC)
            expires = min(expires, candidate.astimezone(UTC))
        except ValueError:
            continue
    if expires <= published:
        raise ValueError("Das Händlerangebot oder der Gutschein ist bereits abgelaufen.")
    with connection(db_path) as conn:
        conn.execute(
            """
            UPDATE deals SET status = 'published', published_at = ?, expires_at = ?,
                expired_at = NULL, updated_at = ? WHERE id = ?
            """,
            (published.isoformat(), expires.isoformat(), published.isoformat(), deal_id),
        )
