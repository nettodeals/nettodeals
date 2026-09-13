# main.py
from datetime import datetime
import os
import sqlite3
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import uvicorn

app = FastAPI(title="NettoDeals", version="1.0.0")

DB_DIR = "/data"
os.makedirs(DB_DIR, exist_ok=True)
DB_FILE = os.path.join(DB_DIR, "nettodeals.db")


def init_db():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            base_price REAL NOT NULL,
            coupon_discount REAL DEFAULT 0,
            payment_bonus REAL DEFAULT 0,
            effective_price REAL NOT NULL,
            shop_name TEXT NOT NULL,
            affiliate_link TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
  conn.commit()
  conn.close()


init_db()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NettoDeals.ch - Effektivpreise für Schweizer Elektronik</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 font-sans antialiased min-h-screen flex flex-col">
    <!-- Header -->
    <header class="bg-white border-b border-slate-200 sticky top-0 z-50">
        <div class="max-w-6xl mx-auto px-4 py-4 flex justify-between items-center">
            <div class="flex items-center space-x-2">
                <span class="text-2xl font-black text-indigo-600 tracking-tight">Netto<span class="text-slate-900">Deals</span><span class="text-xs align-super bg-indigo-100 text-indigo-800 px-1.5 py-0.5 rounded-full font-bold ml-1">CH</span></span>
            </div>
            <p class="text-sm text-slate-500 hidden sm:block">Der echte Endpreis nach Gutscheinen & Zahlungs-Boni</p>
        </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-6xl mx-auto px-4 py-8 flex-grow w-full grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        <!-- Left/Main Column: Deal Grid -->
        <div class="lg:col-span-2 space-y-6">
            <div class="flex justify-between items-center">
                <h1 class="text-xl font-bold text-slate-900">Aktuelle Top-Deals</h1>
                <span class="text-sm text-slate-500">{{ deals|length }} Angebote gefunden</span>
            </div>

            {% if deals %}
                <div class="grid grid-cols-1 gap-4">
                    {% for deal in deals %}
                    <div class="bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow p-5 flex flex-col justify-between">
                        <div>
                            <div class="flex justify-between items-start gap-2 mb-2">
                                <span class="text-xs font-semibold uppercase tracking-wider bg-slate-100 text-slate-600 px-2.5 py-1 rounded-md">{{ deal[2] }}</span>
                                <span class="text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded">{{ deal[7] }}</span>
                            </div>
                            <h2 class="text-lg font-bold text-slate-900 mb-3">{{ deal[1] }}</h2>
                            
                            <!-- Price Breakdown Badge Container -->
                            <div class="flex flex-wrap gap-2 mb-4">
                                {% if deal[4] > 0 %}
                                <span class="text-xs bg-amber-50 text-amber-700 border border-amber-200 px-2 py-1 rounded">Gutschein: -CHF {{ "%.2f"|format(deal[4]) }}</span>
                                {% endif %}
                                {% if deal[5] > 0 %}
                                <span class="text-xs bg-blue-50 text-blue-700 border border-blue-200 px-2 py-1 rounded">Zahlung: -CHF {{ "%.2f"|format(deal[5]) }}</span>
                                {% endif %}
                            </div>
                        </div>

                        <div class="pt-4 border-t border-slate-100 flex items-center justify-between mt-auto">
                            <div>
                                <div class="text-xs text-slate-400 line-through">CHF {{ "%.2f"|format(deal[3]) }}</div>
                                <div class="text-2xl font-black text-indigo-600">CHF {{ "%.2f"|format(deal[6]) }}</div>
                            </div>
                            <a href="{{ deal[8] }}" target="_blank" rel="nofollow noopener" class="bg-indigo-600 hover:bg-indigo-700 text-white font-medium px-5 py-2.5 rounded-lg text-sm transition-colors shadow-sm">
                                Zum Deal &rarr;
                            </a>
                        </div>
                    </div>
                    {% endfor %}
                </div>
            {% else %}
                <div class="bg-white rounded-xl border border-slate-200 p-8 text-center text-slate-500">
                    Noch keine Deals vorhanden. Erfasse den ersten Deal über das Formular!
                </div>
            {% endif %}
        </div>

        <!-- Right Column: Simple Admin Form to Add Deals -->
        <div class="lg:col-span-1">
            <div class="bg-white rounded-xl border border-slate-200 p-6 sticky top-24 shadow-sm">
                <h2 class="text-lg font-bold text-slate-900 mb-4">Deal erfassen</h2>
                <form action="/deals" method="POST" class="space-y-4">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Titel</label>
                        <input type="text" name="title" required placeholder="z.B. iPhone 15 Pro 128GB" class="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Kategorie</label>
                        <input type="text" name="category" required placeholder="z.B. Smartphones" class="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Grundpreis (CHF)</label>
                            <input type="number" step="0.05" name="base_price" required placeholder="999.00" class="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Gutschein (CHF)</label>
                            <input type="number" step="0.05" name="coupon_discount" value="0.00" class="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                        </div>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Zahlungs-Bonus</label>
                            <input type="number" step="0.05" name="payment_bonus" value="0.00" class="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Shop Name</label>
                            <input type="text" name="shop_name" required placeholder="Digitec" class="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                        </div>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 uppercase mb-1">Affiliate Link</label>
                        <input type="url" name="affiliate_link" required placeholder="https://partner.digitec.ch/..." class="w-full text-sm border border-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                    </div>
                    <button type="submit" class="w-full bg-slate-900 hover:bg-slate-800 text-white font-medium py-2.5 rounded-lg text-sm transition-colors shadow-sm">
                        Deal speichern
                    </button>
                </form>
            </div>
        </div>
    </main>

    <!-- Footer -->
    <footer class="bg-white border-t border-slate-200 mt-12 py-6 text-center text-xs text-slate-400">
        &copy; 2026 NettoDeals.ch &bull; Dezentral gehostet auf FluxNodes
    </footer>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, title, category, base_price, coupon_discount, payment_bonus,"
      " effective_price, shop_name, affiliate_link, created_at FROM deals ORDER"
      " BY id DESC"
  )
  deals = cursor.fetchall()
  conn.close()

  template = Jinja2Template(HTML_TEMPLATE)
  return template.render(deals=deals)


@app.post("/deals")
def create_deal(
    title: str = Form(...),
    category: str = Form(...),
    base_price: float = Form(...),
    coupon_discount: float = Form(0.0),
    payment_bonus: float = Form(0.0),
    shop_name: str = Form(...),
    affiliate_link: str = Form(...),
):
  effective_price = base_price - coupon_discount - payment_bonus
  if effective_price < 0:
    effective_price = 0.0

  created_at = datetime.utcnow().isoformat()

  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute(
      """
        INSERT INTO deals (title, category, base_price, coupon_discount, payment_bonus, effective_price, shop_name, affiliate_link, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
          created_at,
      ),
  )
  conn.commit()
  conn.close()

  return RedirectResponse(url="/", status_code=303)


if __name__ == "__main__":
  uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
