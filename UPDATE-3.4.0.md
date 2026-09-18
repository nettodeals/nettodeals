# NettoDeals 3.4.0: Installation und Redaktion

## Was sich ändert

Der zentrale Einstieg ist wieder `/admin`. Der separate Steckbrief-Block ist von
der Homepage entfernt. Bereits veröffentlichte Artikel bleiben unter ihren alten
URLs erreichbar; sie werden nicht automatisch in Angebote umgewandelt, weil ihnen
verifizierbare Preise, Händler und Produktbilder fehlen können. Die alte Verwaltung
unter `/admin/redaktion` dient noch dem Bestand; ihr Scheduler läuft nicht mehr.

Neu veröffentlichte Deals benötigen:

- Shopname und direkten HTTPS-Shoplink. Ein normaler provisionsfreier Link genügt.
- Positiven Angebotspreis und Preisprüfung innerhalb der letzten 48 Stunden.
- Direkte HTTPS-Produktbildadresse, Rechtegeber und bestätigtes Nutzungsrecht.
- Bei eingetragener UVP: Link zur offiziellen Herstellerquelle. Andernfalls UVP 0.

YouTube-Key und Affiliate-Partner sind keine Voraussetzungen. Produktbild und
Preis dürfen nicht erfunden werden. Die App kann eine manuell bestätigte UVP oder
eine Bildlizenz nicht selbst verifizieren. Eine UVP ist kein früherer Marktpreis.
Die Prozentersparnis wird abgerundet, um den Rabatt nicht nach oben aufzurunden.

## Produktbilder ergänzen – auch auf Android

1. Im Adminbereich bei einem Entwurf „Produktbild recherchieren“ oder
   „Hersteller & UVP suchen“ öffnen.
2. Möglichst das offizielle Presse-/Medienportal des Herstellers verwenden. Prüfe,
   ob die Bedingungen die konkrete Nutzung auf deiner Website erlauben.
3. Falls du Google-Bildersuche verwendest: zur Originalseite wechseln. Eine Anzeige
   in der Suche oder ein Google-Vorschaubild ist keine Nutzungserlaubnis. Googles
   Nutzungsrechte-Filter hilft bei der Recherche; die Lizenz beim Anbieter prüfen.
4. Die direkte Bildadresse kopieren (z.B. JPG, PNG, WebP), nicht die URL der
   Google-Ergebnisseite und nicht einfach die Produktseite.
5. Unter „Bild, Aktionspreis & Shop ergänzen“ Bild-URL und Rechtegeber eintragen.
   Die Vorschau muss das korrekte Produkt zeigen. Nutzungsrecht bestätigen.
6. Bei Hersteller-UVP den CHF-Wert für das richtige Modell/Variante/Land und die
   Herstellerseite als Quelle eintragen. Keine EUR-UVP als CHF übernehmen.

Die App lädt Bilder im Besucherbrowser vom angegebenen Host, ohne Referrer.
Sie betreibt kein Google-Scraping und kopiert keine fremden Bilder automatisch.
Hotlink-Sperren oder später gelöschte externe Bilder können die Darstellung
verhindern; das erkennt die Vorschau beim Einpflegen, nicht ein permanenter Crawler.
Bei Bedarf ein erlaubtes Bild auf deinem eigenen HTTPS-Medienhost bereitstellen.
Die serverseitige Pflichtprüfung validiert URL/Bestätigung, nicht Bildinhalt oder Lizenz.

## Aktionspreise und Veröffentlichung

Unter `/admin` einen Import-Entwurf öffnen. Über „Signalquelle prüfen“ das Angebot
recherchieren. Den konkreten Händler, direkten Produktlink und aktuellen Endpreis
eintragen. „Provisionsfreier Händlerlink“ wählen, wenn kein Affiliate-Vertrag besteht.
Es gibt keine automatische Garantie, dass dieser Shop tatsächlich der günstigste ist.

Der Endpreis im Entwurfseditor ist bereits inklusive bestätigter Abzüge. Beim
Speichern werden alte importierte Gutschein-/Bonusabzüge zurückgesetzt, damit sie
nicht doppelt abgezogen werden. Gutscheinbedingungen und erforderlichen Code angeben.
Die manuelle Neuerfassung hat weiterhin getrennte Felder für Basispreis und Abzüge.

Speichern bestätigt die Preisprüfung zum aktuellen Zeitpunkt. „Jetzt veröffentlichen“
stellt den Deal sofort online. „Für Zeitplan freigeben“ legt ihn in die Warteschlange.
Im oberen Adminbereich den Zeitplan aktivieren und 6, 12 oder 24 Stunden wählen.
Die erste Veröffentlichung erfolgt beim nächsten Scheduler-Lauf, normalerweise
innerhalb einer Minute. Danach höchstens ein Deal pro Intervall, kein Nachhol-Stapel.

Bei zu altem Preisstand oder fehlenden Pflichtangaben bleibt der Deal Entwurf; die
Warteschlange zeigt `failed` und die Ursache. Prüfen, speichern und erneut freigeben.
Nach dem Bearbeiten eines vorgemerkten Entwurfs erneut freigeben. `processing`
bedeutet, dass die Veröffentlichung gerade läuft. Nach einem Prozessabbruch kann
dieser Status eine manuelle Prüfung erfordern; nicht während eines laufenden
Publikationsvorgangs erneut klicken. Die App muss für den Zeitplan dauerhaft laufen.

Nach Veröffentlichung bleiben Deals standardmässig 48 Stunden aktiv, höchstens bis
zum bekannten früheren Ablaufdatum. Danach verschiebt die bestehende Routine sie
in „Vergangene Deals“; der Hintergrundlauf erfolgt ungefähr alle zehn Minuten.
Das ist zeitbasiert und keine automatische Prüfung des Lagerbestands beim Händler.

## YouTube: richtige API und Einfügeort

Benötigt wird die **YouTube Data API v3** für die Suche nach öffentlichen Videos.
Für diese öffentliche Suche genügt ein API-Key; kein YouTube-Login der Besucher,
kein OAuth-Client, keine YouTube Analytics API und keine kostenpflichtige Publishing-App.

1. https://console.cloud.google.com/ öffnen und ein Projekt erstellen/auswählen.
2. Unter „APIs und Dienste“ die API-Bibliothek öffnen.
3. „YouTube Data API v3“ suchen und aktivieren.
4. Unter „Anmeldedaten“ einen API-Schlüssel erstellen.
5. Den Schlüssel unter API-Einschränkungen auf „YouTube Data API v3“ beschränken.
   Der Abruf erfolgt serverseitig: eine Browser-Referrer-Beschränkung passt nicht.
   Eine IP-Beschränkung nur setzen, wenn du die festen ausgehenden Server-IPs kennst.
6. In deiner Orbit-App im bereits verwendeten ENV-Bereich eine Variable setzen:

   Name: `YOUTUBE_API_KEY`

   Wert: dein tatsächlicher API-Schlüssel, ohne umgebende JSON-Anführungszeichen
   und ohne abschliessendes Komma.

7. Änderungen speichern und die Anwendung mit der neuen Umgebung neu starten.
   Falls deine Oberfläche weiterhin maximal 20 Variablen erlaubt, den vorhandenen
   gleichnamigen Eintrag bearbeiten statt einen doppelten anzulegen.

Der Key gehört nicht in GitHub, HTML oder einen Chat. Eine lokale `.env` wird durch
den bisherigen Startbefehl nicht automatisch eingelesen; auf Orbit die ENV-Felder nutzen.
Bei manueller Serverkonfiguration kann Uvicorn ausdrücklich mit `--env-file` starten.

Bei Veröffentlichung sucht die App nach bis zu drei Videos zum Produktnamen mit
„Test Review“, Region CH und Sprachpräferenz Deutsch. Die Suchtreffer sind keine
geprüften Produkttests; Modelltreue und Unabhängigkeit sind nicht garantiert.
Fehlt der Key oder scheitert die API (z.B. Kontingent), wird trotzdem veröffentlicht.
Bereits veröffentlichte Deals werden durch Eintragen des Keys nicht rückwirkend ergänzt.
Das tatsächliche Kontingent im Google-Projekt prüfen; es wird kein unbegrenzter
API-Zugriff versprochen. Es wurden keine Anfragen mit deinem Key durchgeführt.

Offizielle Anleitungen:
- https://developers.google.com/youtube/v3/getting-started
- https://developers.google.com/youtube/v3/guides/authentication
- https://support.google.com/websearch/answer/29508?hl=de

## Update mit Termux

Zuerst die produktive Datenbank konsistent sichern (SQLite-Backup mit WAL-Berücksichtigung)
und die aktuellen Orbit-ENV-Einstellungen sichern. Keine Instances löschen.
Das ZIP basiert auf GitHub-main `c3e9d5c` (3.3.0). Spätere eigene Änderungen vorher
vergleichen, insbesondere Impressum/Datenschutz. Keine Datenbank oder echte ENV-Datei
ist im Paket enthalten.

ZIP `nettodeals-3.4.0.zip` in Android-Downloads speichern, dann in Termux:

```sh
cd ~/netto-update-v311/repo
git status --short
```

Wenn Änderungen oder unbekannte Dateien erscheinen: anhalten und prüfen. Bei deinem
früheren Update gab es versehentlich erzeugte Befehlsfragmente als Dateien; diese
nicht mit `git add --all` übernehmen. Erst mit sauberem Arbeitsverzeichnis fortfahren.

```sh
git fetch origin --prune
git switch main
git pull --ff-only origin main
git switch -c release/3.4.0
unzip -t ~/storage/downloads/nettodeals-3.4.0.zip
update_dir=$(mktemp -d "$HOME/nettodeals-v340.XXXXXX")
unzip ~/storage/downloads/nettodeals-3.4.0.zip -d "$update_dir"
head -1 "$update_dir/CHANGELOG.md"
cp -R "$update_dir"/. .
git diff --stat
git diff -- nettodeals/templates/info.html
python -m compileall -q main.py nettodeals tests
git add --all
git diff --cached --stat
git commit -m "Release 3.4.0"
git log -1 --oneline
git push -u origin release/3.4.0
gh pr create --repo nettodeals/nettodeals --base main --head release/3.4.0 --title "NettoDeals 3.4.0" --body "Einheitlicher Deal-Workflow, Produktbilder und Aurora-Preiskarten."
```

Bei einem Fehler stoppen. Vor `push` muss ein neuer Commit sichtbar sein.
Auf GitHub Änderungen und grüne CI prüfen, dann den Pull Request zusammenführen.
Orbit anschliessend normal von `main` aktualisieren; kein Hard Redeploy erforderlich.
Nach dem Start zeigt `/api/status` Version 3.4.0. Neue Tabellen/Spalten werden additiv
angelegt. Daten und alte Artikel bleiben erhalten. Bestehende veröffentlichte Deals
werden nicht ungefragt zurückgezogen; Bildrechte und UVP-Quellen bei Altbestand prüfen.

Der neue Zeitplan startet deaktiviert. Bei zwei Flux-Instances mit getrennten SQLite-
Datenbanken können unterschiedliche Inhalte erscheinen. Vor Aktivierung muss eine
konsistente Datenhaltung bestehen; diese Version führt keine Datenreplikation ein.
Die Absicherung gegen gleichzeitige Scheduler gilt für dieselbe lokale SQLite-Datei.

## Umfang und Prüfung

Keine bezahlten Publishing-Dienste. Kein automatischer Social-Upload. Alte
Steckbrief-Social-Downloads bleiben verfügbar; neue Deal-Veröffentlichungen erzeugen
in dieser Version keine neuen Steckbrief-Exportpakete.

61 erfolgreiche automatische Tests prüfen unter anderem Veröffentlichung ohne Partner/YouTube,
YouTube-Ausfall, Bildpflicht, UVP-Quellenpflicht, Preisalter, Preis-/Rabattanzeige,
Warteschlange, parallele Scheduler, CSRF und Entzug einer Freigabe nach Bearbeitung.
Die Bildlizenz, konkrete Händlerpreise und deine Orbit-Konfiguration sind redaktionell
beziehungsweise im produktiven System zu prüfen.

Zusätzlich bestanden Ruff, Bandit und die Python-Syntaxprüfung. Eine visuelle
Browserprüfung konnte in der Arbeitsumgebung nicht durchgeführt werden, weil der
Testbrowser-Download scheiterte. Deshalb nach dem Deployment besonders die mobile
Darstellung und die echten externen Produktbilder kontrollieren.
