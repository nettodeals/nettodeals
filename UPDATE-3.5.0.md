# NettoDeals 3.5.0 – Update und erster Einsatz

## Was dieses Paket liefert

Händlerlink importieren → Daten prüfen → „Deal + Social vorbereiten“ → Texte freigeben
→ sofort veröffentlichen oder im bestehenden Zeitplan einplanen. Social-Beiträge
werden manuell gepostet. Keine automatische Toppreise-Abfrage, kein automatisches
Social-Posting, keine neue Affiliate-Voraussetzung.

Der Linkimport liest JSON-LD-Produktdaten und Open-Graph-Metadaten. Er übernimmt
Titel, Beschreibung/Fakten, eindeutigen CHF-Preis und Bild-URL soweit vorhanden.
Shopname wird zunächst aus der Domain gebildet. Ein Vergleichspreis wird NICHT aus
einem beliebigen durchgestrichenen Preis als UVP geraten. Mehrdeutige Varianten,
fehlende Preise und nur per JavaScript sichtbare Angebote müssen ergänzt werden.
Bei Zugriffssperren bleibt ein manuell bearbeitbarer Entwurf; es gibt keine Umgehung.
Gleiche Quell-URL öffnet den bestehenden Eintrag, statt eine Kopie anzulegen.

## Vor dem Update

- Produktive SQLite-Datenbank mit einem konsistenten Hosting-Backup sichern,
  einschliesslich noch nicht eingecheckter WAL-Daten. Kein blindes Kopieren nur der
  Hauptdatei während laufender Schreibvorgänge.
- Bestehende ENV-Einstellungen sichern. ADMIN_TOKEN und DB_PATH beibehalten.
- Zwei Orbit-Instances mit getrennten Datenbanken bleiben getrennte Datenbestände.
  Diese Version implementiert keine Datenreplikation. Für Redaktion eine feste
  Instanz verwenden oder zuerst gemeinsame konsistente Datenhaltung sicherstellen.
  Auch Sitzungen benötigen auf beiden Instanzen denselben ADMIN_TOKEN.
- Das Paket enthält additive Tabellen/Spalten. Bestehende Deals bleiben erhalten.
  Ein Code-Rollback kennt die neuen Studio-Felder nicht: bei Problemen zunächst den
  Veröffentlichungszeitplan deaktivieren und das Backup kontrolliert wiederherstellen.

## Termux: einzeln ausführen

ZIP `nettodeals-3.5.0.zip` nach Android Downloads laden. Bei Dateinamen mit `(1)`
vorher umbenennen. Falls noch nicht erfolgt: `termux-setup-storage` und erlauben.

```sh
cd ~/netto-update-v311/repo
git config --local core.pager cat
git status --short
```

Bei offenen Projektänderungen zuerst sichern/committen. Nicht mit unklarem Stand
überschreiben. Die folgenden Schritte setzen einen sauberen Arbeitsbaum voraus.

```sh
git fetch origin --prune
git switch main
git pull --ff-only origin main
git switch -c release/3.5.0
git branch --show-current
```

Hier muss `release/3.5.0` stehen. Falls der Branch schon existiert, nicht blind
weiterkopieren: mit `git switch release/3.5.0` wechseln und dessen Stand prüfen.
Falls `main` wegen früherer lokaler Commits nicht vorspult: nicht `reset --hard`
verwenden, sondern den Status klären.

```sh
unzip -t ~/storage/downloads/nettodeals-3.5.0.zip
update_dir=$(mktemp -d "$HOME/nettodeals-v350.XXXXXX")
unzip ~/storage/downloads/nettodeals-3.5.0.zip -d "$update_dir"
head -1 "$update_dir/CHANGELOG.md"
```

Das Paket basiert auf dem im Paket `RELEASE-BASE.txt` genannten GitHub-Commit.
Falls `main` seither eigene Änderungen enthält, diese mit dem Paket abgleichen.

```sh
cp -R "$update_dir"/. .
python -m compileall -q main.py nettodeals tests
git --no-pager diff --stat
git add -- README.md CHANGELOG.md UPDATE-3.5.0.md RELEASE-BASE.txt .env.example nettodeals/ tests/
git --no-pager diff --cached --stat
git commit -m "Release 3.5.0: merchant import and Gemini social studio"
git --no-pager log -1 --oneline
git push -u origin release/3.5.0
```

Nur nach erfolgreichem Commit pushen. Danach EINMAL:

```sh
gh pr create --repo nettodeals/nettodeals --base main --head release/3.5.0 --title "NettoDeals 3.5.0" --body "Haendlerlink-Import, Gemini-Entwuerfe, Aurora-Grafiken und Social-Export mit manueller Freigabe."
```

PR prüfen, grüne CI abwarten, zusammenführen. Kein Ruff/Pillow-Build auf Termux
notwendig. `compileall` prüft nur Syntax; die vollständigen Tests laufen in CI.
Bei `No commits between...` zuerst Branch, Commit und Push prüfen, nicht den
PR-Befehl wiederholen.

## Orbit und Gemini

1. Zuerst das Update über den normalen Pull-/Build-Workflow von `main` deployen.
2. `/api/status` muss `3.5.0` melden. `/admin` zeigt Tabs und den Händlerlink-Import.
3. Bereits OHNE KI-Schlüssel funktioniert der gesamte Vorlagen-/Bildworkflow.
4. Für Gemini einen eigenen Schlüssel unter https://aistudio.google.com/api-keys
   erstellen. Das Projekt ausdrücklich im kostenlosen Tarif ohne aktiviertes
   kostenpflichtiges Billing betreiben. Das tatsächliche Kontingent dort prüfen.
5. In Orbit `GEMINI_API_KEY` ergänzen. Der Wert ist nur der Schlüssel, ohne zusätzliche
   Anführungszeichen/Kommas. `GEMINI_MODEL` ist optional; Standard ist
   `gemini-2.5-flash-lite`. Es ist nur ein neuer ENV-Eintrag erforderlich.
6. Änderungen übernehmen und beide App-Instances mit der neuen Umgebung starten.
   Ein Hard Redeploy oder Entfernen von Instances ist nicht nötig.
7. Den bisherigen GROQ_API_KEY kannst du aus Orbit entfernen, falls der alte Pilot
   nicht mehr benötigt wird. Die alten Routen bleiben zur Kompatibilität erhalten;
   der neue Editor ruft Groq nicht auf.

Die App kann den Google-Abrechnungstarif nicht erkennen. Ein Schlüssel aus einem
bezahlten Projekt kann Kosten auslösen. Ein lokales Tageslimit ist keine Garantie
für kostenlose Nutzung. Es gibt keine automatische Tarifumstellung, keinen bezahlten
Ausweichanbieter und keine API-Bildgenerierung.

## Erster echter Test

1. Im Tab „Quellen & Import“ einen direkten Händler-Produktlink eingeben.
2. Im Editor Titel/Variante, Shop, CHF-Endpreis (Lieferkosten berücksichtigen), Fakten
   und Bildquelle prüfen. Fehlendes ergänzen. Ohne erkannten CHF-Preis steht 0.
3. Falls belegt: Händler-Stattpreis ODER Hersteller-UVP mit Quellenlink auswählen.
4. Nutzungsrecht für Produktbild auf Website UND Social Media bestätigen. Der Import
   stellt keine Bildlizenz aus. Ohne Bestätigung entstehen keine Produktgrafiken.
5. Preisprüfung bestätigen. Für den ersten API-Test zusätzlich „Gemini verwenden“
   ankreuzen. Es gehen nur Produkttitel und Faktentext an Google. Keine geheimen
   oder personenbezogenen Angaben in dieses Feld schreiben.
6. „Deal + Social vorbereiten“. Bei Erfolg zeigt der Editor das Modell als Anbieter;
   bei Fehlern eine konkrete Statusmeldung und die verwendete Textvorlage.
7. Kurzbeschreibung und alle Social-Texte bearbeiten, Fakten abgleichen, freigeben.
   „Kopieren“ kopiert auch ungespeicherte Texte aus dem Feld; der ZIP-Download enthält
   den zuletzt gespeicherten/freigegebenen Stand. Änderungen deshalb freigeben.
8. „Deal jetzt veröffentlichen“ oder zurück zum Kontrollzentrum → Entwürfe → Zeitplan.
9. Unter „Bilder & Export“ Feed-PNG, Story-PNG oder das komplette ZIP herunterladen.
   Entwürfe sind noch keine veröffentlichten Angebote. Vor Social-Posting Dealstatus
   und aktuellen Händlerpreis prüfen. Links in Instagram/TikTok sind nicht automatisch
   anklickbar; Profil-/Story-Link in der jeweiligen Plattform selbst ergänzen.

Gemini: maximal zehn Versuche pro UTC-Tag und Datenbank, einschliesslich Fehler.
Kein automatischer Retry. Erneutes „Vorbereiten“ erzeugt neue Entwürfe und verwirft
vorherige Freigaben. Eine Preis-/Quellenänderung sperrt ältere Pakete und nimmt den
Deal aus der Warteschlange. Änderungen an bereits heruntergeladenen oder geposteten
Inhalten lassen sich nicht automatisch zurückholen.

Ohne belegte Produktfakten sind die Vorlagentexte bewusst knapp. Gemini macht aus
unsicheren Quellen keine verifizierten Fakten. Menschliche Prüfung bleibt nötig.
Die Free-Tier-Datenverarbeitung von Google berücksichtigen:
https://ai.google.dev/gemini-api/terms
https://ai.google.dev/gemini-api/docs/pricing

## Toppreise und YouTube

- HTML-/MHT-/MHTML-Upload bleibt im Import-Tab. Eine einzelne Quelle reicht.
- Nur bei „Neue Toppreise“ ist die Bestätigung der 48-Stunden-Auswahl erforderlich.
- Ein importiertes Signal öffnest du über „Deal + Social vorbereiten“ und ersetzt
  dort den Vergleichslink durch den konkreten Händlerlink.
- YouTube ist optional. Für die Suche `YOUTUBE_API_KEY` aus einem Google-Projekt mit
  aktivierter YouTube Data API v3 hinterlegen; auf diese API einschränken.
  Dies ist ein anderer Dienst als Gemini.
- Vorhandene passende Video-URLs erhalten auf der Deal-Seite Thumbnails. Neue Suche
  ist im Editor möglich; auch die vorhandene Publikationsanreicherung bleibt bestehen.
- Treffer sind nicht automatisch redaktionell geprüft. Titel/Variante kontrollieren.
  Die Thumbnails werden erst beim Anzeigen der Deal-Seite von YouTube geladen;
  keine eingebetteten Videoplayer und keine automatische Wiedergabe.

## Betrieb und Grenzen

Der lokale Renderer liefert PNGs in 1080×1350 (Feed) und 1080×1920 (Story/TikTok).
PNG-Bilder liegen mit den Texten in der bestehenden SQLite-Datenbank und sind nur
im Adminbereich abrufbar. Backups umfassen damit auch die Social-Pakete. Speicherbedarf
wächst mit der Zahl der Pakete; Löschen eines Deals entfernt sein Paket.

Netzwerkabrufe sind grössenbegrenzt, verwenden öffentliche HTTPS-Adressen, prüfen
TLS und pinnen die aufgelöste öffentliche IP gegen DNS-Rebinding. Auch Weiterleitungen
werden neu geprüft. Blockierte Seiten und JavaScript-only-Shops bleiben Ausnahmen
zur manuellen Bearbeitung. Kein Captcha-Umgehen, keine Proxies und keine Anmeldung
beim Händler. Es gibt keinen flächendeckenden Bestpreisnachweis oder automatischen
Gutscheintest. Ein Angebot aus einem Händlerlink wird nicht als günstigster Shop
in der ganzen Schweiz bezeichnet.

Der vorhandene Ablauf nach 48 Stunden bleibt bestehen. Abgelaufene Deal-Seiten
bleiben im Archiv; Social-Posts musst du auf den Plattformen selbst aktualisieren.
Ein öffentliches Herstellerfoto oder ein Google-Suchtreffer ist keine automatische
Nutzungserlaubnis.

Validierung: 99 lokale Tests bestanden, darunter Tests mit simulierten Händler-/Gemini-Antworten, vollständige
Regressionstests, Ruff, Bandit, Syntaxprüfung und pip-audit ohne bekannte Schwachstellen sowie visuelle Prüfung der lokal
berechneten Feed-/Story-Karten. Ein echter Gemini-Aufruf und der Betrieb auf deinen
Orbit-Instances benötigen deinen Schlüssel und das Deployment; nicht live verifiziert.
