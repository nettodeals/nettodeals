# Update auf NettoDeals 3.6.0 mit Termux

Dieses Paket basiert auf main, Commit 2e48ea0f43fd82951d1a086a90839739c73891c5.
Es enthält das vollständige Repository und einen binären Git-Patch inklusive
Otto-Bildern. Google Analytics aus 3.5.1 ist enthalten. Keine neuen Orbit-ENV nötig.

## 1. Herunterladen und entpacken

ZIP als nettodeals-3.6.0.zip im Android-Downloadordner speichern.
Nur Befehle kopieren, keine Prompt-Zeichen. Jeden Block einzeln ausführen.

```sh
termux-setup-storage
pkg install git gh unzip
mkdir -p ~/nettodeals-update-360
unzip ~/storage/downloads/nettodeals-3.6.0.zip -d ~/nettodeals-update-360
cd ~/netto-update-v311/repo
git config --local core.pager cat
git status -sb
```

Bei geänderten oder unbekannten Dateien zuerst sichern/prüfen. Nicht mit git add
--all versehentlich die früheren Dateien „tatus -sb“ oder „witch main“ aufnehmen.
Die folgenden Schritte setzen einen sauberen Arbeitsstand voraus.

## 2. Hauptbranch aktualisieren und Patch anwenden

```sh
git fetch origin --prune
git switch main
git pull --ff-only origin main
git switch -c release/3.6.0
git apply --check ~/nettodeals-update-360/update-from-3.5.1.patch
```

Falls irgendein Befehl fehlschlägt: stoppen und Ausgabe prüfen, nicht erzwingen.
Der Patch ist für die genannte Basis erstellt. Bei zwischenzeitlichen Änderungen
können Konflikte eine individuelle Anpassung erfordern. Bei bereits vorhandenem
Release-Branch erst dessen Stand prüfen; keinen Branch überschreiben.

```sh
git apply --index ~/nettodeals-update-360/update-from-3.5.1.patch
git diff --cached --stat
git commit -m "Release NettoDeals 3.6.0: Otto und Social-Studio"
git push -u origin release/3.6.0
gh pr create --repo nettodeals/nettodeals --base main --head release/3.6.0 --title "NettoDeals 3.6.0" --body "Robuste Gemini-Einrichtung, Social-Entwürfe mit CTA und Otto im Aurora-Design."
```

Bei „Author identity unknown“ zuerst eigenen Namen und eigene GitHub-E-Mail mit
`git config --local user.name` bzw. `git config --local user.email` setzen; danach
Commit wiederholen. Ein Push vor dem Commit überträgt keine Dateiänderungen.

## 3. Prüfen, mergen, deployen

Auf GitHub PR öffnen, Änderungen ansehen und grüne CI abwarten. Nicht trotz roter
Tests mergen. Danach „Merge pull request“. In Orbit Repository-Branch main neu
bauen/deployen. Kein Löschen von Instanzen, Datenbank oder Konfiguration nötig.
Vorher die persistente Datenbank sichern. Datenbankmigrationen sind additiv.
Das Paket enthält keine produktive Datenbank oder Schlüssel.

Termux muss die Python-Abhängigkeiten nicht bauen; die vollständigen Tests laufen
in GitHub Actions. Damit werden frühere Android-Buildprobleme vermieden.

## 4. Gemini ohne Environment einrichten

Admin → Gemini: vollständigen API-Schlüssel aus Google AI Studio einfügen,
aktivieren, Modell wählen, speichern, Verbindung testen. Neue längere Schlüssel
mit Punkten werden akzeptiert; maximal 4096 Zeichen. Ein Paar versehentlich
mitkopierter Anführungszeichen wird entfernt. Leerzeichen im Schlüssel und
Steuerzeichen bleiben unzulässig. Schlüssel nie in GitHub oder Chat posten.

Die bisherige Formatprüfung lehnte gültige Formate ab. Eine erfolgreiche
Speicherung beweist noch keine API-Berechtigung: Projekt, Modellzugriff und
Kontingent werden erst beim Verbindungstest geprüft. Keine pauschale Zusage,
dass jeder Google-Schlüssel oder jedes Modell kostenlos ist; Free-Tier-Projekt
und dessen Modellkontingent in AI Studio verwenden. Standardmodell bleibt
konfigurierbar. Kein Live-Test mit deinem privaten Schlüssel wurde durchgeführt.

Speicherung erfolgt verschlüsselt in der bestehenden Datenbank, abgeleitet vom
vorhandenen ADMIN_TOKEN. ADMIN_TOKEN stabil halten. Nach Tokenwechsel Schlüssel
neu speichern. Bei zwei unabhängigen Flux-Instanzen mit separaten Datenbanken
muss die Einstellung auf beiden vorhanden sein; dieses Release synchronisiert
weder Datenbanken noch Schlüssel zwischen Instanzen. Persistente DB beibehalten.

## 5. Neuer Deal-/Social-Ablauf

1. Händlerlink oder vorhandenen Toppreise-HTML-Upload verwenden.
2. Preis, Produktfakten und Produktbild samt Nutzungsgrundlage prüfen.
3. Social-Studio: Einstieg, Zielgruppe, Nutzen und Einschränkung ergänzen.
   Felder sind optional, aber konkrete Fakten verbessern den Entwurf.
4. Ziel auswählen: Folgen, Website, Diskussion oder Speichern; Otto-Pose wählen.
5. Mit Gemini vorbereiten oder ohne API mit lokalen Vorlagen arbeiten.
6. Texte und Bilder prüfen, freigeben, Deal veröffentlichen bzw. einplanen.
7. Social-ZIP laden: Captions, Sprechskript, Feed-/Story-Bild und drei Hochformat-
   Karten. In TikTok als Foto-Beitrag oder in einem Videoeditor verwenden.
   Es wird keine fertige MP4 und kein automatischer Plattform-Upload erzeugt.

Eine klare Frage startet den Beitrag; Nutzen und Einschränkung schaffen
Einordnung; ein primäres Ziel steuert den CTA. Der Kurzlink nettodeals.ch/d/ID
funktioniert erst bei veröffentlichten oder vergangenen Deals, nicht bei
Entwürfen. Plattformen machen Bildflächen oder Captions nicht automatisch
klickbar. Profil-Link nur bewerben, wenn er tatsächlich eingerichtet ist.

Bestehende Social-Pakete nach Update neu erzeugen, da zusätzliche Felder in ihre
Gültigkeitsprüfung einfliessen. Bestehende Deal-Veröffentlichungen bleiben
bestehen. Preise/Rabatte werden nicht von der KI erfunden. Ohne belegten
Vergleichspreis keine Ersparnisbehauptung. Otto-Assets: OTTO-BRAND-GUIDE.md.

## Validierung und Grenzen

136 Python-Tests und 7 Analytics-Tests; Ruff, Bandit und Abhängigkeitsprüfung.
Gemini-Antworten werden in Tests simuliert; kein Live-Zugriff mit deinem Konto.
Lokale Grafikerzeugung ohne laufende Bild-KI-Kosten. Engagement ist ein Testziel,
keine Garantie: Profilaufrufe, Follows und Website-Klicks pro Beitrag vergleichen.
