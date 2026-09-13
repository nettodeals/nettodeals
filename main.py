# main.py

from contextlib import contextmanager
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
import hashlib
import os
import sqlite3
import re
from difflib import SequenceMatcher
from typing import Any, Optional
from urllib.parse import urljoin

import requests
import uvicorn

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jinja2 import Template


# ============================================================
# KONFIGURATION
# ============================================================

APP_PORT = int(os.getenv("APP_PORT", "8000"))

DB_PATH = os.getenv(
    "DB_PATH",
    "/data/nettodeals.db",
)

# ------------------------------------------------------------
# Admin
# ------------------------------------------------------------

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# ------------------------------------------------------------
# AWIN
# ------------------------------------------------------------

AWIN_PUBLISHER_ID = os.getenv("AWIN_PUBLISHER_ID", "")
AWIN_API_TOKEN = os.getenv("AWIN_API_TOKEN", "")

AWIN_API_BASE = "https://api.awin.com"

# ------------------------------------------------------------
# TRADEDOUBLER
# ------------------------------------------------------------

TRADEDOUBLER_PRODUCTS_TOKEN = os.getenv(
    "TRADEDOUBLER_PRODUCTS_TOKEN",
    "",
)

TRADEDOUBLER_VOUCHERS_TOKEN = os.getenv(
    "TRADEDOUBLER_VOUCHERS_TOKEN",
    "",
)

TRADEDOUBLER_API_BASE = "https://api.tradedoubler.com/1.0"

# ------------------------------------------------------------
# IMPORT-EINSTELLUNGEN
# ------------------------------------------------------------

MAX_PRODUCTS_PER_FEED = int(
    os.getenv("MAX_PRODUCTS_PER_FEED", "20")
)

HTTP_TIMEOUT = int(
    os.getenv("HTTP_TIMEOUT", "30")
)

# ------------------------------------------------------------
# TOPPREISE.CH – Trend-/Popularitätsquelle
# ------------------------------------------------------------
# Toppreise dient ausschliesslich als Signal für stark nachgefragte
# Produkte. Die Seite ist KEIN Affiliate-Partner; deshalb werden
# Toppreise-Produkte nie automatisch veröffentlicht.
TOPPREISE_ENABLED = os.getenv("TOPPREISE_ENABLED", "true").lower() in (
    "1", "true", "yes", "on"
)
TOPPREISE_URL = os.getenv(
    "TOPPREISE_URL",
    "https://www.toppreise.ch/topprodukte",
)
TOPPREISE_MAX_PRODUCTS = int(
    os.getenv("TOPPREISE_MAX_PRODUCTS", "50")
)

# Zweite Trendquelle: Produkte mit neu erreichten/aktualisierten Toppreisen.
TOPPREISE_NEW_ENABLED = os.getenv("TOPPREISE_NEW_ENABLED", "true").lower() in (
    "1", "true", "yes", "on"
)
TOPPREISE_NEW_URL = os.getenv(
    "TOPPREISE_NEW_URL",
    "https://www.toppreise.ch/neue-toppreise",
)
TOPPREISE_NEW_MAX_PRODUCTS = int(
    os.getenv("TOPPREISE_NEW_MAX_PRODUCTS", str(TOPPREISE_MAX_PRODUCTS))
)
TOPPREISE_USER_AGENT = os.getenv(
    "TOPPREISE_USER_AGENT",
    "Mozilla/5.0 (compatible; NettoDeals/2.2; +https://nettodeals.ch)"
)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="NettoDeals",
    version="2.0.0",
)


# ============================================================
# DATENBANK
# ============================================================

def ensure_db_directory() -> None:
    db_dir = os.path.dirname(DB_PATH)

    if db_dir:
        os.makedirs(
            db_dir,
            exist_ok=True,
        )


@contextmanager
def get_db():
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )

    conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()

    finally:
        conn.close()


def init_db() -> None:

    ensure_db_directory()

    with get_db() as conn:

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

                coupon_code TEXT,

                description TEXT,

                source TEXT NOT NULL DEFAULT 'manual',

                source_id TEXT,

                status TEXT NOT NULL DEFAULT 'draft',

                created_at TEXT NOT NULL,

                updated_at TEXT NOT NULL,

                UNIQUE(source, source_id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS import_logs (

                id INTEGER PRIMARY KEY AUTOINCREMENT,

                source TEXT NOT NULL,

                status TEXT NOT NULL,

                message TEXT,

                imported_count INTEGER NOT NULL DEFAULT 0,

                created_at TEXT NOT NULL
            )
            """
        )

        # Leichte Migration für bestehende Datenbanken
        existing_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(deals)").fetchall()
        }

        for column, definition in (
            ("popularity_rank", "INTEGER"),
            ("source_url", "TEXT"),
            ("last_checked_at", "TEXT"),
        ):
            if column not in existing_columns:
                conn.execute(
                    f"ALTER TABLE deals ADD COLUMN {column} {definition}"
                )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_deals_status
            ON deals(status)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_deals_source
            ON deals(source)
            """
        )


@app.on_event("startup")
def startup_event():

    init_db()


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def now_iso() -> str:

    return datetime.now(
        timezone.utc
    ).isoformat()


def calculate_effective_price(
    base_price: float,
    coupon_discount: float = 0.0,
    payment_bonus: float = 0.0,
) -> float:

    return round(
        max(
            0.0,
            base_price
            - coupon_discount
            - payment_bonus,
        ),
        2,
    )


def make_source_id(*values: Any) -> str:

    raw = "|".join(
        str(value or "")
        for value in values
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    if value is None:
        return default

    try:

        if isinstance(value, str):

            value = (
                value
                .replace("CHF", "")
                .replace("€", "")
                .replace(",", ".")
                .strip()
            )

        return float(value)

    except (
        ValueError,
        TypeError,
    ):

        return default


def first_value(
    data: dict,
    keys: list[str],
    default: Any = None,
):

    for key in keys:

        if key in data:

            value = data.get(key)

            if value not in (
                None,
                "",
            ):
                return value

    return default


def verify_admin_token(
    token: str,
) -> None:

    if not ADMIN_TOKEN:

        raise HTTPException(
            status_code=503,
            detail=(
                "ADMIN_TOKEN ist auf dem Server "
                "nicht konfiguriert."
            ),
        )

    if token != ADMIN_TOKEN:

        raise HTTPException(
            status_code=403,
            detail="Ungültiger Admin-Token.",
        )


def log_import(
    source: str,
    status: str,
    message: str,
    imported_count: int = 0,
) -> None:

    with get_db() as conn:

        conn.execute(
            """
            INSERT INTO import_logs (
                source,
                status,
                message,
                imported_count,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                source,
                status,
                message,
                imported_count,
                now_iso(),
            ),
        )


# ============================================================
# DEAL SPEICHERN / UPDATE
# ============================================================

def upsert_deal(
    *,
    title: str,
    category: str,
    base_price: float,
    coupon_discount: float,
    payment_bonus: float,
    shop_name: str,
    affiliate_link: str,
    coupon_code: Optional[str] = None,
    description: Optional[str] = None,
    source: str = "manual",
    source_id: Optional[str] = None,
    status: str = "draft",
) -> bool:

    title = str(title or "").strip()
    category = str(category or "Deals").strip()
    shop_name = str(shop_name or "Unbekannter Shop").strip()
    affiliate_link = str(
        affiliate_link or ""
    ).strip()

    if not title:
        return False

    # Ohne gültigen Link nicht automatisch veröffentlichen
    if not affiliate_link.startswith(
        ("http://", "https://")
    ):
        status = "draft"

    base_price = safe_float(base_price)

    coupon_discount = safe_float(
        coupon_discount
    )

    payment_bonus = safe_float(
        payment_bonus
    )

    effective_price = calculate_effective_price(
        base_price,
        coupon_discount,
        payment_bonus,
    )

    if not source_id:

        source_id = make_source_id(
            title,
            shop_name,
            affiliate_link,
        )

    timestamp = now_iso()

    with get_db() as conn:

        existing = conn.execute(
            """
            SELECT id
            FROM deals
            WHERE source = ?
            AND source_id = ?
            """,
            (
                source,
                source_id,
            ),
        ).fetchone()

        if existing:

            conn.execute(
                """
                UPDATE deals
                SET

                    title = ?,

                    category = ?,

                    base_price = ?,

                    coupon_discount = ?,

                    payment_bonus = ?,

                    effective_price = ?,

                    shop_name = ?,

                    affiliate_link = ?,

                    coupon_code = ?,

                    description = ?,

                    updated_at = ?

                WHERE id = ?
                """,
                (
                    title,
                    category,
                    base_price,
                    coupon_discount,
                    payment_bonus,
                    effective_price,
                    shop_name,
                    affiliate_link,
                    coupon_code,
                    description,
                    timestamp,
                    existing["id"],
                ),
            )

            return False

        conn.execute(
            """
            INSERT INTO deals (

                title,
                category,
                base_price,
                coupon_discount,
                payment_bonus,
                effective_price,
                shop_name,
                affiliate_link,
                coupon_code,
                description,
                source,
                source_id,
                status,
                created_at,
                updated_at

            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                category,
                base_price,
                coupon_discount,
                payment_bonus,
                effective_price,
                shop_name,
                affiliate_link,
                coupon_code,
                description,
                source,
                source_id,
                status,
                timestamp,
                timestamp,
            ),
        )

        return True


# ============================================================
# AWIN
# ============================================================

def awin_headers() -> dict:

    if not AWIN_API_TOKEN:

        raise RuntimeError(
            "AWIN_API_TOKEN fehlt."
        )

    return {
        "Authorization":
            f"Bearer {AWIN_API_TOKEN}",
        "Content-Type":
            "application/json",
        "Accept":
            "application/json",
    }


def import_awin_offers() -> int:

    if not AWIN_PUBLISHER_ID:

        raise RuntimeError(
            "AWIN_PUBLISHER_ID fehlt."
        )

    if not AWIN_API_TOKEN:

        raise RuntimeError(
            "AWIN_API_TOKEN fehlt."
        )

    url = (
        f"{AWIN_API_BASE}"
        f"/publisher/{AWIN_PUBLISHER_ID}"
        f"/promotions"
    )

    payload = {
        "filters": {
            "membership": "joined",
            "status": "active",
            "type": "all",
        },
        "pagination": {
            "page": 1,
            "pageSize": 200,
        },
    }

    response = requests.post(
        url,
        headers=awin_headers(),
        json=payload,
        timeout=HTTP_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    # AWIN-Antwort kann je nach API-Version
    # unterschiedlich verschachtelt sein

    offers = []

    if isinstance(data, list):

        offers = data

    elif isinstance(data, dict):

        offers = (
            data.get("offers")
            or data.get("promotions")
            or data.get("content")
            or []
        )

    imported = 0

    for offer in offers:

        if not isinstance(offer, dict):
            continue

        advertiser = offer.get(
            "advertiser",
            {}
        )

        if not isinstance(
            advertiser,
            dict,
        ):
            advertiser = {}

        title = first_value(
            offer,
            [
                "title",
                "name",
            ],
            "AWIN Angebot",
        )

        description = first_value(
            offer,
            [
                "description",
                "terms",
            ],
            "",
        )

        offer_type = first_value(
            offer,
            ["type"],
            "promotion",
        )

        coupon_code = first_value(
            offer,
            [
                "voucherCode",
                "voucher_code",
                "code",
            ],
            "",
        )

        advertiser_name = first_value(
            advertiser,
            ["name"],
            "AWIN Shop",
        )

        advertiser_id = first_value(
            advertiser,
            ["id"],
            "",
        )

        tracking_url = first_value(
            offer,
            [
                "urlTracking",
                "trackingUrl",
            ],
            "",
        )

        destination_url = first_value(
            offer,
            [
                "url",
                "destinationUrl",
            ],
            "",
        )

        # Bevorzugt AWIN Tracking URL
        affiliate_link = (
            tracking_url
            or destination_url
            or ""
        )

        promotion_id = first_value(
            offer,
            [
                "promotionId",
                "id",
            ],
            "",
        )

        source_id = make_source_id(
            "awin",
            promotion_id,
            advertiser_id,
        )

        created = upsert_deal(
            title=title,
            category=(
                "Rabattcode"
                if offer_type == "voucher"
                else "Aktion"
            ),
            base_price=0.0,
            coupon_discount=0.0,
            payment_bonus=0.0,
            shop_name=advertiser_name,
            affiliate_link=affiliate_link,
            coupon_code=coupon_code,
            description=description,
            source="awin",
            source_id=source_id,
            status="draft",
        )

        if created:
            imported += 1

    return imported


# ============================================================
# AWIN DEEPLINK
# ============================================================

def generate_awin_link(
    advertiser_id: int,
    destination_url: str,
) -> str:

    if not AWIN_PUBLISHER_ID:
        raise RuntimeError(
            "AWIN_PUBLISHER_ID fehlt."
        )

    url = (
        f"{AWIN_API_BASE}"
        f"/publishers/{AWIN_PUBLISHER_ID}"
        f"/linkbuilder/generate"
    )

    payload = {
        "advertiserId": advertiser_id,
        "destinationUrl": destination_url,
        "shorten": False,
    }

    response = requests.post(
        url,
        headers=awin_headers(),
        json=payload,
        timeout=HTTP_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    tracking_url = data.get("url")

    if not tracking_url:

        raise RuntimeError(
            "AWIN hat keinen Tracking-Link zurückgegeben."
        )

    return tracking_url


# ============================================================
# TRADEDOUBLER PRODUCTS
# ============================================================

def get_tradedoubler_feeds() -> list[dict]:

    if not TRADEDOUBLER_PRODUCTS_TOKEN:

        raise RuntimeError(
            "TRADEDOUBLER_PRODUCTS_TOKEN fehlt."
        )

    url = (
        f"{TRADEDOUBLER_API_BASE}"
        f"/productFeeds.json"
    )

    response = requests.get(
        url,
        params={
            "token":
                TRADEDOUBLER_PRODUCTS_TOKEN,
        },
        timeout=HTTP_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    if isinstance(data, dict):

        return data.get(
            "feeds",
            []
        )

    return []


def get_tradedoubler_products(
    feed_id: int,
) -> list[dict]:

    url = (
        f"{TRADEDOUBLER_API_BASE}"
        f"/products.json;fid={feed_id}"
        f";limit={MAX_PRODUCTS_PER_FEED}"
    )

    response = requests.get(
        url,
        params={
            "token":
                TRADEDOUBLER_PRODUCTS_TOKEN,
        },
        timeout=HTTP_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    if isinstance(data, list):

        return data

    if isinstance(data, dict):

        return (
            data.get("products")
            or data.get("product")
            or []
        )

    return []


def import_tradedoubler_products() -> int:

    feeds = get_tradedoubler_feeds()

    imported = 0

    for feed in feeds:

        if not isinstance(feed, dict):
            continue

        if not feed.get(
            "active",
            True,
        ):
            continue

        feed_id = first_value(
            feed,
            ["feedId", "id"],
        )

        if not feed_id:
            continue

        products = (
            get_tradedoubler_products(
                int(feed_id)
            )
        )

        for product in products:

            if not isinstance(
                product,
                dict,
            ):
                continue

            title = first_value(
                product,
                [
                    "name",
                    "title",
                    "productName",
                ],
                "",
            )

            if not title:
                continue

            price = first_value(
                product,
                [
                    "price",
                    "salePrice",
                    "lowestPrice",
                ],
                0,
            )

            category = first_value(
                product,
                [
                    "category",
                    "categoryName",
                ],
                "Produkte",
            )

            shop_name = first_value(
                product,
                [
                    "programName",
                    "merchantName",
                    "advertiserName",
                    "shopName",
                ],
                "TradeDoubler Shop",
            )

            # Wir bevorzugen explizite Tracking-Links.
            # Falls die API nur eine normale Produkt-URL liefert,
            # bleibt der Deal als Draft.

            affiliate_link = first_value(
                product,
                [
                    "trackingUrl",
                    "trackingURL",
                    "affiliateUrl",
                    "clickUrl",
                ],
                "",
            )

            description = first_value(
                product,
                [
                    "description",
                    "shortDescription",
                ],
                "",
            )

            product_id = first_value(
                product,
                [
                    "id",
                    "productId",
                    "sku",
                ],
                "",
            )

            source_id = make_source_id(
                "tradedoubler",
                feed_id,
                product_id,
                title,
            )

            created = upsert_deal(
                title=title,
                category=category,
                base_price=safe_float(price),
                coupon_discount=0.0,
                payment_bonus=0.0,
                shop_name=shop_name,
                affiliate_link=affiliate_link,
                description=description,
                source="tradedoubler_product",
                source_id=source_id,
                status="draft",
            )

            if created:
                imported += 1

    return imported


# ============================================================
# TRADEDOUBLER VOUCHERS
# ============================================================

def import_tradedoubler_vouchers() -> int:

    if not TRADEDOUBLER_VOUCHERS_TOKEN:

        raise RuntimeError(
            "TRADEDOUBLER_VOUCHERS_TOKEN fehlt."
        )

    url = (
        f"{TRADEDOUBLER_API_BASE}"
        f"/vouchers.json"
    )

    response = requests.get(
        url,
        params={
            "token":
                TRADEDOUBLER_VOUCHERS_TOKEN,
        },
        timeout=HTTP_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    vouchers = []

    if isinstance(data, list):

        vouchers = data

    elif isinstance(data, dict):

        vouchers = (
            data.get("vouchers")
            or data.get("voucher")
            or []
        )

    imported = 0

    for voucher in vouchers:

        if not isinstance(
            voucher,
            dict,
        ):
            continue

        title = first_value(
            voucher,
            [
                "title",
                "name",
            ],
            "TradeDoubler Gutschein",
        )

        code = first_value(
            voucher,
            [
                "code",
                "voucherCode",
            ],
            "",
        )

        description = first_value(
            voucher,
            [
                "shortDescription",
                "description",
            ],
            "",
        )

        shop_name = first_value(
            voucher,
            [
                "programName",
                "advertiserName",
            ],
            "TradeDoubler Shop",
        )

        affiliate_link = first_value(
            voucher,
            [
                "trackingUrl",
                "url",
                "landingPage",
            ],
            "",
        )

        voucher_id = first_value(
            voucher,
            [
                "id",
                "voucherId",
            ],
            "",
        )

        source_id = make_source_id(
            "tradedoubler_voucher",
            voucher_id,
            code,
            shop_name,
        )

        created = upsert_deal(
            title=title,
            category="Rabattcode",
            base_price=0.0,
            coupon_discount=0.0,
            payment_bonus=0.0,
            shop_name=shop_name,
            affiliate_link=affiliate_link,
            coupon_code=code,
            description=description,
            source="tradedoubler_voucher",
            source_id=source_id,
            status="draft",
        )

        if created:
            imported += 1

    return imported



# ============================================================
# TOPPREISE – BELIEBTE PRODUKTE ALS NACHFRAGE-SIGNAL
# ============================================================

class _ToppreiseTextParser(HTMLParser):
    """Kleiner stdlib-Parser, damit keine zusätzliche Dependency nötig ist."""

    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.parts.append(text)

    @property
    def text(self) -> str:
        return "\n".join(self.parts)


def normalize_toppreise_title(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    value = re.sub(r"^(?:Top 100|Topprodukte|Beliebte Produkte)\s*", "", value, flags=re.I)
    return value[:300]


def parse_chf_price(value: str) -> float:
    value = (value or "").replace("'", "").replace("’", "")
    value = value.replace(" ", "").replace(",", ".")
    return safe_float(value)


def scrape_toppreise_products(source_url: str = TOPPREISE_URL, max_products: int = TOPPREISE_MAX_PRODUCTS) -> list[dict]:
    """Liest Toppreise als Popularitäts-/Trendquelle.

    Der Parser ist bewusst tolerant, weil sich das Markup einer fremden Seite
    ändern kann. Bei einer Änderung bleibt der Import als Fehler im Admin-Log
    sichtbar statt die Anwendung zu stoppen.
    """

    response = requests.get(
        source_url,
        headers={
            "User-Agent": TOPPREISE_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "de-CH,de;q=0.9,en;q=0.7",
        },
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()

    parser = _ToppreiseTextParser()
    parser.feed(response.text)
    text = parser.text

    # Die Seite enthält Produktname gefolgt von "ab CHF ..." bzw.
    # in der englischen Variante "from CHF ...".
    pattern = re.compile(
        r"(?P<title>[A-Za-z0-9ÄÖÜäöüÀ-ÿ][^\n]{2,260}?)\s+"
        r"(?:ab|from)\s+CHF\s*(?P<price>[0-9'’.,]+)",
        re.IGNORECASE,
    )

    blocked = {
        "toppreise", "top 100", "topbewertungen", "neue produkte", "neue toppreise",
        "shops", "marken", "black friday", "verfügbarkeit",
    }
    products: list[dict] = []
    seen: set[str] = set()

    for match in pattern.finditer(text):
        title = normalize_toppreise_title(match.group("title"))
        price = parse_chf_price(match.group("price"))
        key = title.casefold()

        if (
            len(title) < 4
            or key in seen
            or any(title.casefold() == item for item in blocked)
        ):
            continue

        # Navigationstexte oder offensichtlich lange Sammeltexte aussortieren.
        if title.count(" ") > 32:
            continue

        seen.add(key)
        products.append(
            {
                "title": title,
                "price": price,
                "source_url": source_url,
            }
        )

        if len(products) >= max_products:
            break

    if not products:
        raise RuntimeError(
            "Toppreise-Seite wurde geladen, aber keine Produkte konnten "
            "aus dem aktuellen Seitenformat erkannt werden."
        )

    return products


def _meaningful_tokens(value: str) -> set[str]:
    stopwords = {
        "der", "die", "das", "und", "mit", "für", "von", "the",
        "edition", "digital", "black", "white", "schwarz", "weiss",
        "grau", "blue", "pro", "plus", "gb", "tb", "chf",
    }
    tokens = re.findall(r"[A-Za-zÄÖÜäöü0-9]{3,}", (value or "").casefold())
    return {token for token in tokens if token not in stopwords}


def find_coupon_matches(product_title: str, limit: int = 3) -> list[dict]:
    """Sucht bereits importierte Gutscheine, die semantisch zum Produkt passen.

    Ohne Händlerzuordnung darf ein Gutschein nicht als garantiert gültig
    dargestellt werden. Deshalb werden Treffer nur als "zu prüfen" markiert.
    """

    product_tokens = _meaningful_tokens(product_title)
    if not product_tokens:
        return []

    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, title, shop_name, coupon_code, description, source
            FROM deals
            WHERE coupon_code IS NOT NULL
              AND TRIM(coupon_code) <> ''
            ORDER BY updated_at DESC
            LIMIT 2000
            """
        ).fetchall()

    matches: list[tuple[int, dict]] = []

    for row in rows:
        haystack = " ".join(
            str(row[key] or "")
            for key in ("title", "shop_name", "description")
        )
        overlap = product_tokens & _meaningful_tokens(haystack)
        score = len(overlap)

        # Ein einzelnes Markenwort ist oft zu unsicher.
        if score >= 2:
            matches.append((score, dict(row)))

    matches.sort(key=lambda item: item[0], reverse=True)
    return [row for _, row in matches[:limit]]


def import_toppreise_products(
    source: str = "toppreise",
    source_url: str = TOPPREISE_URL,
    max_products: int = TOPPREISE_MAX_PRODUCTS,
    trend_label: str = "Toppreise Popularitätsrang",
) -> int:
    products = scrape_toppreise_products(source_url, max_products)
    imported = 0

    for rank, product in enumerate(products, start=1):
        title = product["title"]
        price = safe_float(product.get("price"))
        matches = find_coupon_matches(title)

        coupon_code = ""
        description_parts = [
            f"{trend_label}: #{rank}. ",
            "Produkt wurde als stark nachgefragt erkannt.",
        ]

        if matches:
            # Nur den besten Kandidaten anzeigen; der Deal bleibt Draft,
            # damit der Admin die tatsächliche Gutschein-Gültigkeit prüft.
            best = matches[0]
            coupon_code = str(best.get("coupon_code") or "")
            description_parts.append(
                f" Gutschein-Kandidat gefunden bei {best.get('shop_name') or 'unbekanntem Shop'} "
                f"(Quelle: {best.get('source')}). Bitte vor Veröffentlichung prüfen."
            )
        else:
            description_parts.append(
                " Kein passender Rabattcode in den aktuell importierten Gutscheinquellen gefunden."
            )

        source_id = make_source_id(source, title)
        timestamp = now_iso()

        with get_db() as conn:
            existing = conn.execute(
                """
                SELECT id FROM deals
                WHERE source = ? AND source_id = ?
                """,
                (source, source_id),
            ).fetchone()

            values = (
                title,
                "Topprodukt",
                price,
                0.0,
                0.0,
                price,
                "Toppreise.ch",
                "",
                coupon_code,
                "".join(description_parts),
                rank,
                product.get("source_url") or source_url,
                timestamp,
                timestamp,
            )

            if existing:
                conn.execute(
                    """
                    UPDATE deals
                    SET title = ?, category = ?, base_price = ?,
                        coupon_discount = ?, payment_bonus = ?, effective_price = ?,
                        shop_name = ?, affiliate_link = ?, coupon_code = ?,
                        description = ?, popularity_rank = ?, source_url = ?,
                        last_checked_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    values + (existing["id"],),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO deals (
                        title, category, base_price, coupon_discount,
                        payment_bonus, effective_price, shop_name,
                        affiliate_link, coupon_code, description,
                        source, source_id, status, created_at, updated_at,
                        popularity_rank, source_url, last_checked_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)
                    """,
                    (
                        title, "Topprodukt", price, 0.0, 0.0, price,
                        "Toppreise.ch", "", coupon_code,
                        "".join(description_parts), source, source_id,
                        timestamp, timestamp, rank,
                        product.get("source_url") or source_url,
                        timestamp,
                    ),
                )
                imported += 1

    return imported



# ============================================================
# TREND → AFFILIATE-MATCHING
# ============================================================

def title_match_score(a: str, b: str) -> float:
    """Bewertet, ob ein Trendprodukt zu einem Affiliate-Produkt passt."""
    a_tokens = _meaningful_tokens(a)
    b_tokens = _meaningful_tokens(b)
    if not a_tokens or not b_tokens:
        return 0.0

    overlap = len(a_tokens & b_tokens)
    union = len(a_tokens | b_tokens)
    jaccard = overlap / union if union else 0.0
    sequence = SequenceMatcher(None, (a or '').casefold(), (b or '').casefold()).ratio()

    # Exakte Modell-/Markenüberschneidungen sind wichtiger als reine Zeichenähnlichkeit.
    return (overlap * 10.0) + (jaccard * 10.0) + sequence


def find_affiliate_match(product_title: str) -> Optional[dict]:
    """Findet unter bereits importierten Affiliate-Angeboten den besten Kandidaten.

    Es wird ausschliesslich auf lokal vorhandene Daten gematcht. Damit werden
    keine fremden Suchseiten automatisiert abgefragt.
    """
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM deals
            WHERE source IN ('awin', 'tradedoubler_product')
              AND affiliate_link LIKE 'http%'
            ORDER BY updated_at DESC
            LIMIT 5000
            """
        ).fetchall()

    best = None
    best_score = 0.0
    for row in rows:
        score = title_match_score(product_title, str(row['title'] or ''))
        if score > best_score:
            best_score = score
            best = dict(row)

    # Mindestens zwei sinnvolle gemeinsame Tokens oder ein sehr ähnlicher Titel.
    if best and best_score >= 13.0:
        best['_match_score'] = round(best_score, 2)
        return best
    return None


def find_coupon_for_shop(shop_name: str) -> Optional[dict]:
    shop_tokens = _meaningful_tokens(shop_name)
    if not shop_tokens:
        return None
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT id, title, shop_name, coupon_code, description, source
            FROM deals
            WHERE coupon_code IS NOT NULL AND TRIM(coupon_code) <> ''
            ORDER BY updated_at DESC
            LIMIT 3000
            """
        ).fetchall()
    best = None
    best_score = 0
    for row in rows:
        score = len(shop_tokens & _meaningful_tokens(str(row['shop_name'] or '')))
        if score > best_score:
            best_score = score
            best = dict(row)
    return best if best_score >= 1 else None


def enrich_trend_products_with_affiliates() -> int:
    """Verbindet Trend-Signale mit lokal importierten Affiliate-Produkten.

    Ein Treffer bleibt immer Entwurf und wird nie automatisch veröffentlicht.
    """
    changed = 0
    with get_db() as conn:
        trends = conn.execute(
            """
            SELECT * FROM deals
            WHERE source IN ('toppreise', 'toppreise_new')
              AND status = 'draft'
            ORDER BY updated_at DESC
            LIMIT 500
            """
        ).fetchall()

    for trend in trends:
        match = find_affiliate_match(str(trend['title']))
        if not match:
            continue
        coupon = find_coupon_for_shop(str(match.get('shop_name') or ''))
        coupon_code = str(coupon.get('coupon_code') or '') if coupon else str(trend['coupon_code'] or '')
        price = safe_float(match.get('base_price')) or safe_float(trend['base_price'])
        description = (
            f"Trend-Signal aus Toppreise. Affiliate-Produkt lokal gematcht "
            f"(Score {match['_match_score']}) bei {match.get('shop_name')}. "
            "Vor Veröffentlichung Preis, Verfügbarkeit und Gutschein prüfen."
        )
        if coupon:
            description += f" Gutschein-Kandidat: {coupon_code} (Quelle: {coupon.get('source')})."

        with get_db() as conn:
            conn.execute(
                """
                UPDATE deals
                SET category = ?, base_price = ?, effective_price = ?, shop_name = ?,
                    affiliate_link = ?, coupon_code = ?, description = ?,
                    last_checked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    'Trend-Deal Kandidat', price, price,
                    str(match.get('shop_name') or trend['shop_name']),
                    str(match.get('affiliate_link') or ''), coupon_code,
                    description, now_iso(), now_iso(), trend['id'],
                ),
            )
        changed += 1
    return changed


def configured_status(configured: bool) -> str:
    return 'configured' if configured else 'not_configured'

# ============================================================
# ALLE QUELLEN SYNCHRONISIEREN
# ============================================================

def sync_all_sources() -> dict:
    result = {
        "awin": 0,
        "tradedoubler_products": 0,
        "tradedoubler_vouchers": 0,
        "toppreise": 0,
        "toppreise_new": 0,
        "trend_affiliate_matches": 0,
        "errors": [],
        "sources": {
            "awin": {"status": configured_status(bool(AWIN_PUBLISHER_ID and AWIN_API_TOKEN)), "message": ""},
            "tradedoubler_products": {"status": configured_status(bool(TRADEDOUBLER_PRODUCTS_TOKEN)), "message": ""},
            "tradedoubler_vouchers": {"status": configured_status(bool(TRADEDOUBLER_VOUCHERS_TOKEN)), "message": ""},
            "toppreise": {"status": "disabled" if not TOPPREISE_ENABLED else "pending", "message": ""},
            "toppreise_new": {"status": "disabled" if not TOPPREISE_NEW_ENABLED else "pending", "message": ""},
        },
    }

    def run_source(key: str, label: str, enabled: bool, func):
        if not enabled:
            return
        try:
            count = func()
            result[key] = count
            result["sources"][key] = {"status": "success", "message": f"{count} verarbeitet"}
            log_import(key, "success", f"{label} erfolgreich verarbeitet.", count)
        except Exception as exc:
            message = str(exc)
            result["errors"].append(f"{label}: {message}")
            result["sources"][key] = {"status": "error", "message": message}
            log_import(key, "error", message)

    run_source(
        "awin", "AWIN", bool(AWIN_PUBLISHER_ID and AWIN_API_TOKEN), import_awin_offers
    )
    run_source(
        "tradedoubler_products", "TradeDoubler Produkte", bool(TRADEDOUBLER_PRODUCTS_TOKEN), import_tradedoubler_products
    )
    run_source(
        "tradedoubler_vouchers", "TradeDoubler Gutscheine", bool(TRADEDOUBLER_VOUCHERS_TOKEN), import_tradedoubler_vouchers
    )

    # Wichtig: beide Toppreise-Quellen laufen unabhängig voneinander.
    run_source(
        "toppreise", "Toppreise Topprodukte", TOPPREISE_ENABLED,
        lambda: import_toppreise_products(
            source="toppreise", source_url=TOPPREISE_URL,
            max_products=TOPPREISE_MAX_PRODUCTS,
            trend_label="Toppreise Popularitätsrang",
        ),
    )
    run_source(
        "toppreise_new", "Toppreise Neue Toppreise", TOPPREISE_NEW_ENABLED,
        lambda: import_toppreise_products(
            source="toppreise_new", source_url=TOPPREISE_NEW_URL,
            max_products=TOPPREISE_NEW_MAX_PRODUCTS,
            trend_label="Toppreise Neue-Toppreise-Rang",
        ),
    )

    # Matching nur nach erfolgreichen Importen vorhandener Affiliate-Daten.
    try:
        result["trend_affiliate_matches"] = enrich_trend_products_with_affiliates()
        log_import("trend_affiliate_matching", "success", "Trendprodukte mit lokalen Affiliate-Angeboten abgeglichen.", result["trend_affiliate_matches"])
    except Exception as exc:
        result["errors"].append(f"Trend/Affiliate-Matching: {exc}")
        log_import("trend_affiliate_matching", "error", str(exc))

    return result

# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():

    try:

        with get_db() as conn:

            conn.execute(
                "SELECT 1"
            )

        return JSONResponse(
            {
                "status": "healthy",
                "database": "connected",
                "awin_configured": bool(
                    AWIN_API_TOKEN
                ),
                "tradedoubler_products_configured":
                    bool(
                        TRADEDOUBLER_PRODUCTS_TOKEN
                    ),
                "tradedoubler_vouchers_configured":
                    bool(
                        TRADEDOUBLER_VOUCHERS_TOKEN
                    ),
                "toppreise_enabled": TOPPREISE_ENABLED,
                "toppreise_new_enabled": TOPPREISE_NEW_ENABLED,
            }
        )

    except Exception as exc:

        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(exc),
            },
        )


# ============================================================
# HOMEPAGE
# ============================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>NettoDeals.ch – Schweizer Deals</title>

<script src="https://cdn.tailwindcss.com"></script>

</head>


<body class="bg-slate-50 text-slate-900 min-h-screen flex flex-col">


<header class="bg-white border-b border-slate-200">

<div class="max-w-7xl mx-auto px-4 py-5 flex justify-between items-center">

<div>

<h1 class="text-2xl font-black text-indigo-600">

Netto<span class="text-slate-900">Deals</span>

<span class="text-xs bg-indigo-100 text-indigo-700 px-2 py-1 rounded-full">
CH
</span>

</h1>

</div>


<p class="text-sm text-slate-500 hidden md:block">

Der echte Endpreis nach Gutscheinen & Aktionen

</p>

</div>

</header>


<main class="max-w-7xl mx-auto px-4 py-8 w-full flex-grow">


<div class="flex justify-between items-center mb-6">

<div>

<h2 class="text-2xl font-bold">

Aktuelle Top-Deals

</h2>

<p class="text-sm text-slate-500 mt-1">

{{ deals|length }} veröffentlichte Angebote

</p>

</div>

</div>


{% if deals %}

<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">

{% for deal in deals %}

<article class="bg-white rounded-2xl border border-slate-200 p-5 shadow-sm flex flex-col">


<div class="flex justify-between gap-3 mb-3">

<span class="text-xs font-semibold bg-indigo-50 text-indigo-700 px-2 py-1 rounded">

{{ deal["category"] }}

</span>


<span class="text-xs text-slate-500">

{{ deal["shop_name"] }}

</span>

</div>


<h3 class="font-bold text-lg mb-3">

{{ deal["title"] }}

</h3>


{% if deal["description"] %}

<p class="text-sm text-slate-500 mb-4">

{{ deal["description"] }}

</p>

{% endif %}


{% if deal["coupon_code"] %}

<div class="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-4">

<div class="text-xs text-amber-700">

Rabattcode

</div>

<div class="font-bold text-amber-900">

{{ deal["coupon_code"] }}

</div>

</div>

{% endif %}


<div class="mt-auto pt-4 border-t border-slate-100">


{% if deal["base_price"] > 0 %}

<div class="text-sm text-slate-400 line-through">

CHF {{ "%.2f"|format(deal["base_price"]) }}

</div>


<div class="text-2xl font-black text-indigo-600">

CHF {{ "%.2f"|format(deal["effective_price"]) }}

</div>

{% else %}

<div class="text-sm font-semibold text-indigo-600">

Aktion ansehen

</div>

{% endif %}


{% if deal["affiliate_link"] %}

<a
href="{{ deal["affiliate_link"] }}"
target="_blank"
rel="nofollow sponsored noopener noreferrer"
class="block mt-4 text-center bg-slate-900 hover:bg-slate-800 text-white font-semibold py-3 rounded-xl"
>

Zum Deal →

</a>

{% endif %}

</div>

</article>

{% endfor %}

</div>


{% else %}

<div class="bg-white border border-slate-200 rounded-2xl p-12 text-center">

<h3 class="font-bold text-lg">

Noch keine Deals veröffentlicht

</h3>

<p class="text-slate-500 mt-2">

Neue Angebote werden automatisch geprüft.

</p>

</div>

{% endif %}


</main>


<footer class="bg-white border-t border-slate-200 py-6 text-center text-xs text-slate-400">

© 2026 NettoDeals.ch

</footer>


</body>

</html>
"""


@app.get(
    "/",
    response_class=HTMLResponse,
)
def read_root():

    with get_db() as conn:

        deals = conn.execute(
            """
            SELECT *
            FROM deals

            WHERE status = 'published'

            ORDER BY
                effective_price ASC,
                updated_at DESC
            """
        ).fetchall()

    template = Template(
        HTML_TEMPLATE
    )

    return HTMLResponse(
        template.render(
            deals=deals
        )
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NettoDeals Admin</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-100 text-slate-900">
<div class="max-w-7xl mx-auto px-4 py-8">
  <div class="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-8">
    <div>
      <h1 class="text-3xl font-black">NettoDeals Admin</h1>
      <p class="text-slate-500">Trendprodukte, Gutschein-Abgleich und Deal-Freigabe</p>
    </div>
    <a href="/" class="text-sm text-indigo-600 font-semibold">↗ Öffentliche Seite</a>
  </div>

  {% if sync_result %}
  <div class="bg-indigo-50 border border-indigo-200 rounded-xl p-5 mb-6">
    <div class="font-bold text-indigo-900 mb-2">Synchronisierung abgeschlossen</div>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
      <div>AWIN: <strong>{{ sync_result["awin"] }}</strong></div>
      <div>TradeDoubler Produkte: <strong>{{ sync_result["tradedoubler_products"] }}</strong></div>
      <div>TradeDoubler Gutscheine: <strong>{{ sync_result["tradedoubler_vouchers"] }}</strong></div>
      <div>Toppreise Topprodukte: <strong>{{ sync_result["toppreise"] }}</strong></div>
      <div>Toppreise Neue Toppreise: <strong>{{ sync_result["toppreise_new"] }}</strong></div>
      <div>Trend → Affiliate Matches: <strong>{{ sync_result["trend_affiliate_matches"] }}</strong></div>
    </div>
    <div class="mt-4 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
      {% for name, info in sync_result["sources"].items() %}
      <div class="border rounded-lg px-3 py-2 bg-white">
        <strong>{{ name }}</strong> · {{ info["status"] }}{% if info["message"] %} · {{ info["message"] }}{% endif %}
      </div>
      {% endfor %}
    </div>
    {% if sync_result["errors"] %}
      <div class="mt-3 text-sm text-red-700">
        {% for error in sync_result["errors"] %}<div>⚠ {{ error }}</div>{% endfor %}
      </div>
    {% endif %}
  </div>
  {% endif %}

  <section class="bg-white rounded-xl border p-6 mb-8">
    <div class="flex flex-col md:flex-row gap-4 md:items-end">
      <div class="flex-1">
        <label class="block text-sm font-semibold mb-2">Admin Token</label>
        <input id="admin-token" type="password" class="w-full border rounded-lg px-3 py-2" placeholder="ADMIN_TOKEN" autocomplete="current-password">
        <p class="text-xs text-slate-400 mt-2">Der Token bleibt nur in diesem Browser (localStorage) und wird bei jeder Admin-Aktion mitgesendet.</p>
      </div>
      <form action="/admin/sync" method="post" onsubmit="return attachToken(this)">
        <input type="hidden" name="admin_token">
        <button class="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-3 rounded-lg font-semibold">🔄 Quellen synchronisieren</button>
      </form>
    </div>
    <div id="token-status" class="text-xs mt-3"></div>
  </section>

  <section class="grid grid-cols-1 md:grid-cols-6 gap-4 mb-8">
    <div class="bg-white rounded-xl border p-4"><div class="text-xs text-slate-500">Entwürfe</div><div class="text-2xl font-black">{{ stats.drafts }}</div></div>
    <div class="bg-white rounded-xl border p-4"><div class="text-xs text-slate-500">Veröffentlicht</div><div class="text-2xl font-black">{{ stats.published }}</div></div>
    <div class="bg-white rounded-xl border p-4"><div class="text-xs text-slate-500">Toppreise Topprodukte</div><div class="text-2xl font-black">{{ stats.toppreise }}</div></div>
    <div class="bg-white rounded-xl border p-4"><div class="text-xs text-slate-500">Neue Toppreise</div><div class="text-2xl font-black">{{ stats.toppreise_new }}</div></div>
    <div class="bg-white rounded-xl border p-4"><div class="text-xs text-slate-500">Gutschein-Kandidaten</div><div class="text-2xl font-black">{{ stats.coupon_candidates }}</div></div>
    <div class="bg-white rounded-xl border p-4"><div class="text-xs text-slate-500">Affiliate-Matches</div><div class="text-2xl font-black">{{ stats.affiliate_matches }}</div></div>
  </section>

  <section class="bg-white rounded-xl border p-6 mb-8">
    <h2 class="text-xl font-bold mb-4">Manuellen Deal anlegen</h2>
    <form action="/admin/deals/create" method="post" onsubmit="return attachToken(this)" class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <input type="hidden" name="admin_token">
      <input required name="title" class="border rounded-lg px-3 py-2" placeholder="Deal-Titel">
      <input required name="shop_name" class="border rounded-lg px-3 py-2" placeholder="Shop">
      <input name="affiliate_link" class="border rounded-lg px-3 py-2" placeholder="Affiliate-/Deal-Link (https://...)">
      <input name="coupon_code" class="border rounded-lg px-3 py-2" placeholder="Rabattcode (optional)">
      <input name="base_price" type="number" step="0.01" class="border rounded-lg px-3 py-2" placeholder="Preis in CHF">
      <input name="category" class="border rounded-lg px-3 py-2" value="Deals">
      <textarea name="description" class="border rounded-lg px-3 py-2 md:col-span-2" placeholder="Beschreibung / Bedingungen"></textarea>
      <div class="md:col-span-2"><button class="bg-slate-900 text-white px-5 py-3 rounded-lg font-semibold">Deal veröffentlichen</button></div>
    </form>
  </section>

  <div class="flex items-center justify-between mb-4">
    <div>
      <h2 class="text-xl font-bold">Entwürfe zur Prüfung</h2>
      <p class="text-sm text-slate-500">Toppreise-Einträge sind Nachfrage-Signale und werden nie automatisch veröffentlicht.</p>
    </div>
  </div>

  <div class="space-y-4">
  {% for deal in drafts %}
    <article class="bg-white border rounded-xl p-5">
      <div class="flex flex-col lg:flex-row lg:justify-between gap-5">
        <div class="min-w-0">
          <div class="flex flex-wrap gap-2 mb-2">
            <span class="text-xs bg-slate-100 px-2 py-1 rounded">{{ deal["source"] }}</span>
            {% if deal["popularity_rank"] %}<span class="text-xs bg-violet-100 text-violet-700 px-2 py-1 rounded">🔥 Rang #{{ deal["popularity_rank"] }}</span>{% endif %}
            {% if deal["coupon_code"] %}<span class="text-xs bg-amber-100 text-amber-800 px-2 py-1 rounded">🎟 Gutschein-Kandidat</span>{% endif %}
          </div>
          <h3 class="font-bold text-lg">{{ deal["title"] }}</h3>
          <p class="text-sm text-slate-500">{{ deal["shop_name"] }}{% if deal["base_price"] > 0 %} · ab CHF {{ "%.2f"|format(deal["base_price"]) }}{% endif %}</p>
          {% if deal["coupon_code"] %}<div class="mt-3 text-sm">Code: <strong>{{ deal["coupon_code"] }}</strong> <span class="text-amber-700">(vor Veröffentlichung prüfen)</span></div>{% endif %}
          {% if deal["description"] %}<p class="text-sm text-slate-600 mt-3">{{ deal["description"] }}</p>{% endif %}
          <div class="flex flex-wrap gap-4 mt-3 text-sm">
            {% if deal["affiliate_link"] %}<a href="{{ deal["affiliate_link"] }}" target="_blank" rel="noopener noreferrer" class="text-indigo-600">Affiliate-Link testen →</a>{% endif %}
            {% if deal["source_url"] %}<a href="{{ deal["source_url"] }}" target="_blank" rel="noopener noreferrer" class="text-indigo-600">Quelle öffnen →</a>{% endif %}
          </div>
        </div>
        <div class="flex lg:flex-col gap-2 shrink-0">
          <form action="/admin/deals/{{ deal["id"] }}/publish" method="post" onsubmit="return attachToken(this)"><input type="hidden" name="admin_token"><button class="bg-emerald-600 text-white px-4 py-2 rounded-lg">✓ Veröffentlichen</button></form>
          <form action="/admin/deals/{{ deal["id"] }}/delete" method="post" onsubmit="return attachToken(this)"><input type="hidden" name="admin_token"><button class="bg-red-600 text-white px-4 py-2 rounded-lg">✕ Löschen</button></form>
        </div>
      </div>
    </article>
  {% else %}
    <div class="bg-white border rounded-xl p-8 text-center text-slate-500">Noch keine Entwürfe vorhanden.</div>
  {% endfor %}
  </div>

  <section class="mt-10 bg-white rounded-xl border p-6">
    <h2 class="text-lg font-bold mb-3">Letzte Import-Logs</h2>
    <div class="space-y-2 text-sm">
    {% for log in logs %}
      <div class="flex flex-col md:flex-row md:justify-between gap-1 border-b pb-2">
        <div><strong>{{ log["source"] }}</strong> · {{ log["status"] }} · {{ log["message"] or "" }}</div>
        <div class="text-slate-400">{{ log["created_at"] }}</div>
      </div>
    {% else %}<div class="text-slate-500">Noch keine Logs.</div>{% endfor %}
    </div>
  </section>
</div>
<script>
const tokenInput = document.getElementById('admin-token');
const status = document.getElementById('token-status');
tokenInput.value = localStorage.getItem('nettodeals_admin_token') || '';
function refreshTokenStatus() {
  if (tokenInput.value) {
    status.textContent = '✓ Token im Browser bereit.';
    status.className = 'text-xs mt-3 text-emerald-600';
  } else {
    status.textContent = 'Kein Token gespeichert.';
    status.className = 'text-xs mt-3 text-slate-400';
  }
}
tokenInput.addEventListener('input', () => {
  if (tokenInput.value) localStorage.setItem('nettodeals_admin_token', tokenInput.value);
  else localStorage.removeItem('nettodeals_admin_token');
  refreshTokenStatus();
});
function attachToken(form) {
  const token = tokenInput.value.trim();
  if (!token) { alert('Bitte zuerst den Admin Token eingeben.'); tokenInput.focus(); return false; }
  localStorage.setItem('nettodeals_admin_token', token);
  form.querySelectorAll('input[name="admin_token"]').forEach(i => i.value = token);
  return true;
}
refreshTokenStatus();
</script>
</body>
</html>
"""


def load_admin_data() -> tuple[list[sqlite3.Row], dict, list[sqlite3.Row]]:
    with get_db() as conn:
        drafts = conn.execute(
            """
            SELECT * FROM deals
            WHERE status = 'draft'
            ORDER BY
                CASE WHEN popularity_rank IS NULL THEN 1 ELSE 0 END,
                popularity_rank ASC,
                updated_at DESC
            LIMIT 500
            """
        ).fetchall()

        stats = {
            "drafts": conn.execute("SELECT COUNT(*) FROM deals WHERE status = 'draft'").fetchone()[0],
            "published": conn.execute("SELECT COUNT(*) FROM deals WHERE status = 'published'").fetchone()[0],
            "toppreise": conn.execute("SELECT COUNT(*) FROM deals WHERE source = 'toppreise'").fetchone()[0],
            "toppreise_new": conn.execute("SELECT COUNT(*) FROM deals WHERE source = 'toppreise_new'").fetchone()[0],
            "coupon_candidates": conn.execute(
                "SELECT COUNT(*) FROM deals WHERE status = 'draft' AND coupon_code IS NOT NULL AND TRIM(coupon_code) <> ''"
            ).fetchone()[0],
            "affiliate_matches": conn.execute(
                "SELECT COUNT(*) FROM deals WHERE source IN ('toppreise', 'toppreise_new') AND affiliate_link LIKE 'http%'"
            ).fetchone()[0],
        }

        logs = conn.execute(
            "SELECT * FROM import_logs ORDER BY id DESC LIMIT 30"
        ).fetchall()

    return drafts, stats, logs


def render_admin(sync_result: Optional[dict] = None) -> HTMLResponse:
    drafts, stats, logs = load_admin_data()
    return HTMLResponse(
        Template(ADMIN_TEMPLATE).render(
            drafts=drafts,
            stats=stats,
            logs=logs,
            sync_result=sync_result,
        )
    )


@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return render_admin()


# ============================================================
# SYNC
# ============================================================

@app.post("/admin/sync", response_class=HTMLResponse)
def admin_sync(
    admin_token: str = Form(...),
):
    verify_admin_token(admin_token)
    result = sync_all_sources()
    return render_admin(sync_result=result)


# ============================================================
# DEAL VERÖFFENTLICHEN
# ============================================================

@app.post(
    "/admin/deals/{deal_id}/publish"
)
def publish_deal(
    deal_id: int,
    admin_token: str = Form(...),
):

    verify_admin_token(
        admin_token
    )

    with get_db() as conn:
        deal = conn.execute(
            "SELECT affiliate_link, source FROM deals WHERE id = ?",
            (deal_id,),
        ).fetchone()

        if not deal:
            raise HTTPException(status_code=404, detail="Deal nicht gefunden.")

        if not str(deal["affiliate_link"] or "").startswith(("http://", "https://")):
            raise HTTPException(
                status_code=400,
                detail="Ein Deal benötigt vor der Veröffentlichung einen gültigen Affiliate-/Deal-Link."
            )

        conn.execute(
            """
            UPDATE deals
            SET status = 'published', updated_at = ?
            WHERE id = ?
            """,
            (now_iso(), deal_id),
        )

    return RedirectResponse(
        url="/admin",
        status_code=303,
    )


# ============================================================
# DEAL LÖSCHEN
# ============================================================

@app.post(
    "/admin/deals/{deal_id}/delete"
)
def delete_deal(
    deal_id: int,
    admin_token: str = Form(...),
):

    verify_admin_token(
        admin_token
    )

    with get_db() as conn:

        conn.execute(
            """
            DELETE FROM deals
            WHERE id = ?
            """,
            (deal_id,),
        )

    return RedirectResponse(
        url="/admin",
        status_code=303,
    )


# ============================================================
# MANUELLER DEAL
# ============================================================

@app.post("/admin/deals/create")
def create_manual_deal(
    admin_token: str = Form(...),
    title: str = Form(...),
    category: str = Form("Deals"),
    base_price: float = Form(0.0),
    coupon_discount: float = Form(0.0),
    payment_bonus: float = Form(0.0),
    shop_name: str = Form(...),
    affiliate_link: str = Form(""),
    coupon_code: str = Form(""),
    description: str = Form(""),
):

    verify_admin_token(
        admin_token
    )

    upsert_deal(
        title=title,
        category=category,
        base_price=base_price,
        coupon_discount=coupon_discount,
        payment_bonus=payment_bonus,
        shop_name=shop_name,
        affiliate_link=affiliate_link,
        coupon_code=coupon_code,
        description=description,
        source="manual",
        source_id=make_source_id(
            "manual",
            title,
            affiliate_link,
        ),
        status="published",
    )

    return RedirectResponse(
        url="/admin",
        status_code=303,
    )


# ============================================================
# API STATUS
# ============================================================

@app.get("/api/status")
def api_status():

    return {

        "app": "NettoDeals",

        "awin": bool(
            AWIN_PUBLISHER_ID
            and AWIN_API_TOKEN
        ),

        "tradedoubler_products": bool(
            TRADEDOUBLER_PRODUCTS_TOKEN
        ),

        "tradedoubler_vouchers": bool(
            TRADEDOUBLER_VOUCHERS_TOKEN
        ),

        "toppreise_enabled": TOPPREISE_ENABLED,
        "toppreise_url": TOPPREISE_URL,
        "toppreise_new_enabled": TOPPREISE_NEW_ENABLED,
        "toppreise_new_url": TOPPREISE_NEW_URL,
        "toppreise_user_agent_configured": bool(TOPPREISE_USER_AGENT),

        "database": DB_PATH,

    }


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=APP_PORT,
        reload=False,
    )
