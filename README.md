# NettoDeals.ch 🇨🇭

Ein mobiles, selbst gehostetes Elektronik-Deal-Portal für die Schweiz. NettoDeals
berechnet den Effektivpreis nach festen Gutscheinen und Zahlungsboni, importiert
Affiliate-Angebote zunächst als Entwurf und sortiert veröffentlichte Deals nach
kostenlosen Schweizer Nachfrage-Signalen.

Die vollständige Zuordnung der behobenen Befunde und Upgrade-Hinweise steht in
[`CHANGELOG.md`](CHANGELOG.md).

## Was Version 3 verbessert

- sichere Jinja-Templates mit aktiviertem HTML-Autoescaping und strikter CSP;
- geschützter Adminbereich mit kurzlebiger HttpOnly-Session, CSRF-Schutz und
  begrenzten Loginversuchen;
- korrigierte Awin- und TradeDoubler-Feldzuordnung inklusive Pagination;
- erneute Moderation, wenn ein externer Anbieter einen veröffentlichten Deal ändert;
- automatische Archivierung verschwundener oder abgelaufener Angebote;
- automatische Synchronisierung im Hintergrund;
- mobile-first Oberfläche mit einer eigenständigen, dezenten Aurora-Farbwelt;
- anonyme Klickzählung ohne Benutzerprofile, Cookies oder gespeicherte IP-Adressen;
- reproduzierbare Python-Abhängigkeiten, Tests, CI und gehärteter Containerbetrieb.

## Kostenlose Trendsuche für die Schweiz

Direktes Scraping von Toppreise ist für Serveranwendungen unzuverlässig und kann
mit `403`, `504`, Layoutänderungen oder Nutzungsbeschränkungen scheitern. Version 3
verwendet deshalb zwei einfache Signale:

1. den öffentlichen Google-Trends-RSS-Feed mit `geo=CH`, ohne API-Key;
2. täglich aggregierte Klickzahlen auf veröffentlichte Deals aus den letzten 14 Tagen.

Die RSS-Antwort wird in SQLite gecacht. Schlägt Google vorübergehend fehl, bleiben
die letzten Trendbegriffe und die lokalen Klickzahlen nutzbar. Trendbegriffe werden
nur dann gewertet, wenn sie tatsächlich zum Titel eines vorhandenen Deals passen;
allgemeine Nachrichten-Suchbegriffe beeinflussen die Sortierung daher kaum.

Das System speichert keine IP-Adresse, keinen Referrer und keine personenbezogene
Klickhistorie. Ältere Tagesaggregate werden automatisch entfernt. Für hohe Last
oder mehrere Replikate sollte die Zählung später durch einen gemeinsamen Store wie
Valkey/Redis ersetzt werden.

## Lokaler Start

Voraussetzungen: Python 3.12 und Git.

```bash
git clone https://github.com/nettodeals/nettodeals.git
cd nettodeals
python -m venv .venv
source .venv/bin/activate
python -m pip install --requirement requirements.txt
cp .env.example .env
```

Setze in `.env` einen zufälligen `ADMIN_TOKEN` mit mindestens 32 Zeichen. Anschließend:

```bash
set -a
source .env
set +a
DB_PATH=./nettodeals.db python -m uvicorn main:app --reload
```

Die Startseite liegt unter <http://127.0.0.1:8000/>, der Adminbereich unter
<http://127.0.0.1:8000/admin>. Für lokales HTTP muss `COOKIE_SECURE=false` gesetzt
sein. Im produktiven HTTPS-Betrieb muss der Wert `true` sein.

## Docker Compose

```bash
cp .env.example .env
# ADMIN_TOKEN in .env ersetzen
docker compose up --build -d
```

Die SQLite-Datei liegt im benannten Volume `nettodeals-data`. Der Container läuft
als unprivilegierter Benutzer und besitzt einen Healthcheck.

## Wichtige Umgebungsvariablen

| Variable | Standard | Bedeutung |
| --- | --- | --- |
| `DB_PATH` | `/data/nettodeals.db` | SQLite-Datei |
| `ADMIN_TOKEN` | leer | Erforderliches Admin-Geheimnis |
| `COOKIE_SECURE` | `true` | Admin-Cookie nur über HTTPS |
| `ALLOWED_HOSTS` | `*` | Kommagetrennte erlaubte Hostnamen |
| `AUTO_SYNC_ENABLED` | `true` | Hintergrund-Synchronisierung |
| `AUTO_SYNC_INTERVAL` | `21600` | Abstand in Sekunden, mindestens 900 |
| `GOOGLE_TRENDS_ENABLED` | `true` | Kostenloses Schweizer Trendsignal |
| `AWIN_PUBLISHER_ID` | leer | Aktiviert Awin zusammen mit Token |
| `AWIN_API_TOKEN` | leer | Awin Bearer-Token |
| `TRADEDOUBLER_PRODUCTS_TOKEN` | leer | TradeDoubler Products-Token |
| `TRADEDOUBLER_VOUCHERS_TOKEN` | leer | TradeDoubler Vouchers-Token |

API-Fehler werden vor dem Speichern von bekannten Geheimnissen bereinigt. Die
ungeschützte Statusroute meldet nur Aktivierungszustände und niemals Dateipfade
oder Tokenwerte. Interaktive API-Dokumentation ist standardmäßig deaktiviert.

## Moderationsmodell

- Neue Affiliate-Angebote beginnen immer als `draft`.
- Eine Veröffentlichung erfordert eine gültige HTTPS-Zieladresse.
- Ändern Affiliate-APIs sicherheitsrelevante Inhalte, fällt der Deal wieder auf
  `draft` zurück.
- Nur nach einem vollständig erfolgreichen, nicht abgeschnittenen Import werden
  nicht mehr gelieferte Datensätze archiviert.
- Ein `expires_at` in der Vergangenheit archiviert den Deal automatisch.

## Entwicklung und Tests

```bash
python -m pip install --requirement requirements-dev.txt
ruff check .
python -m pytest
bandit -q -r nettodeals main.py
pip-audit --requirement requirements.txt
```

Die Architektur ist in `config.py`, `db.py`, `security.py`, `services.py`,
`trends.py`, Templates und statische Assets aufgeteilt. `main.py` bleibt als
kleiner ASGI-Einstiegspunkt erhalten.

## Lizenz

Alle Rechte vorbehalten. Eine Open-Source-Lizenz sollte erst nach einer bewussten
Entscheidung des Rechteinhabers ergänzt werden.
