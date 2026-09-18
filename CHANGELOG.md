# NettoDeals 3.4.0 – Deals im Aurora-Design

- Einheitlicher Deal-Workflow ohne verpflichtenden Affiliate-Zugang oder YouTube-Key.
- Produktbild, Rechtebestätigung und maximal 48 Stunden alte Preisprüfung vor Freigabe.
- Hersteller-UVP mit Quellenlink; transparente CHF-Ersparnis und abgerundete Prozente.
- Aurora-Preiskarten und grössere Produktbilder auf Start- und Detailseiten.
- Bildvorschau im Adminbereich, Recherchelinks für Hersteller und Bildsuche.
- Persistente Freigabewarteschlange mit eigenem 6-/12-/24-Stunden-Zeitplan.
- Änderung importierter Daten entzieht die Warteschlangenfreigabe; neue Bilder
  und UVP-Werte benötigen erneut eine Bestätigung beziehungsweise Quelle.
- Alte Steckbriefe nicht mehr auf der Homepage; alte URLs bleiben erhalten,
  der alte automatische Steckbrief-Zeitplan wird nicht weiter ausgeführt.
- Neue Datenbankspalten und Tabellen werden additiv angelegt.
- Keine neuen Pflicht-ENV-Variablen, keine kostenpflichtigen Publishing-Dienste.

# NettoDeals 3.3.0 – Kostenlose Produktredaktion

- Separater Veröffentlichungsweg ohne Affiliate-Partner oder bestätigten Kaufpreis.
- Quellenbasierte, vorlagenbasierte Steckbriefe statt erfundener Tests und Rabatte.
- Sofortpublikation und persistenter 6-/12-/24-Stunden-Zeitplan mit Freigabewarteschlange.
- Auswahl vorhandener importierter Produkte ohne Übernahme fremder Produktbilder.
- Quellenalter maximal sieben Tage beim Publizieren; ältere Artikel bleiben als
  zeitlich eingeordnete redaktionelle Inhalte zugänglich.
- Authentifizierte Social-Downloads mit Text und lokalen PNG-Karten, kein
  kostenpflichtiger Publishing-Dienst und kein automatischer externer Upload.
- Öffentliche Artikel, Startseitenkarten, Canonicals, Social-Metadaten und Sitemap.
- Additive Datenbankmigration; bestehende Deal-Prüfung und Deal-Ablauf bleiben erhalten.
- Normale Händlerlinks sind bei manuellen Deals ausdrücklich auswählbar.

# NettoDeals 3.2.0 – Automatisierte Redaktion

## Veröffentlichung 3.2.0

- sichere Partnerfeed-Zuordnung für Toppreise-Trendsignale;
- direkte Händlerziele statt öffentlicher Toppreise-Kaufziele;
- Produktbilder mit Quellenangabe, Hersteller-UVP und Rabattkennzeichnung;
- Gutscheinvorschläge samt Bedingungen und Gültigkeit;
- optionaler YouTube-API-Abruf sowie faktenbasierter NettoDeals-Kurzcheck;
- automatische 48-Stunden-Laufzeit und öffentliche vergangene Deals;
- mobile Pflege, manuelles Beenden und erneute Prüfung im Adminbereich;
- additive SQLite-Migration ohne Löschen vorhandener Deals.

# NettoDeals 3.1.2 – Überarbeitung

## Mobiler Toppreise-Import 3.1.2

- Native Unterstützung für `.mht`- und `.mhtml`-Webarchive, wie sie Chrome auf
  Android beim Speichern einer vollständigen Seite erzeugt.
- MIME-Archive werden mit der Python-Standardbibliothek verarbeitet; ausgewertet
  wird ausschliesslich der erste `text/html`-Teil. Bilder und andere eingebettete
  Ressourcen werden weder gespeichert noch ausgeführt.
- Webarchive sind auf 20 MB begrenzt, der extrahierte HTML-Inhalt weiterhin auf
  5 MB. Ungültige Archive und nicht erlaubte Dateitypen liefern verständliche
  Fehlermeldungen.
- Der mobile Dateiauswahldialog akzeptiert HTML, HTM, MHT und MHTML.

## SEO-, Vertrauens- und Qualitätsupdate 3.1.1

- Indexierbare Deal-Detailseiten mit sprechenden Slugs und dauerhaften IDs.
- Canonical-Links, individuelle Metadaten, Open-Graph-Angaben, Favicon,
  `robots.txt` und eine dynamische XML-Sitemap.
- Interne Suche, Admin-, API-, Health- und Weiterleitungsrouten werden von der
  Indexierung ausgeschlossen.
- Neue Felder `source_name`, `price_type` und `price_checked_at` werden beim Start
  automatisch in vorhandene SQLite-Datenbanken migriert.
- Toppreise-Einträge zeigen „ab CHF“, Datenquelle und Prüfzeitpunkt; Toppreise wird
  nicht mehr als konkreter Händler ausgegeben.
- Unvollständige Snapshots mit weniger als 50 Top-100- beziehungsweise 10
  48-Stunden-Produkten werden abgewiesen.
- Öffentliche Seiten für Projektbeschreibung, redaktionelle Transparenz,
  Datenschutz und Impressum ergänzt. Betreiberplatzhalter müssen vor dem Deploy
  ersetzt werden.
- Unveränderte Imports verändern nicht mehr das in der Sitemap verwendete
  Aktualisierungsdatum.

## Redaktioneller Toppreise-Startbestand

- Admin-Import für gespeicherte HTML-Ansichten der Top 100 und der neuen
  Toppreise mit ausgewähltem 48-Stunden-Zeitraum ergänzt.
- Höchstens 100 Produkte pro Datei; Zusammenführung über Toppreise-Produkt-IDs.
- Importe bleiben bis zur Einzelprüfung Entwürfe und enthalten keine Produktbilder.
- Redaktionelle Direktlinks werden getrennt von Affiliate-Links gespeichert und
  auf der Homepage ausdrücklich als provisionsfrei ausgewiesen.
- Uploads sind auf 5 MB pro Datei begrenzt; der 48-Stunden-Filter muss im Formular
  bestätigt werden, unerkannte Snapshot-Strukturen führen zu einer Fehlermeldung.

## Behobene Befunde

| Bereich | Änderung |
| --- | --- |
| Deal-Erfassung | Spalten und Platzhalter des Inserts stimmen überein; manuelle und importierte Deals werden über denselben getesteten Upsert gespeichert. |
| XSS | Jinja-Autoescaping ist für HTML/XML aktiv; unkontrolliertes `Template(...)` und `safe`-Rendering entfallen. |
| Affiliate-Mapping | Verschachtelter Awin-Gutscheincode sowie TradeDoubler-Angebote, Preise, Kategorien, Shops und Tracking-Links werden korrekt gelesen. |
| Synchronisierung | Pagination pro Quelle, Hintergrund-Sync, vollständigkeitsabhängige Archivierung und Ablaufdatum-Archivierung sind implementiert. |
| Moderation | Externe Inhaltsänderungen setzen veröffentlichte Angebote zurück auf `draft`. |
| Adminschutz | Signierte, kurzlebige HttpOnly-Session, CSRF-Schutz, Login-Limit und mindestens 32 Zeichen langes Admin-Geheimnis. |
| Eingaben und Links | Begrenzte Formfelder, endliche/beschränkte Geldwerte und ausschließlich normalisierte HTTPS-Zieladressen. |
| Datenbank | Parametrisierte Abfragen, WAL, Busy-Timeout, Transaktions-Rollback, Indizes und automatische Migration der vorhandenen SQLite-Tabelle. |
| Statusrouten | Keine Ausgabe von Datenbankpfaden, Tokens oder internen Fehlermeldungen. |
| Architektur | Fachlogik, Konfiguration, Datenzugriff, Sicherheit, Trends, Templates und Assets sind getrennt; tote SQLModel-Dateien entfallen. |
| Frontend | Keine Tailwind-CDN-Laufzeit; lokale CSS/JS-Assets, CSP, mobile Karten, horizontale Filterchips, 44-px-Paging-Ziele und klare Affiliate-Kennzeichnung. Die dezente Blau/Violett/Pink/Cyan-Aurora ist eigenständig in CSS umgesetzt und verwendet weder fremde Logos noch Markenassets. |
| Social Media | X, Instagram und TikTok sind als dezente, tastaturbedienbare Footer-Links mit mobilgerechten Touch-Zielen eingebunden; externe Seiten öffnen sicher in einem neuen Tab. |
| Betrieb | Python 3.12 in Anwendung und Container, Non-root-Container, persistentes Volume, Healthcheck und dokumentierte Umgebungsvariablen. |
| Qualität | Reproduzierbar gepinnte Pakete, 28 Tests, Ruff, Bandit, `pip-audit` und GitHub-Actions-CI. |

## Neue Trendsignale

Toppreise wird nicht automatisch vom Server gescrapt. Optional kann der Admin
zwei selbst gespeicherte Browser-Snapshots als redaktionelle Entwürfe importieren.
Die Sortierung kombiniert zusätzlich den öffentlichen Google-Trends-RSS-Export
für die Schweiz mit ausschließlich täglich
aggregierten Deal-Aufrufen der letzten 14 Tage. Die letzte erfolgreiche
RSS-Antwort bleibt in SQLite erhalten, sodass ein temporärer Ausfall die Sortierung
nicht lahmlegt.

Der RSS-Feed signalisiert kurzfristige Suchspitzen und ist kein reiner
Produkt-Bestseller-Feed. Deshalb werden nur Begriffe gewertet, die zum Titel eines
vorhandenen Deals passen; mit wachsendem Traffic übernimmt das eigene Klicksignal
zunehmend die Feinordnung.

## Upgrade-Hinweise

1. Vor dem ersten Start die vorhandene SQLite-Datei sichern.
2. `ADMIN_TOKEN` auf einen zufälligen Wert mit mindestens 32 Zeichen setzen.
3. Abhängigkeiten neu installieren oder das Image neu bauen.
4. Beim Start ergänzt die Anwendung fehlende Spalten und Indizes automatisch.
5. Den Adminbereich öffnen und alle importierten Entwürfe vor Veröffentlichung prüfen.
