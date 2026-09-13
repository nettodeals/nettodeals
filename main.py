# main.py
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
import uvicorn
from bs4 import BeautifulSoup
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from jinja2 import Template


# ============================================================
# KONFIGURATION
# ============================================================

APP_PORT = int(os.getenv("APP_PORT", "8000"))
DB_PATH = os.getenv("DB_PATH", "/data/nettodeals.db")

TOPPREISE_URL = "https://www.toppreise.ch/topprodukte"

USER_AGENT = os.getenv(
    "SCRAPER_USER_AGENT",
    "NettoDeals.ch Deal Importer/1.0"
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="NettoDeals",
    version="2.0.0",
)


# ============================================================
# DATENBANK
# ============================================================

def ensure_db_directory():
    db_dir = os.path.dirname(DB_PATH)

    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    ensure_db_directory()

    with get_db() as conn:

        # Veröffentliche Deals
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                title TEXT NOT NULL,
                category TEXT NOT NULL,

                base_price REAL NOT NULL,

                coupon_code TEXT DEFAULT '',
                coupon_discount REAL NOT NULL DEFAULT 0,

                payment_bonus REAL NOT NULL DEFAULT 0,

                effective_price REAL NOT NULL,

                shop_name TEXT NOT NULL,

                affiliate_link TEXT NOT NULL,

                source_name TEXT DEFAULT 'manual',
                source_url TEXT DEFAULT '',

                created_at TEXT NOT NULL
            )
            """
        )

        # Importierte Kandidaten
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deal_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                title TEXT NOT NULL,
                base_price REAL NOT NULL DEFAULT 0,

                category TEXT DEFAULT 'Topprodukte',

                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL UNIQUE,

                imported_at TEXT NOT NULL,

                status TEXT NOT NULL DEFAULT 'pending'
            )
            """
        )


@app.on_event("startup")
def startup_event():
    init_db()


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_swiss_price(text: str):
    """
    Wandelt z.B.

    CHF 1'199.95
    CHF 999.00

    in float um.
    """

    if not text:
        return None

    match = re.search(
        r"CHF\s*([\d'’.,]+)",
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    value = match.group(1)

    value = value.replace("'", "")
    value = value.replace("’", "")
    value = value.replace(",", ".")

    try:
        return float(value)

    except ValueError:
        return None


def clean_product_title(text: str):
    """
    Entfernt Preisangaben aus dem Linktext.
    """

    text = re.sub(
        r"\s+ab\s+CHF\s+.*$",
        "",
        text,
        flags=re.IGNORECASE
    )

    return " ".join(text.split()).strip()


# ============================================================
# TOPPREISE IMPORT
# ============================================================

def fetch_toppreise_products(limit=100):

    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
    }

    response = requests.get(
        TOPPREISE_URL,
        headers=headers,
        timeout=20,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    products = []
    seen_urls = set()

    #
    # Wir suchen Links, deren Text eine CHF-Preisangabe enthält.
    #
    # Die genaue HTML-Struktur einer externen Website kann sich
    # ändern, deshalb ist dieser Import bewusst defensiv gebaut.
    #

    for link in soup.find_all("a", href=True):

        text = " ".join(
            link.get_text(" ", strip=True).split()
        )

        href = link.get("href")

        if not text:
            continue

        if "CHF" not in text:
            continue

        price = parse_swiss_price(text)

        if price is None:
            continue

        title = clean_product_title(text)

        if len(title) < 5:
            continue

        full_url = urljoin(
            TOPPREISE_URL,
            href
        )

        # Keine Duplikate
        if full_url in seen_urls:
            continue

        seen_urls.add(full_url)

        products.append(
            {
                "title": title,
                "base_price": price,
                "category": "Topprodukte",
                "source_name": "Toppreise.ch",
                "source_url": full_url,
            }
        )

        if len(products) >= limit:
            break

    return products


def import_toppreise(limit=100):

    products = fetch_toppreise_products(limit)

    imported = 0
    skipped = 0

    with get_db() as conn:

        for product in products:

            try:

                cursor = conn.execute(
                    """
                    INSERT OR IGNORE INTO deal_candidates (
                        title,
                        base_price,
                        category,
                        source_name,
                        source_url,
                        imported_at,
                        status
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 'pending')
                    """,
                    (
                        product["title"],
                        product["base_price"],
                        product["category"],
                        product["source_name"],
                        product["source_url"],
                        now_iso(),
                    ),
                )

                if cursor.rowcount > 0:
                    imported += 1
                else:
                    skipped += 1

            except Exception:
                skipped += 1

    return {
        "found": len(products),
        "imported": imported,
        "skipped": skipped,
    }


# ============================================================
# HTML
# ============================================================

HTML_TEMPLATE = """
<!DOCTYPE html>

<html lang="de">

<head>

<meta charset="UTF-8">

<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>NettoDeals.ch – Schweizer Deals</title>

<script src="https://cdn.tailwindcss.com"></script>

</head>


<body class="bg-slate-50 text-slate-800 min-h-screen flex flex-col">


<header class="bg-white border-b border-slate-200 sticky top-0 z-50">

<div class="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">

<div>

<a href="/" class="text-2xl font-black text-indigo-600 tracking-tight">

Netto<span class="text-slate-900">Deals</span>

<span class="text-xs align-super bg-indigo-100 text-indigo-800 px-1.5 py-0.5 rounded-full font-bold ml-1">

CH

</span>

</a>

</div>


<p class="text-sm text-slate-500 hidden sm:block">

Der echte Endpreis nach Gutscheinen & Zahlungs-Boni

</p>

</div>

</header>


<main class="max-w-6xl mx-auto px-4 py-8 flex-grow w-full grid grid-cols-1 lg:grid-cols-3 gap-8">


<!-- DEALS -->

<section class="lg:col-span-2 space-y-6">


<div class="flex justify-between items-center">

<h1 class="text-xl font-bold text-slate-900">

Aktuelle Top-Deals

</h1>


<span class="text-sm text-slate-500">

{{ deals|length }} Angebote gefunden

</span>

</div>


{% if deals %}

<div class="grid grid-cols-1 gap-4">


{% for deal in deals %}

<article class="bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition p-5">


<div class="flex justify-between items-start gap-3 mb-3">


<span class="text-xs font-semibold uppercase tracking-wider bg-slate-100 text-slate-600 px-2.5 py-1 rounded-md">

{{ deal["category"] }}

</span>


<span class="text-xs font-medium text-emerald-700 bg-emerald-50 px-2 py-1 rounded">

{{ deal["shop_name"] }}

</span>


</div>


<h2 class="text-lg font-bold text-slate-900 mb-3">

{{ deal["title"] }}

</h2>


{% if deal["coupon_code"] %}

<div class="mb-3">

<span class="text-xs bg-amber-50 text-amber-700 border border-amber-200 px-2 py-1 rounded">

Gutschein: {{ deal["coupon_code"] }}

</span>

</div>

{% endif %}


<div class="flex flex-wrap gap-2 mb-4">


{% if deal["coupon_discount"] > 0 %}

<span class="text-xs bg-amber-50 text-amber-700 border border-amber-200 px-2 py-1 rounded">

- CHF {{ "%.2f"|format(deal["coupon_discount"]) }}

</span>

{% endif %}


{% if deal["payment_bonus"] > 0 %}

<span class="text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-1 rounded">

Zahlungsbonus: - CHF {{ "%.2f"|format(deal["payment_bonus"]) }}

</span>

{% endif %}


</div>


<div class="pt-4 border-t border-slate-100 flex items-center justify-between">


<div>

<div class="text-xs text-slate-400 line-through">

CHF {{ "%.2f"|format(deal["base_price"]) }}

</div>


<div class="text-2xl font-black text-indigo-600">

CHF {{ "%.2f"|format(deal["effective_price"]) }}

</div>

</div>


<a

href="{{ deal["affiliate_link"] }}"

target="_blank"

rel="nofollow sponsored noopener noreferrer"

class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-5 py-2.5 rounded-lg text-sm"

>

Zum Deal →

</a>


</div>

</article>


{% endfor %}


</div>


{% else %}


<div class="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500">

Noch keine veröffentlichten Deals vorhanden.

</div>


{% endif %}


</section>


<!-- ADMIN -->

<aside>


<div class="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">


<h2 class="text-lg font-bold mb-4">

Admin

</h2>


<a

href="/admin"

class="block w-full text-center bg-slate-900 hover:bg-slate-800 text-white font-medium py-2.5 rounded-lg text-sm"

>

Deal-Verwaltung öffnen

</a>


</div>


<div class="bg-white rounded-xl border border-slate-200 p-6 shadow-sm mt-4">


<h2 class="text-lg font-bold mb-4">

Deal erfassen

</h2>


<form action="/deals" method="POST" class="space-y-4">


<input

type="text"

name="title"

required

placeholder="Titel"

class="w-full border border-slate-300 rounded-lg px-3 py-2"

/>


<input

type="text"

name="category"

required

value="Elektronik"

class="w-full border border-slate-300 rounded-lg px-3 py-2"

/>


<input

type="number"

step="0.01"

min="0"

name="base_price"

required

placeholder="Grundpreis CHF"

class="w-full border border-slate-300 rounded-lg px-3 py-2"

/>


<input

type="text"

name="coupon_code"

placeholder="Rabattcode"

class="w-full border border-slate-300 rounded-lg px-3 py-2"

/>


<input

type="number"

step="0.01"

min="0"

name="coupon_discount"

value="0"

placeholder="Gutschein-Rabatt"

class="w-full border border-slate-300 rounded-lg px-3 py-2"

/>


<input

type="number"

step="0.01"

min="0"

name="payment_bonus"

value="0"

placeholder="Zahlungsbonus"

class="w-full border border-slate-300 rounded-lg px-3 py-2"

/>


<input

type="text"

name="shop_name"

required

placeholder="Shop"

class="w-full border border-slate-300 rounded-lg px-3 py-2"

/>


<input

type="url"

name="affiliate_link"

required

placeholder="Dein Affiliate-Link"

class="w-full border border-slate-300 rounded-lg px-3 py-2"

/>


<button

type="submit"

class="w-full bg-indigo-600 hover:bg-indigo-700 text-white py-2.5 rounded-lg"

>

Deal speichern

</button>


</form>


</div>


</aside>


</main>


<footer class="bg-white border-t border-slate-200 mt-12 py-6 text-center text-xs text-slate-400">

© 2026 NettoDeals.ch

</footer>


</body>

</html>
"""


ADMIN_TEMPLATE = """
<!DOCTYPE html>

<html lang="de">

<head>

<meta charset="UTF-8">

<meta name="viewport" content="width=device-width, initial-scale=1.0">

<title>NettoDeals Admin</title>

<script src="https://cdn.tailwindcss.com"></script>

</head>


<body class="bg-slate-50 text-slate-800">


<div class="max-w-6xl mx-auto px-4 py-8">


<div class="flex justify-between items-center mb-8">

<h1 class="text-2xl font-bold">

NettoDeals Admin

</h1>


<a href="/" class="text-indigo-600">

← Zur Webseite

</a>

</div>


<div class="bg-white border rounded-xl p-6 mb-8">


<h2 class="text-lg font-bold mb-4">

Toppreise importieren

</h2>


<form action="/admin/import/toppreise" method="POST">

<button

class="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-3 rounded-lg"

>

Top-100 importieren

</button>

</form>


</div>


<h2 class="text-xl font-bold mb-4">

Importierte Kandidaten

</h2>


<div class="space-y-4">


{% for candidate in candidates %}


<div class="bg-white border rounded-xl p-5">


<div class="flex justify-between gap-4 mb-3">


<div>

<h3 class="font-bold">

{{ candidate["title"] }}

</h3>


<p class="text-sm text-slate-500">

Toppreise Preis: CHF {{ "%.2f"|format(candidate["base_price"]) }}

</p>

</div>


<a

href="{{ candidate["source_url"] }}"

target="_blank"

class="text-sm text-indigo-600"

>

Quelle öffnen →

</a>


</div>


<form

action="/admin/publish/{{ candidate["id"] }}"

method="POST"

class="grid grid-cols-1 md:grid-cols-2 gap-3"


>


<input

name="shop_name"

required

placeholder="Shop, z.B. Digitec"

class="border rounded-lg px-3 py-2"

/>


<input

name="affiliate_link"

type="url"

required

placeholder="Dein echter Affiliate-Link"

class="border rounded-lg px-3 py-2 md:col-span-2"

/>


<input

name="coupon_code"

placeholder="Rabattcode"

class="border rounded-lg px-3 py-2"

/>


<input

name="coupon_discount"

type="number"

step="0.01"

min="0"

value="0"

placeholder="CHF Rabatt"

class="border rounded-lg px-3 py-2"

/>


<input

name="payment_bonus"

type="number"

step="0.01"

min="0"

value="0"

placeholder="Zahlungsbonus"

class="border rounded-lg px-3 py-2"

/>


<button

class="bg-emerald-600 text-white py-2 rounded-lg md:col-span-2"

>

Als NettoDeal veröffentlichen

</button>


</form>


</div>


{% else %}


<div class="bg-white border rounded-xl p-8 text-slate-500">

Noch keine Kandidaten importiert.

</div>


{% endfor %}


</div>


</div>

</body>

</html>
"""


# ============================================================
# ROUTES
# ============================================================

@app.get("/", response_class=HTMLResponse)
def read_root():

    with get_db() as conn:

        deals = conn.execute(
            """
            SELECT *
            FROM deals
            ORDER BY id DESC
            """
        ).fetchall()

    template = Template(HTML_TEMPLATE)

    return HTMLResponse(
        template.render(deals=deals)
    )


@app.get("/admin", response_class=HTMLResponse)
def admin_page():

    with get_db() as conn:

        candidates = conn.execute(
            """
            SELECT *
            FROM deal_candidates
            WHERE status = 'pending'
            ORDER BY id DESC
            """
        ).fetchall()

    template = Template(ADMIN_TEMPLATE)

    return HTMLResponse(
        template.render(candidates=candidates)
    )


# ============================================================
# MANUELLEN DEAL ERSTELLEN
# ============================================================

@app.post("/deals")
def create_deal(

    title: str = Form(...),
    category: str = Form(...),
    base_price: float = Form(...),

    coupon_code: str = Form(""),
    coupon_discount: float = Form(0),

    payment_bonus: float = Form(0),

    shop_name: str = Form(...),
    affiliate_link: str = Form(...),

):

    effective_price = max(
        0,
        base_price
        - coupon_discount
        - payment_bonus
    )

    with get_db() as conn:

        conn.execute(
            """
            INSERT INTO deals (

                title,
                category,

                base_price,

                coupon_code,
                coupon_discount,

                payment_bonus,

                effective_price,

                shop_name,

                affiliate_link,

                source_name,
                source_url,

                created_at

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title.strip(),
                category.strip(),

                base_price,

                coupon_code.strip(),
                coupon_discount,

                payment_bonus,

                effective_price,

                shop_name.strip(),

                affiliate_link.strip(),

                "manual",
                "",

                now_iso(),
            ),
        )

    return RedirectResponse(
        "/",
        status_code=303
    )


# ============================================================
# TOPPREISE IMPORT
# ============================================================

@app.post("/admin/import/toppreise")
def import_toppreise_route():

    try:

        import_toppreise(100)

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Import fehlgeschlagen: {str(exc)}"
        )

    return RedirectResponse(
        "/admin",
        status_code=303
    )


# ============================================================
# KANDIDAT VERÖFFENTLICHEN
# ============================================================

@app.post("/admin/publish/{candidate_id}")
def publish_candidate(

    candidate_id: int,

    shop_name: str = Form(...),
    affiliate_link: str = Form(...),

    coupon_code: str = Form(""),
    coupon_discount: float = Form(0),

    payment_bonus: float = Form(0),

):

    with get_db() as conn:

        candidate = conn.execute(
            """
            SELECT *
            FROM deal_candidates
            WHERE id = ?
            AND status = 'pending'
            """,
            (candidate_id,),
        ).fetchone()

        if not candidate:

            raise HTTPException(
                status_code=404,
                detail="Kandidat nicht gefunden."
            )

        effective_price = max(
            0,
            candidate["base_price"]
            - coupon_discount
            - payment_bonus
        )

        conn.execute(
            """
            INSERT INTO deals (

                title,
                category,

                base_price,

                coupon_code,
                coupon_discount,

                payment_bonus,

                effective_price,

                shop_name,

                affiliate_link,

                source_name,
                source_url,

                created_at

            )

            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate["title"],
                candidate["category"],

                candidate["base_price"],

                coupon_code.strip(),
                coupon_discount,

                payment_bonus,

                effective_price,

                shop_name.strip(),

                affiliate_link.strip(),

                candidate["source_name"],
                candidate["source_url"],

                now_iso(),
            ),
        )

        conn.execute(
            """
            UPDATE deal_candidates
            SET status = 'published'
            WHERE id = ?
            """,
            (candidate_id,),
        )

    return RedirectResponse(
        "/",
        status_code=303
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():

    try:

        with get_db() as conn:
            conn.execute("SELECT 1")

        return JSONResponse(
            {
                "status": "healthy",
                "database": "connected",
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
# API TEST
# ============================================================

@app.get("/api/toppreise-preview")
def toppreise_preview():

    try:

        products = fetch_toppreise_products(20)

        return {
            "count": len(products),
            "products": products,
        }

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=str(exc)
        )


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
