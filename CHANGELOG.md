# NettoDeals 3.0 – Überarbeitung

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
| Betrieb | Python 3.12 in Anwendung und Container, Non-root-Container, persistentes Volume, Healthcheck und dokumentierte Umgebungsvariablen. |
| Qualität | Reproduzierbar gepinnte Pakete, 15 Tests, Ruff, Bandit, `pip-audit` und GitHub-Actions-CI. |

## Neue Trendsignale

Toppreise wird nicht mehr gescrapt. Die Sortierung kombiniert stattdessen den
öffentlichen Google-Trends-RSS-Export für die Schweiz mit ausschließlich täglich
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
