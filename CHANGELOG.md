# NettoDeals 3.1.1 – Überarbeitung

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
| Qualität | Reproduzierbar gepinnte Pakete, 24 Tests, Ruff, Bandit, `pip-audit` und GitHub-Actions-CI. |

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
