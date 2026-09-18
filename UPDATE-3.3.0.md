# Update auf NettoDeals 3.3.0 mit Termux

## Was automatisch läuft – und was nicht

Die Website veröffentlicht freigegebene Produktsteckbriefe aus deiner Warteschlange.
Affiliate-Partner sind dafür nicht erforderlich. Der Zeitplan ist zunächst aus.
Die Texte entstehen lokal aus einer Vorlage und den von dir bestätigten Fakten;
es gibt keine kostenpflichtige KI- oder Publishing-Schnittstelle.

Für jede Veröffentlichung werden Texte und eigene PNG-Grafiken für X, Instagram
und TikTok vorbereitet. Du lädst diese im Adminbereich herunter und veröffentlichst
sie selbst in der jeweiligen App. „Als geteilt markieren“ ist deine eigene
Bestätigung, keine technische Überprüfung des Posts. Vollautomatisches Crossposting
ist **nicht** Bestandteil dieser Version. Bestehende Hostingkosten bleiben bestehen.

Die Warteschlange füllt sich nicht von selbst: vorhandene Toppreise-Importe können
gesammelt ausgewählt werden. Neue Quellen musst du weiterhin importieren und freigeben.
Ein Artikel belegt kein aktuelles Preisminimum, keinen Rabatt und keine Verfügbarkeit.
Für echte Preisangebote bleibt der bisherige Deal-Workflow mit belegbaren Angaben.

## 1. Vorbereiten und sichern

Lade `nettodeals-3.3.0.zip` auf dein Android-Gerät herunter. Öffne Termux.
Die Befehle sind einzeln einzugeben; die angezeigten Prompt-Zeichen nicht mitkopieren.

```sh
termux-setup-storage
pkg install git unzip gh
cd ~/netto-update-v311/repo
git status --short
```

Falls der letzte Befehl Änderungen anzeigt: **anhalten**, zuerst sichern oder committen.
Keine Dateien im Repository löschen. Sichere vor dem Deployment ausserdem deine
laufende SQLite-Datenbank mit einem konsistenten SQLite-Backup sowie die Host-
Konfiguration. Eine Kopie nur der laufenden `.db` ohne WAL kann unvollständig sein.
Die Git-Dateien enthalten nicht deine produktiven Daten oder Geheimnisse.

## 2. Aktuellen Hauptzweig holen und Update-Zweig anlegen

```sh
git fetch origin --prune
git switch main
git pull --ff-only origin main
git switch -c release/3.3.0
```

Bei einem Fehler stoppen. Existiert der Zweig bereits, prüfe ihn zuerst statt ihn
zu überschreiben. Das Paket basiert auf Version 3.2.0 (Commit `c756d23`). Falls du
seither eigene Änderungen gemacht hast, diese vor dem Kopieren mit dem Paket
vergleichen; insbesondere Impressum, Datenschutz und individuelle Templates.

## 3. Paket entpacken und Dateien übernehmen

```sh
unzip -t ~/storage/downloads/nettodeals-3.3.0.zip
mkdir -p ~/netto-update-v330
unzip -n ~/storage/downloads/nettodeals-3.3.0.zip -d ~/netto-update-v330
head -1 ~/netto-update-v330/CHANGELOG.md
```

Die erste Zeile muss „NettoDeals 3.3.0“ enthalten. Verwende einen frischen
Zielordner; `unzip -n` überschreibt keine vorher entpackten Dateien.
Dann im Repository:

```sh
cd ~/netto-update-v311/repo
cp -R ~/netto-update-v330/. .
git diff --stat
git diff -- nettodeals/templates/info.html
git status --short
python -m compileall -q main.py nettodeals tests
```

Das Archiv enthält keine `.git`-Historie, echten `.env`-Dateien oder Datenbanken.
Es enthält die vollständigen Projektdateien einschliesslich CI-Konfiguration.
`compileall` ist nur eine Syntaxprüfung. Die vollständigen Tests laufen in GitHub
Actions auf Linux; native Python-Abhängigkeiten müssen nicht in Termux gebaut werden.

## 4. Auf GitHub prüfen und zusammenführen

```sh
git add --all
git diff --cached --stat
git commit -m "Release 3.3.0: free editorial publishing and social export"
git push -u origin release/3.3.0
gh pr create --base main --head release/3.3.0 --title "NettoDeals 3.3.0" --body "Kostenlose Steckbriefe, redaktioneller Zeitplan und manuelle Social-Exports."
```

Öffne den angezeigten Pull Request auf GitHub. Kontrolliere „Files changed“ und
warte auf grüne Tests. Erst dann „Merge pull request“ ausführen. Falls GitHub eine
Anmeldung verlangt, `gh auth login` verwenden; Token nicht in Chats oder Commits setzen.

## 5. Auf Orbit aktualisieren

Der Deployment-Zweig muss `main` sein. Nutze den normalen Pull/Build- bzw.
Deployment-Ablauf deiner bestehenden App. Ein Hard Redeploy oder Löschen der
Instances ist für diese Änderung nicht nötig. Persistentes Datenvolume und
bestehende ENV-Einstellungen beibehalten. Es werden keine neuen ENV-Variablen benötigt.

Die neue Pillow-Abhängigkeit wird beim Build aus `requirements.txt` installiert.
Beim App-Start werden neue Tabellen additiv angelegt. Kontrolliere die Build-/App-
Logs und `/api/status` (Version `3.3.0`). Die Anwendung muss dauerhaft laufen,
damit der Zeitplan arbeitet. Verpasste Intervalle werden nicht schlagartig nachgeholt.

**Wichtig bei zwei Flux-Instances:** Zwei getrennte lokale SQLite-Datenbanken sind
nicht synchron. Freigaben, Artikel und Zeitpläne können zwischen den Instanzen
abweichen. Diese Version löst keine instanzübergreifende Datenreplikation. Aktiviere
den produktiven Zeitplan erst, wenn Schreibzugriffe und öffentliche Auslieferung
auf eine konsistente Datenbasis zeigen. Eine SQLite-Datei nicht ungeprüft über ein
Netzlaufwerk gemeinsam verwenden. Die Tests gegen Doppelpublikation gelten für
mehrere Zugriffe auf dieselbe lokale SQLite-Datenbank.

## 6. Erste kostenlose Beiträge veröffentlichen

1. Unter `/admin/redaktion` anmelden oder im bisherigen Adminbereich auf
   „Kostenlose Redaktion öffnen“ tippen.
2. Einen Steckbrief erfassen: Titel, Kategorie, eigene belegte Fakten, HTTPS-Quelle,
   Quellenname und Datum der tatsächlichen Quellenprüfung. Keine fremden Reviews
   kopieren. Das Datum nicht künstlich aktualisieren.
3. Bestätigung anklicken und sofort veröffentlichen oder in die Warteschlange legen.
   Alternativ mehrere vorhandene importierte Produkte ausdrücklich auswählen und
   mit bestätigtem Quelldatum freigeben. Dabei werden keine Preise, fremden Bilder
   oder Beschreibungen übernommen.
4. Gewünschtes Intervall (6/12/24 Stunden) aktivieren. Die erste Freigabe kann beim
   nächsten Scheduler-Lauf innerhalb etwa einer Minute erscheinen. Als Startwert
   sind 12 Stunden vorgesehen. Quellen älter als sieben Tage werden nicht publiziert.
5. Unter „Social Media“ je Plattform ZIP herunterladen, Text kopieren und PNG in
   der Plattform-App hochladen. Danach bei Bedarf manuell als geteilt markieren.

TikTok bekommt eine 9:16-Fotokarte, kein Video; Instagram und X eine 4:5-Karte.
Links in Instagram-Bildunterschriften sind nicht automatisch anklickbar: den
gewünschten Link separat im Profil pflegen. Prüfe Plattformvorschau, Textlänge,
Quellenangaben und gegebenenfalls Werbekennzeichnung vor dem Senden.

## Pflege und Grenzen

- Steckbriefe bleiben als redaktionelle Artikel sichtbar; nach sieben Tagen wird
  ihr älterer Quellenstand gekennzeichnet. Sie werden nicht als aktive Rabatte ausgegeben.
- Echte Deals behalten den bisherigen Ablauf-/Archivierungsmechanismus.
- „Zurückziehen“ nimmt einen Steckbrief von der Website; bereits manuell gepostete
  Social-Beiträge musst du auf der jeweiligen Plattform selbst entfernen/korrigieren.
- Veröffentlichten Artikel zurückziehen, bearbeiten und erneut veröffentlichen
  aktualisiert die Exporttexte. Ein bereits geteilter externer Beitrag ändert sich nicht.
- Eigene Typografiekarten ersetzen fehlende lizenzierte Produktfotos, nicht echte
  Produktabbildungen. Es werden keine Bilder von Toppreise oder Shops kopiert.
- Keine Zugangsdaten zu X, Meta oder TikTok erforderlich. Es finden keine externen
  Testposts statt.

## Geprüft

51 automatisierte Tests inklusive quellendatierter Freigaben, Scheduler-Neustart,
gleichzeitiger Scheduler-Aufrufe, Archiv-/Entwurfs-Trennung, CSRF, XSS-Escaping,
authentifizierter Exporte, Bildformate, Pagination und Erhalt vorhandener Daten.
Zusätzlich Syntaxprüfung, Ruff, Bandit und Abhängigkeitsprüfung. Eine erfolgreiche
lokale Prüfung ersetzt nicht den Smoke-Test auf deiner produktiven Flux-Umgebung.
