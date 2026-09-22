# NettoDeals.ch 3.5.0 🇨🇭

Neu: Händlerlink → gemeinsamer Deal-/Social-Editor → Freigabe. Optional Gemini mit
`GEMINI_API_KEY`; ohne Schlüssel oder bei Fehlern Textvorlagen. Aurora-Bilder werden
lokal erstellt. Kein automatisches Social-Posting und kein Toppreise-Crawling.


## Groq-Redaktionspilot

Im Adminbereich je Entwurf „Mit KI vorbereiten“ wählen. Geprüfte Produktfakten
werden nach Bestätigung an Groq übermittelt. Der Assistent erstellt editierbare
Website- und Social-Texte; Veröffentlichung und Preisprüfung bleiben separat.
Ohne Schlüssel arbeitet die Anwendung wie bisher. Nur `GROQ_API_KEY` ist für
den optionalen Test zusätzlich nötig. Kein automatischer API-Aufruf beim Start.

**Einrichtung, Termux-Update und Testablauf:** [UPDATE-GROQ-PILOT.md](UPDATE-GROQ-PILOT.md).

## Aktuell: ein Deal-Workflow mit Aurora-Preiskarten

Ab 3.4 erfolgt die Redaktion über `/admin`: normaler Shoplink, geprüfter Preis,
Produktbild und bestätigtes Bildrecht. YouTube und Affiliate-Partner sind optional.
Veröffentlichung sofort oder aus einer freigegebenen Warteschlange alle 6/12/24 Stunden.
Eine belegte Hersteller-UVP wird mit CHF-Ersparnis und abgerundetem Prozentwert
visualisiert. Ohne UVP-Quelle wird kein Rabatt erfunden.

Die separate Steckbrief-Kategorie ist von der Startseite entfernt; bestehende
Artikel und Downloads bleiben über ihre alten URLs erreichbar. Der alte
Steckbrief-Scheduler läuft nicht mehr. Der neue Deal-Zeitplan ist zunächst aus.

**Aktuelle Anleitung: [UPDATE-3.5.0.md](UPDATE-3.5.0.md)** – einschliesslich Bilder,
YouTube Data API v3, Termux und Grenzen der Automatisierung.

Die folgenden Versionsabschnitte dokumentieren den früheren Funktionsstand.

## Kostenlose Redaktion ohne Affiliate-Partner

Unter `/admin/redaktion` lassen sich kurze Produktsteckbriefe sofort oder alle
6, 12 oder 24 Stunden veröffentlichen. Voraussetzung ist ein freigegebener Vorrat
mit Quellenangabe und tatsächlich geprüftem Quelldatum. Kein Publishing-Abo,
keine Social-API und keine zusätzlichen Umgebungsvariablen erforderlich.

Steckbriefe sind ausdrücklich keine bestätigten Preisangebote oder Produkttests.
Sie können vorhandene Toppreise-Importe als Signal verwenden, übernehmen aber
nicht automatisch fremde Beschreibungen, Bilder, Rabatte oder Händlernachweise.
Die bisherige Prüfung echter Deals bleibt bestehen.

Bei Veröffentlichung werden drei Social-Pakete mit Text und eigener PNG-Grafik
vorbereitet. Der Upload auf X, Instagram und TikTok erfolgt manuell. Es werden
keine Beiträge an externe Plattformen gesendet. TikTok erhält eine Hochformat-
Fotokarte, kein Video. Die Grafiken nutzen die mitgelieferte freie DejaVu-Schrift.

**Installation, Grenzen und Smartphone-Anleitung:** [UPDATE-3.3.0.md](UPDATE-3.3.0.md).

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

## Neu in Version 3.1.2

- direkter Import von `.mht`- und `.mhtml`-Webarchiven aus Chrome für Android;
- sichere Extraktion ausschliesslich des eingebetteten HTML-Dokuments;
- getrennte Grössenlimits von 20 MB für das Webarchiv und 5 MB für HTML;
- mobilgerechte Dateiauswahl für HTML, HTM, MHT und MHTML.

## Neu in Version 3.2.0

- Toppreise bleibt ausschliesslich interne Signal- und Prüfquelle; Toppreise-Links
  können nicht mehr als öffentliches Kaufziel veröffentlicht werden;
- Ein-Klick-Anreicherung gleicht Entwürfe mit vorhandenen TradeDoubler-
  Produktfeeds ab und übernimmt nur ausreichend sicher zugeordnete Direktangebote;
- fehlende Händlerdaten können mobil im Entwurf ergänzt werden;
- lizenzierte Produktbilder aus Partnerfeeds, Hersteller-UVP, transparente
  Rabattberechnung und der Hinweis „Gefunden bei …“;
- Gutscheine werden nach Shop und Gültigkeit aus Awin-/TradeDoubler-Feeds
  vorgeschlagen, Bedingungen bleiben sichtbar;
- optional bis zu drei passende externe YouTube-Beiträge über die offizielle
  YouTube Data API;
- automatisch erzeugter, ausdrücklich nicht als eigener Produkttest dargestellter
  NettoDeals-Kurzcheck;
- standardmässig 48 Stunden Laufzeit sowie eine öffentlich sichtbare,
  ausgegraute Sammlung „Vergangene Deals“;
- veröffentlichte und vergangene Angebote lassen sich im Adminbereich beenden
  beziehungsweise erneut zur Prüfung öffnen.

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

1. `https://www.toppreise.ch/topprodukte` im Browser öffnen und als HTML oder
   auf Android als MHT/MHTML-Webarchiv speichern;
2. unter `https://www.toppreise.ch/neue-toppreise` **48 Stunden** auswählen und
   auch diese Ansicht als HTML oder MHT/MHTML speichern;
3. beide Dateien unter **Toppreise-Auswahl importieren** hochladen.

Der Import ist bewusst manuell, weil direkte Serverabrufe von Toppreise je nach
Netzwerk blockiert werden können. Er übernimmt pro Datei höchstens 100 Titel,
Preise und Produktlinks ausschliesslich als interne Rechercheangaben, führt
Überschneidungen über die Toppreise-Produkt-ID zusammen und legt alles als
prüfpflichtigen Entwurf an. Bilder werden nicht kopiert. Eine Veröffentlichung
ist erst mit einem direkten Händlerlink, konkretem Shop und positivem Preis
möglich. Vor regelmässiger oder kommerzieller Nutzung sind die jeweils aktuellen
Bedingungen von Toppreise zu prüfen und idealerweise eine schriftliche Erlaubnis
einzuholen.

### Automatisierter Redaktionsablauf

1. Toppreise-Snapshots liefern Produkttrends als Entwürfe.
2. **Anreichern & veröffentlichen** sucht in bereits importierten Partnerangeboten
   nach demselben Modell. Abweichende Modellnummern werden abgewiesen.
3. Bei sicherem Treffer übernimmt das System Händler, Direktlink, Preis, Bild,
   UVP und – wenn vorhanden – einen noch gültigen Shop-Gutschein.
4. Fehlt ein Partnerangebot, bleibt der Entwurf unveröffentlicht und zeigt die
   mobil ausfüllbaren Pflichtfelder.
5. Der Kurzcheck und optionale YouTube-Verweise werden erzeugt; danach läuft der
   Deal höchstens 48 Stunden.
6. Anschliessend wechselt er automatisch zu `/vergangene-deals`. Der alte
   Kaufbutton wird entfernt, die Preisreferenz bleibt sichtbar.

Gutscheine werden nicht automatisch als Preisabzug verrechnet, wenn ihr Feed
nur einen Prozentwert oder unklare Bedingungen enthält. Damit wird kein nicht
verifizierter Endpreis versprochen.

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
| `YOUTUBE_API_KEY` | leer | Optional: offizielle YouTube-Suche für externe Reviews |
| `DEAL_LIFETIME_HOURS` | `48` | Maximale öffentliche Laufzeit, 1 bis 720 Stunden |

API-Fehler werden vor dem Speichern von bekannten Geheimnissen bereinigt. Die
ungeschützte Statusroute meldet nur Aktivierungszustände und niemals Dateipfade
oder Tokenwerte. Interaktive API-Dokumentation ist standardmäßig deaktiviert.

## Moderationsmodell

- Neue Affiliate-Angebote beginnen immer als `draft`.
- Toppreise-Snapshots beginnen immer als `draft` und bleiben interne Signale.
- Eine Veröffentlichung erfordert einen direkten HTTPS-Händlerlink, Shop und Preis.
- Ändern Affiliate-APIs sicherheitsrelevante Inhalte, fällt der Deal wieder auf
  `draft` zurück.
- Nur nach einem vollständig erfolgreichen, nicht abgeschnittenen Import werden
  nicht mehr gelieferte Datensätze archiviert.
- Ein `expires_at` in der Vergangenheit verschiebt den Deal sichtbar zu `expired`.

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
