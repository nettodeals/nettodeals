# NettoDeals 3.4.1 – Groq mit zehn echten Angeboten testen

Das Paket basiert auf GitHub-main `79c8c32` (zusammengeführtes Update 3.4.0).
GitHub und Orbit wurden nicht geändert. Der echte API-Test benötigt deinen eigenen
Groq-Schlüssel. Die lokale Prüfung verwendete simulierte Antworten, keine Live-KI.

## 1. Groq vorbereiten

1. https://console.groq.com/ öffnen und ein Konto erstellen/anmelden.
2. Prüfen, dass du den kostenlosen Tarif verwendest. Keine kostenpflichtige
   Umstellung für diesen Pilot vornehmen.
3. In der API-Key-Verwaltung https://console.groq.com/keys einen eigenen Schlüssel
   für NettoDeals erstellen. Diesen nicht in Chat, GitHub oder Screenshots teilen.
4. In den Kontoeinstellungen kontrollieren, ob `openai/gpt-oss-20b` freigegeben ist
   und welches Anfrage-/Tokenkontingent für dein Konto gilt.

Der Pilot ruft Groq direkt auf, nicht OpenAI. Der Modellname enthält zwar „openai“,
aber du brauchst nur einen Groq-Schlüssel. Es gibt keinen kostenpflichtigen
Ausweichanbieter und kein automatisches Upgrade.

Wichtig: Die App kann deinen Groq-Abrechnungstarif nicht feststellen. Ein Schlüssel
aus einem kostenpflichtigen Konto kann Kosten verursachen. Das lokale Tageslimit
begrenzt Anfragen, garantiert aber keinen Nullbetrag beim Anbieter. Anbieterlimits
können sich ändern. Das API-Konto muss ausdrücklich kostenlos bleiben.

## 2. Update in Termux

Produktive Datenbank und ENV-Einstellungen zuerst sichern. ZIP in Android-Downloads
speichern. Befehle einzeln eingeben, nie in eine noch geöffnete Git-Seitenanzeige.

```sh
cd ~/netto-update-v311/repo
git config --local core.pager cat
git status --short
```

Bei Änderungen an Projektdateien anhalten und sichern. Falls noch die versehentlich
angelegten Dateien `tatus -sb`, `witch main` oder `e ...` auftauchen: diese nicht
vormerken. Die untenstehenden gezielten `git add`-Pfade lassen solche Dateien im
Repository-Hauptordner aus. Bereits vorgemerkte Fremddateien vorher mit
`git restore --staged .` aus der Vormerkung nehmen; ihre Inhalte bleiben erhalten.

Mit sauberem Stand der Projektdateien fortfahren:

```sh
git fetch origin --prune
git switch main
git pull --ff-only origin main
git switch -c release/3.4.1
unzip -t ~/storage/downloads/nettodeals-3.4.1-groq-pilot.zip
update_dir=$(mktemp -d "$HOME/nettodeals-groq.XXXXXX")
unzip ~/storage/downloads/nettodeals-3.4.1-groq-pilot.zip -d "$update_dir"
head -1 "$update_dir/CHANGELOG.md"
cp -R "$update_dir"/. .
git --no-pager diff --stat
python -m compileall -q main.py nettodeals tests
git add -- README.md CHANGELOG.md UPDATE-GROQ-PILOT.md .env.example nettodeals/ tests/
git --no-pager diff --cached --stat
git commit -m "Release 3.4.1: Groq editorial pilot"
git --no-pager log -1 --oneline
git push -u origin release/3.4.1
gh pr create --repo nettodeals/nettodeals --base main --head release/3.4.1 --title "NettoDeals 3.4.1: Groq-Pilot" --body "Optionaler KI-Textassistent mit manueller Freigabe und begrenzten API-Aufrufen."
```

Nur nach erfolgreichem Commit pushen. Auf GitHub Änderungen und erfolgreiche CI
prüfen, dann zusammenführen. Individuelle Änderungen nach dem genannten Basiscommit
vor dem Kopieren mit dem Paket vergleichen. Normales Orbit-Deployment von `main`
verwenden, keine Instances löschen und kein Hard Redeploy nur für diesen Pilot.

## 3. Auf Orbit konfigurieren

In der App unter dem bereits verwendeten ENV-Bereich hinzufügen:

| Name | Wert |
|---|---|
| `GROQ_API_KEY` | Dein tatsächlicher Groq-Schlüssel |

Nur ein zusätzlicher Eintrag ist nötig. Optional ist `GROQ_MODEL`; ohne Eintrag
nutzt die App `openai/gpt-oss-20b`. Das Modell muss Groqs strikte JSON-Ausgabe
unterstützen. Die Konfiguration der YouTube-API bleibt unabhängig davon.

Keine Anführungszeichen oder Kommas mitkopieren. Die `.env.example` ist nur eine
Vorlage, nicht der Speicherort des echten Schlüssels. Die bestehende Startanweisung
liest keine beliebige `.env` automatisch ein. Änderungen in Orbit übernehmen und
Anwendung mit der neuen Umgebung starten. `/api/status` muss Version 3.4.1 zeigen.

Die App ruft beim Start keine KI auf. Ohne Schlüssel funktioniert der bisherige
Deal-Workflow weiterhin. Entfernen des Schlüssels deaktiviert neue KI-Anfragen;
bereits gespeicherte Entwürfe bleiben erhalten.

## 4. Ersten Deal testen

1. `/admin` öffnen und einen vorhandenen Deal-Entwurf auswählen.
2. Zuerst Bild, Shoplink, Preis, UVP-Quelle und Bildrecht wie bisher pflegen.
3. „Mit KI vorbereiten – Groq-Pilot“ öffnen.
4. In das Faktenfeld ausschliesslich belegte Angaben zur exakten Variante eintragen:
   Modell, tatsächlich vorhandene Ausstattung und Quellenhinweis/Prüfdatum.
   Keine fremden Reviews kopieren, keine Geheimnisse oder Kundendaten einfügen.
5. Quellenprüfung und Übermittlung an Groq bestätigen. „Entwurf vorbereiten“ drücken.
6. Kurzbeschreibung und drei Social-Texte mit den Quellen vergleichen und bei
   Bedarf direkt in den Textfeldern korrigieren.
7. Faktenabgleich bestätigen und „Nur Texte freigeben“ wählen.
8. Zum Deal-Kontrollzentrum zurückkehren und dort separat veröffentlichen oder für
   den vorhandenen Zeitplan freigeben.

Eine neue API-Anfrage entfernt den betreffenden Deal aus der Warteschlange, damit
er nicht während der Vorbereitung automatisch erscheint. Anschliessend wieder
ausdrücklich für den Zeitplan freigeben. Bereits unverändert vorhandene KI-Entwürfe
werden ohne neuen API-Aufruf wiederverwendet. Für eine neue Antwort bei denselben
Fakten erst „KI-Entwurf verwerfen“, dann erneut generieren (verbraucht Kontingent).

Die freigegebene Kurzbeschreibung wird beim Publizieren übernommen, sofern die
Deal-Daten noch zum geprüften Stand passen. Sonst nutzt die Anwendung die bisherige
Textvorlage. Preis-, Bild- und Quellenprüfungen bleiben verpflichtend. Änderungen
am Deal nach der KI-Vorbereitung können den Text ungültig machen: dann neu vorbereiten.
Bereits veröffentlichte Beiträge werden durch neue Textfreigaben nicht still verändert.

Social-Texte sind nur kopierbare Entwürfe. Vor dem manuellen Posten den richtigen
Artikellink, gegebenenfalls Preis-/Quellenstand und passende Kennzeichnung ergänzen.
Die App versendet keine Social-Posts und erstellt hier keine neuen Bilddateien.
Verwerfen eines KI-Entwurfs entfernt keine bereits öffentlich verwendete Beschreibung.

## 5. Die ersten zehn Angebote beurteilen

Pro Angebot notieren:

| Kriterium | Bewertung |
|---|---|
| Exaktes Modell und Variante getroffen? | Ja / Nein |
| Jede genannte Eigenschaft in der Quelle belegt? | Ja / Nein |
| Keine erfundene Nutzungserfahrung oder Testaussage? | Ja / Nein |
| Schweizer Schreibweise und verständliche Sätze? | Ja / Korrektur nötig |
| Korrekturzeit | Minuten |
| Würdest du den Text veröffentlichen? | Ja / Nach Korrektur / Nein |

Erst eine kleine Auswahl durchspielen. Tageslimit: zehn API-Versuche pro UTC-Tag
und gemeinsamer Datenbank; auch Fehler zählen. Eine Anfrage liefert alle vier Texte.
Kein automatischer Retry bei Timeout, Rate Limit oder Kontingentfehler. Innerhalb
einer Anfrage sind Ausgabe und Eingabe begrenzt. Das Anbieterlimit kann früher greifen.

## Grenzen und Datenverarbeitung

- Kein Recherche-Agent: Es werden keine Herstellerseiten aufgerufen, Preise
  recherchiert, Coupons getestet oder Bilderrechte geprüft.
- An Groq gehen Produktname, Kategorie und dein bestätigter Faktentext. Sonstige
  Deal-Felder, Admin-Token und Kundendaten werden nicht automatisch mitgesendet.
- Es werden keine Browser-, Such- oder Codeausführungstools der KI aktiviert.
- Struktur, Länge, HTML-/Link- und offensichtliche Preisangaben werden geprüft.
  Das beweist keine Faktentreue: Auch formal korrekter Text kann Falsches behaupten.
- Texte bleiben bis zur ausdrücklichen menschlichen Freigabe unverwendete Vorschläge.
- Kein eigener KI-Server, keine neue Python-Abhängigkeit, keine bezahlte Publishing-App.
- Bei zwei Flux-Instances mit getrennten SQLite-Dateien sind Entwürfe und Tageslimits
  ebenfalls getrennt. Der Pilot löst keine Datenreplikation. Für den Test eine
  konsistente Datenhaltung beziehungsweise eine feste Testinstanz verwenden.

Offizielle Dokumentation (Stand der Prüfung: 20. September 2026):
- Modelle: https://console.groq.com/docs/models
- Ausgabeformat: https://console.groq.com/docs/structured-outputs
- Kontingente: https://console.groq.com/docs/rate-limits
- Datenverarbeitung und Kontoeinstellungen: https://console.groq.com/docs/your-data

78 lokale Tests bestanden; Ruff, Bandit und Syntaxprüfung bestanden. Darunter:
fehlender Schlüssel, API-Ausfälle, ungültige Ausgabe, Tageslimit, Wiederverwendung,
CSRF, veraltete Daten, manuelle Textfreigabe und Einbindung in den Deal-Zeitplan.
Es wurden weder reale Groq-Ausgaben bewertet noch deine Live-Website verändert.
