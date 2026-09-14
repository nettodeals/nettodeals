"""Affiliate import, normalization, moderation, and synchronization services."""

from __future__ import annotations

import hashlib
import math
import re
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import requests

from .config import Settings
from .db import archive_unseen, connection, log_import, now_iso, upsert_deal
from .security import normalize_external_url, redact_secrets
from .trends import fetch_google_trends, store_and_apply_trends

AWIN_API_BASE = "https://api.awin.com"
TRADEDOUBLER_API_BASE = "https://api.tradedoubler.com/1.0"
MONEY_MAX = 10_000_000.0


def first(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def safe_money(value: Any) -> float:
    if isinstance(value, dict):
        value = first(value, "value", "amount", default=0)
    if isinstance(value, str):
        value = (
            value.replace("CHF", "")
            .replace("€", "")
            .replace("’", "")
            .replace("'", "")
            .replace(" ", "")
        )
        if "," in value and "." in value:
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", ".")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(number):
        return 0.0
    return round(min(MONEY_MAX, max(0.0, number)), 2)


def effective_price(base: Any, coupon: Any = 0, bonus: Any = 0) -> float:
    return round(max(0.0, safe_money(base) - safe_money(coupon) - safe_money(bonus)), 2)


def source_id(*values: Any) -> str:
    raw = "|".join(str(value or "").strip() for value in values)
    return hashlib.sha256(raw.encode()).hexdigest()


def expiry_iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            numeric = float(value)
            if numeric > 10_000_000_000:
                numeric /= 1000
            return datetime.fromtimestamp(numeric, tz=UTC).isoformat()
        text = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat()
    except (ValueError, TypeError, OSError):
        return None


def clean_text(value: Any, maximum: int) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:maximum]


@dataclass(frozen=True, slots=True)
class DealCandidate:
    title: str
    category: str
    base_price: float
    shop_name: str
    affiliate_link: str
    source: str
    source_id: str
    coupon_discount: float = 0.0
    payment_bonus: float = 0.0
    coupon_code: str = ""
    description: str = ""
    expires_at: str | None = None
    source_url: str = ""

    def values(self, *, status: str = "draft") -> dict[str, Any]:
        base = safe_money(self.base_price)
        coupon = safe_money(self.coupon_discount)
        bonus = safe_money(self.payment_bonus)
        return {
            "title": clean_text(self.title, 300),
            "category": clean_text(self.category or "Deals", 80),
            "base_price": base,
            "coupon_discount": coupon,
            "payment_bonus": bonus,
            "effective_price": effective_price(base, coupon, bonus),
            "shop_name": clean_text(self.shop_name or "Unbekannter Shop", 120),
            "affiliate_link": normalize_external_url(self.affiliate_link),
            "coupon_code": clean_text(self.coupon_code, 120),
            "description": clean_text(self.description, 2000),
            "source": self.source,
            "source_id": self.source_id,
            "status": status,
            "expires_at": self.expires_at,
            "source_url": normalize_external_url(self.source_url),
        }


def map_awin_offer(offer: dict[str, Any]) -> DealCandidate | None:
    title = clean_text(first(offer, "title", "name"), 300)
    if not title:
        return None
    advertiser = offer.get("advertiser") if isinstance(offer.get("advertiser"), dict) else {}
    voucher = offer.get("voucher") if isinstance(offer.get("voucher"), dict) else {}
    advertiser_id = first(advertiser, "id", default="")
    promotion_id = first(offer, "promotionId", "id", default="")
    link = first(offer, "urlTracking", "trackingUrl", "url", "destinationUrl", default="")
    return DealCandidate(
        title=title,
        category="Rabattcode" if offer.get("type") == "voucher" else "Aktion",
        base_price=0,
        shop_name=first(advertiser, "name", default="AWIN Shop"),
        affiliate_link=link,
        coupon_code=first(voucher, "code", default=first(offer, "voucherCode", "code", default="")),
        description=first(offer, "description", "terms", default=""),
        source="awin",
        source_id=source_id("awin", promotion_id, advertiser_id, title),
        expires_at=expiry_iso(first(offer, "endDate", default=None)),
        source_url=first(offer, "url", "destinationUrl", default=""),
    )


def _category(product: dict[str, Any]) -> str:
    direct = first(product, "category", "categoryName")
    if isinstance(direct, str) and direct.strip():
        return direct
    categories = product.get("categories")
    if isinstance(categories, list) and categories:
        item = categories[0]
        if isinstance(item, dict):
            return str(first(item, "name", "tdCategoryName", default="Produkte"))
        return str(item)
    return "Produkte"


def _price_from_offer(offer: dict[str, Any], product: dict[str, Any]) -> tuple[float, str]:
    price = first(offer, "price", "salePrice", "lowestPrice", default=None)
    currency = ""
    if isinstance(price, dict):
        currency = str(first(price, "currency", "currencyId", default="")).upper()
    if price in (None, ""):
        price = first(product, "price", "salePrice", "lowestPrice", default=None)
    if isinstance(price, dict):
        currency = currency or str(first(price, "currency", "currencyId", default="")).upper()
    if price in (None, ""):
        history = offer.get("priceHistory") or product.get("priceHistory") or []
        if isinstance(history, list) and history:
            price = history[-1].get("price") if isinstance(history[-1], dict) else 0
            if isinstance(price, dict):
                currency = str(first(price, "currency", "currencyId", default="")).upper()
    currency = currency or str(first(offer, "currency", "currencyId", default="")).upper()
    return safe_money(price), currency


def map_tradedoubler_product(
    product: dict[str, Any], feed_id: Any, expected_currency: str = "CHF"
) -> list[DealCandidate]:
    title = clean_text(first(product, "name", "title", "productName"), 300)
    if not title:
        return []
    offers = product.get("offers")
    if not isinstance(offers, list) or not offers:
        offers = [product]
    candidates: list[DealCandidate] = []
    for offer in offers:
        if not isinstance(offer, dict):
            continue
        price, currency = _price_from_offer(offer, product)
        if currency and expected_currency and currency != expected_currency:
            continue
        link = first(
            offer,
            "productUrl",
            "trackingUrl",
            "trackingURL",
            "affiliateUrl",
            "clickUrl",
            default=first(product, "productUrl", "trackingUrl", default=""),
        )
        offer_id = first(offer, "id", "sourceProductId", "sku", default="")
        product_id = first(product, "id", "groupingId", "productId", "sku", default="")
        candidates.append(
            DealCandidate(
                title=title,
                category=_category(product),
                base_price=price,
                shop_name=first(
                    offer,
                    "programName",
                    "merchantName",
                    "advertiserName",
                    "shopName",
                    default=first(product, "programName", default="TradeDoubler Shop"),
                ),
                affiliate_link=link,
                description=first(product, "shortDescription", "description", default=""),
                source="tradedoubler_product",
                source_id=source_id("tradedoubler", feed_id, product_id, offer_id, title),
                source_url=first(offer, "sourceProductUrl", default=""),
            )
        )
    return candidates


def map_tradedoubler_voucher(voucher: dict[str, Any]) -> DealCandidate | None:
    title = clean_text(first(voucher, "title", "name"), 300)
    if not title:
        return None
    voucher_id = first(voucher, "id", "voucherId", default="")
    shop = first(voucher, "programName", "advertiserName", default="TradeDoubler Shop")
    code = first(voucher, "code", "voucherCode", default="")
    link = first(
        voucher,
        "defaultTrackUri",
        "trackingUrl",
        "url",
        "landingUrl",
        "landingPage",
        default="",
    )
    source_url_value = first(voucher, "landingUrl", "landingPage", default="")
    description = first(voucher, "shortDescription", "description", default="")
    discount = safe_money(first(voucher, "discountAmount", default=0))
    if discount and voucher.get("isPercentage"):
        description = f"{description} ({discount:g}% Rabatt)".strip()
        discount = 0
    return DealCandidate(
        title=title,
        category="Rabattcode",
        base_price=0,
        coupon_discount=discount,
        shop_name=shop,
        affiliate_link=link,
        coupon_code=code,
        description=description,
        source="tradedoubler_voucher",
        source_id=source_id("tradedoubler_voucher", voucher_id, code, shop),
        expires_at=expiry_iso(first(voucher, "endDate", "publishEndDate", default=None)),
        source_url=source_url_value,
    )


@dataclass(slots=True)
class ImportResult:
    source: str
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    archived: int = 0

    @property
    def processed(self) -> int:
        return self.created + self.updated + self.unchanged

    def as_dict(self) -> dict[str, int | str]:
        return {
            "source": self.source,
            "created": self.created,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "archived": self.archived,
        }


class SyncService:
    _lock = threading.Lock()

    def __init__(self, settings: Settings):
        self.settings = settings
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "NettoDeals/3.0 (+https://nettodeals.ch)"})

    @property
    def _secrets(self) -> tuple[str, ...]:
        return (
            self.settings.awin_api_token,
            self.settings.tradedoubler_products_token,
            self.settings.tradedoubler_vouchers_token,
            self.settings.admin_token,
        )

    def _save(self, result: ImportResult, candidate: DealCandidate) -> None:
        values = candidate.values(status="draft")
        if not values["title"]:
            return
        outcome = upsert_deal(self.settings.db_path, values)
        setattr(result, outcome, getattr(result, outcome) + 1)

    def import_awin(self) -> ImportResult:
        result = ImportResult("awin")
        started = now_iso()
        headers = {
            "Authorization": f"Bearer {self.settings.awin_api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        page_size = 200
        complete = False
        for page in range(1, self.settings.awin_max_pages + 1):
            response = self.session.post(
                f"{AWIN_API_BASE}/publisher/{self.settings.awin_publisher_id}/promotions",
                headers=headers,
                json={
                    "filters": {
                        "membership": "joined",
                        "status": "active",
                        "type": "all",
                        "regionCodes": list(self.settings.awin_regions),
                    },
                    "pagination": {"page": page, "pageSize": page_size},
                },
                timeout=self.settings.http_timeout,
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                offers = payload
            elif isinstance(payload, dict):
                offers = first(payload, "offers", "promotions", "content", default=[])
            else:
                offers = []
            if not isinstance(offers, list):
                raise RuntimeError("Awin returned an unexpected offers payload")
            for offer in offers:
                if isinstance(offer, dict) and (candidate := map_awin_offer(offer)):
                    self._save(result, candidate)
            if len(offers) < page_size:
                complete = True
                break
        if not complete:
            raise RuntimeError("Awin pagination limit reached; no records were archived")
        result.archived = archive_unseen(self.settings.db_path, result.source, started)
        return result

    def import_tradedoubler_products(self) -> ImportResult:
        result = ImportResult("tradedoubler_product")
        started = now_iso()
        token = self.settings.tradedoubler_products_token
        response = self.session.get(
            f"{TRADEDOUBLER_API_BASE}/productFeeds.json",
            params={"token": token},
            timeout=self.settings.http_timeout,
        )
        response.raise_for_status()
        payload = response.json()
        feeds = payload.get("feeds", []) if isinstance(payload, dict) else []
        for feed in feeds:
            if not isinstance(feed, dict) or not feed.get("active", True):
                continue
            feed_id = first(feed, "feedId", "id")
            if feed_id in (None, ""):
                continue
            complete = False
            for page in range(self.settings.tradedoubler_max_pages):
                page_size = self.settings.max_products_per_feed
                url = (
                    f"{TRADEDOUBLER_API_BASE}/products.json;fid={int(feed_id)}"
                    f";currency={self.settings.tradedoubler_currency}"
                    f";pageSize={page_size};page={page}"
                )
                response = self.session.get(
                    url,
                    params={"token": token},
                    timeout=self.settings.http_timeout,
                )
                response.raise_for_status()
                data = response.json()
                products = data if isinstance(data, list) else data.get("products", [])
                if not isinstance(products, list):
                    raise RuntimeError("TradeDoubler returned an unexpected products payload")
                for product in products:
                    if isinstance(product, dict):
                        for candidate in map_tradedoubler_product(
                            product, feed_id, self.settings.tradedoubler_currency
                        ):
                            self._save(result, candidate)
                if len(products) < page_size:
                    complete = True
                    break
            if not complete:
                raise RuntimeError(f"TradeDoubler pagination limit reached for feed {feed_id}")
        result.archived = archive_unseen(self.settings.db_path, result.source, started)
        return result

    def import_tradedoubler_vouchers(self) -> ImportResult:
        result = ImportResult("tradedoubler_voucher")
        started = now_iso()
        token = self.settings.tradedoubler_vouchers_token
        page_size = 1000
        complete = False
        for page in range(self.settings.tradedoubler_max_pages):
            response = self.session.get(
                f"{TRADEDOUBLER_API_BASE}/vouchers.json;pageSize={page_size};page={page}",
                params={"token": token},
                timeout=self.settings.http_timeout,
            )
            response.raise_for_status()
            payload = response.json()
            vouchers = (
                payload
                if isinstance(payload, list)
                else first(payload, "vouchers", "voucher", default=[])
            )
            if not isinstance(vouchers, list):
                raise RuntimeError("TradeDoubler returned an unexpected vouchers payload")
            for voucher in vouchers:
                if isinstance(voucher, dict) and (candidate := map_tradedoubler_voucher(voucher)):
                    self._save(result, candidate)
            if len(vouchers) < page_size:
                complete = True
                break
        if not complete:
            raise RuntimeError("TradeDoubler voucher pagination limit reached")
        result.archived = archive_unseen(self.settings.db_path, result.source, started)
        return result

    def refresh_trends(self) -> int:
        terms = fetch_google_trends(
            self.settings.google_trends_url,
            self.settings.http_timeout,
        )
        return store_and_apply_trends(self.settings.db_path, terms)

    def _run_source(self, name: str, function: Any) -> dict[str, Any]:
        try:
            result = function()
            if isinstance(result, ImportResult):
                log_import(
                    self.settings.db_path,
                    name,
                    "success",
                    f"{result.processed} verarbeitet, {result.archived} archiviert",
                    result.processed,
                )
                return {"status": "success", **result.as_dict()}
            log_import(
                self.settings.db_path, name, "success", f"{result} Trends geladen", int(result)
            )
            return {"status": "success", "processed": int(result)}
        # A source sync is a fault-isolation boundary: one malformed or unavailable
        # provider must be logged without preventing the remaining sources.
        except Exception as exc:  # noqa: BLE001
            message = redact_secrets(exc, self._secrets)
            log_import(self.settings.db_path, name, "error", message)
            return {"status": "error", "message": message}

    def sync_all(self) -> dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            return {"status": "busy", "sources": {}}
        try:
            sources: dict[str, Any] = {}
            if self.settings.awin_publisher_id and self.settings.awin_api_token:
                sources["awin"] = self._run_source("awin", self.import_awin)
            if self.settings.tradedoubler_products_token:
                sources["tradedoubler_products"] = self._run_source(
                    "tradedoubler_products", self.import_tradedoubler_products
                )
            if self.settings.tradedoubler_vouchers_token:
                sources["tradedoubler_vouchers"] = self._run_source(
                    "tradedoubler_vouchers", self.import_tradedoubler_vouchers
                )
            if self.settings.google_trends_enabled:
                sources["google_trends_ch"] = self._run_source(
                    "google_trends_ch", self.refresh_trends
                )
            with connection(self.settings.db_path) as conn:
                conn.execute(
                    """
                    UPDATE deals SET status = 'archived', updated_at = ?
                    WHERE status IN ('draft', 'published')
                      AND expires_at IS NOT NULL AND expires_at < ?
                    """,
                    (now_iso(), now_iso()),
                )
            return {"status": "complete", "sources": sources, "finished_at": now_iso()}
        finally:
            self._lock.release()

    def configured_sources(self) -> dict[str, bool]:
        return {
            "awin": bool(self.settings.awin_publisher_id and self.settings.awin_api_token),
            "tradedoubler_products": bool(self.settings.tradedoubler_products_token),
            "tradedoubler_vouchers": bool(self.settings.tradedoubler_vouchers_token),
            "google_trends_ch": self.settings.google_trends_enabled,
        }
