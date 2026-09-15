# NettoDeals.ch 3.1.1 🇨🇭

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

## Neu in Version 3.1.1

- stabile, indexierbare Detailseiten unter `/deal/{id}/{slug}`;
- Canonical-URLs, individuelle Seitentitel und Meta-Descriptions;
- `robots.txt`, dynamische XML-Sitemap und `noindex` für interne Bereiche;
- Social-Metadaten sowie lokales SVG-Favicon ohne fremde Markenassets;
- sichtbarer Zeitpunkt der Preisprüfung und korrekte Kennzeichnung von „Ab“-Preisen;
- getrennte Anzeige von Händler und Datenquelle;
- öffentliche Seiten für Über uns, Redaktion, Datenschutz und Impressum;
- Plausibilitätsgrenzen gegen unvollständig gespeicherte Toppreise-Seiten;
- unveränderte Importe aktualisieren nur Prüfzeitpunkt und Sichtbarkeit, nicht das
  SEO-Änderungsdatum eines Angebots.

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

### Redaktioneller Startbestand aus Toppreise

Solange noch keine Affiliate-Programme freigeschaltet sind, kann der Adminbereich
einen redaktionellen Startbestand aus zwei Toppreise-Ansichten übernehmen:

1. `https://www.toppreise.ch/topprodukte` im Browser öffnen und als HTML speichern;
2. unter `https://www.toppreise.ch/neue-toppreise` **48 Stunden** auswählen und
   auch diese Ansicht als HTML speichern;
3. beide Dateien unter **Toppreise-Auswahl importieren** hochladen.

Der Import ist bewusst manuell, weil direkte Serverabrufe von Toppreise je nach
Netzwerk blockiert werden können. Er übernimmt pro Datei höchstens 100 Titel,
Preise und Produktlinks, führt Überschneidungen über die Toppreise-Produkt-ID
zusammen und legt alles als prüfpflichtigen Entwurf an. Bilder werden nicht
kopiert. Veröffentlichte redaktionelle Links sind klar als provisionsfrei
gekennzeichnet. Vor regelmässiger oder kommerzieller Nutzung sind die jeweils
aktuellen Bedingungen von Toppreise zu prüfen.

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

Vor dem produktiven Einsatz müssen die Platzhalter im Abschnitt `impressum` der
Datei `nettodeals/templates/info.html` durch die echten Betreiber- und
Kontaktdaten ersetzt werden.

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
| `SITE_URL` | `https://nettodeals.ch` | Öffentliche HTTPS-Basis für Canonicals und Sitemap |
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
- Toppreise-Snapshots beginnen ebenfalls immer als `draft` und werden als
  redaktionelle, provisionsfreie Links gekennzeichnet.
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
`trends.py`, `seo.py`, Templates und statische Assets aufgeteilt. `main.py` bleibt als
kleiner ASGI-Einstiegspunkt erhalten.

## Betrieb mit mehreren Instanzen

SQLite ist eine lokale Datei. Mehrere Flux-Instanzen dürfen nur dann parallel
Schreibzugriffe ausführen, wenn sie nachweislich dasselbe persistente Dateisystem
verwenden. Andernfalls entstehen unterschiedliche Entwürfe, Klickzahlen und
Veröffentlichungsstände. Bis eine gemeinsame PostgreSQL-Datenbank verfügbar ist,
sollte genau eine Instanz als schreibende Hauptinstanz betrieben werden.

Die vollständige manuelle GitHub-Aktualisierung ist in
[`GITHUB_UPDATE.md`](GITHUB_UPDATE.md) beschrieben.

## Lizenz

Alle Rechte vorbehalten. Eine Open-Source-Lizenz sollte erst nach einer bewussten
Entscheidung des Rechteinhabers ergänzt werden.
