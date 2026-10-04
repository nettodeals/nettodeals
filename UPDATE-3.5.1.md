# NettoDeals 3.5.1: Gemini ohne Orbit-ENV + Google Analytics

Vollständiges Repository und Update-Patches auf Grundlage von GitHub main,
Commit 836dfc00a1d30b8a0582776633f7ba486e89c44f (3.5.0).

## Enthalten

- Gemini im Admin einrichten, Modell wählen, speichern, testen, deaktivieren und entfernen.
- Fernet-verschlüsselter Schlüssel in der bestehenden Datenbank, geschützt durch einen
  getrennt abgeleiteten Schlüssel aus dem vorhandenen ADMIN_TOKEN.
- Keine neue Orbit-Variable. Gespeicherte Änderungen wirken sofort ohne Neustart.
- Verbindungstest erzeugt eine kurze Textantwort vom Server aus.
- Test und Redaktion teilen sich 10 Versuche pro UTC-Tag/Datenbank, auch Fehler zählen.
- Standardmodell gemini-3.1-flash-lite, im Admin änderbar.
- Komplettes Analytics-Update G-GQGD9NXG70: Aurora-Einwilligung, Widerruf und Admin-Ausschluss.
- Bestehende Deals bleiben erhalten. Die Datenbankmigration ergänzt eine Tabelle.
- Neue Python-Abhängigkeit: cryptography==50.0.2.

## Termux: Update

ZIP als nettodeals-3.5.1.zip in den Android-Download-Ordner laden.
Befehle blockweise kopieren, ohne Terminal-Prompt-Zeichen.

~~~sh
termux-setup-storage
pkg install unzip
unzip ~/storage/downloads/nettodeals-3.5.1.zip -d ~/nettodeals-update-351
cd ~/netto-update-v311/repo
git config --local core.pager cat
git status -sb
~~~

Bei lokalen Änderungen stoppen, nichts löschen oder pauschal mit git add --all
aufnehmen. Unbekannte Dateien aus früheren Fehleingaben nicht committen.

Bei sauberem Arbeitsverzeichnis:

~~~sh
git fetch origin --prune
git switch main
git pull --ff-only origin main
git switch -c release/3.5.1
~~~

### Von 3.5.0 aktualisieren

~~~sh
git apply --check ~/nettodeals-update-351/update-from-3.5.0.patch
~~~

Keine Ausgabe bedeutet: Prüfung erfolgreich. Erst dann:

~~~sh
git apply --index ~/nettodeals-update-351/update-from-3.5.0.patch
~~~

### Nur wenn der vorherige Analytics-Patch bereits auf main installiert ist

Statt der beiden vorigen Befehle:

~~~sh
git apply --check ~/nettodeals-update-351/update-after-analytics.patch
~~~

Bei erfolgreicher Prüfung:

~~~sh
git apply --index ~/nettodeals-update-351/update-after-analytics.patch
~~~

Nur EINEN Patch anwenden. Bei Fehlern stoppen und Meldung weitergeben, nicht
erzwingen. Der Ordner repository/ enthält die vollständige Referenzversion.
Der Patch erkennt abweichende Dateien und ist der bevorzugte Update-Weg.

### Commit, Push und Pull Request

~~~sh
git diff --cached --stat
git commit -m "Release NettoDeals 3.5.1: Gemini setup and consent analytics"
git push -u origin release/3.5.1
~~~

Erst nach erfolgreichem Commit und Push:

~~~sh
gh pr create --repo nettodeals/nettodeals --base main --head release/3.5.1 --title "NettoDeals 3.5.1" --body "Gemini im Admin verwalten, Verbindungstest, verschluesselte Speicherung und Google Analytics mit Einwilligung."
~~~

Auf GitHub die CI-Prüfungen abwarten und nur bei erfolgreichen Prüfungen zusammenführen.
Bei „No commits between …“ zunächst git status -sb und git log -3 --oneline prüfen.

## Auf Orbit deployen

Den zusammengeführten main-Stand neu bauen und deployen. Der Build muss die neue
requirements.txt installieren; ein reiner Prozessneustart genügt nicht.
Instanzen und Datenbank-Volume nicht löschen. Unter /api/status muss 3.5.1 stehen.

In Termux keine Python-Abhängigkeiten dieser Website installieren: Termux dient zum
Git-Update, Orbit/GitHub übernehmen Build und Tests.

## Gemini im Browser einrichten

1. Admin anmelden und den neuen Menüpunkt **Gemini** öffnen, alternativ:
   https://nettodeals.ch/admin/settings/gemini
2. Schlüssel in Google AI Studio erstellen: https://aistudio.google.com/api-keys
3. Schlüssel ausschliesslich in das Passwortfeld der Adminseite einfügen.
4. Modell prüfen, beispielsweise gemini-3.1-flash-lite.
5. **Gemini aktivieren** anhaken und **Einstellungen speichern** wählen.
6. Die Bestätigung zum API-Test anhaken und **Verbindung testen** drücken.
7. Bei Erfolg unter **Entwürfe** den **Deal & Social**-Editor öffnen.
8. Fakten prüfen, **Gemini verwenden** wählen, **Deal + Social vorbereiten** drücken.
9. Texte anschliessend prüfen und freigeben.

Für den kostenlosen Versuch ein geeignetes Google-Projekt im Free Tier verwenden.
Modellverfügbarkeit und Kontingent dort kontrollieren. Die App kann den
Abrechnungstarif nicht erkennen oder Kosten bei einem kostenpflichtigen Projekt
verhindern. Auch der Verbindungstest ist ein API-Aufruf.

Keine KI-Aufrufe beim App-Start, keine automatische KI-Publikation. Bilder werden
weiterhin lokal im Aurora-Layout erstellt. Social-Beiträge bleiben manuelle Exporte.

## Speicherung und mehrere Instanzen

- Admin-Einstellungen haben Vorrang vor GEMINI_API_KEY und GEMINI_MODEL aus Orbit.
- Leeres Schlüsselfeld beim Speichern behält den bisherigen Schlüssel.
- Deaktivieren behält den Schlüssel; Entfernen überschreibt den gespeicherten Wert
  und hält Gemini deaktiviert. Ein alter ENV-Schlüssel wird nicht wieder aktiviert.
- Der gespeicherte Schlüssel wird nie ins Formular oder die öffentliche Status-API
  zurückgegeben.
- Nach Änderung des ADMIN_TOKEN den API-Schlüssel erneut speichern.
- Verschlüsselung ersetzt keine Server-Zugriffskontrolle: Wer Datenbank und Admin-Token
  besitzt, kann den Schlüssel entschlüsseln.
- Backups können alte verschlüsselte Schlüssel enthalten. Kompromittierte Schlüssel
  zusätzlich bei Google widerrufen.
- Speicherung überlebt Neustarts nur bei Wiederverwendung derselben Datenbank.
  Nach Hard Redeploy mit neuem/leeren Volume erneut konfigurieren.
- Bei zwei Flux-Instanzen mit getrennten Datenbanken jede Instanz separat konfigurieren.
  Die Einstellungsseite zeigt die aktuell erreichte Instanzkennung; sie kann sich nach
  Container-Neubau ändern. Wiederholte Testaufrufe sind kein zuverlässiger Weg zur
  Auswahl der Instanz.
- Falls Orbit keine gezielte Instanzadresse anbietet, ist eine zuverlässige Zuordnung
  oder gemeinsame Datenhaltung erforderlich. Dieses Update synchronisiert keine
  getrennten Deal-Datenbanken.
- Zehn Versuche gelten pro Datenbank, nicht global über getrennte Instanzen hinweg.

## Analytics

Die Integration ist bereits enthalten; den früheren Analytics-Patch nicht zusätzlich
anwenden. Weitere Details in UPDATE-ANALYTICS.md (im Repository-Ordner).

Vor dem Einsatz im GA4-Webstream zusätzliche **Optimierte Analysen** ausschalten.
Normale Seitenaufrufe werden weiterhin vom Tag gesendet. Google Signals und
Werbepersonalisierung nicht einschalten, Aufbewahrungsdauer bewusst einstellen.
Keinen zweiten Analytics-Tag einbauen.

Nach Deploy im privaten Browserfenster:
- Vor Zustimmung bzw. nach Ablehnung kein Google-Tag aus der Analysefunktion.
- Zustimmung erteilen und GA4-Echtzeitbericht prüfen.
- „Datenschutz-Einstellungen“ am Seitenende ermöglicht Widerruf.
- Adminseiten enthalten keinen Analytics-Code.
- Nur zustimmende, nicht blockierte Besucher werden gemessen; keine rückwirkenden Daten.

## Fehler einordnen

- Nicht aktiv: aktivieren und speichern; bei wechselndem Zustand Instanzkennung prüfen.
- Einstellungen nicht lesbar: nach Admin-Token-Wechsel Schlüssel neu speichern.
- HTTP 400/401: Schlüssel/Projektkonfiguration prüfen; keine Anführungszeichen mitkopieren.
- HTTP 403: Schlüsselbeschränkungen, Projekt-/Regionsfreigabe oder Hosting-Verbindung
  prüfen; kein Beweis für eine Modellsperre. Reine Browser-Referrer-Beschränkungen
  passen nicht zu serverseitigen Anfragen.
- HTTP 404: Modell-ID und Modellfreigabe prüfen.
- HTTP 429: Google-Kontingent erreicht oder nicht verfügbar.
- Pilotlimit: nächsten UTC-Tag abwarten.
- Netzwerk/TLS/Zeitüberschreitung: Verbindung vom Orbit-Server zu Google prüfen.
  Ein erfolgreicher AI-Studio-Test im Browser beweist keine Server-Erreichbarkeit.

API-Sperren oder fehlendes Google-Kontingent können nicht umgangen werden.
Textvorlagen bleiben auch ohne Gemini verfügbar.

## Validierung und Grenzen

Automatisierte Tests verwenden simulierte Google-Antworten. Geprüft werden
Verschlüsselung, Schlüsselwechsel, Neustart, Authentifizierung, CSRF, ENV-Vorrang,
Deaktivierung, Tageslimit und Fehlermeldungen ohne Geheimnisse.

Ein echter Gemini-Aufruf von deiner Orbit-Instanz ist erst nach Eingabe deines
Schlüssels möglich. Es wurde kein echter Schlüssel angefordert oder verwendet.
Analytics wurde mit JavaScript-Tests geprüft; ein echter Browser-/Netzwerktest
war hier nicht möglich. Nach Deploy Gemini-Verbindungstest und GA4-Echtzeit prüfen.

Das ZIP enthält weder echte API-Schlüssel noch Produktionsdatenbank oder Git-Verlauf.
