# NettoDeals 3.1.2 professionell auf GitHub übernehmen

Diese Anleitung lässt den produktiven `main`-Branch unverändert, bis Version
3.1.2 geprüft und ausdrücklich zusammengeführt wurde.

## 1. Voraussetzungen

- Git ist lokal installiert.
- Das Repository `nettodeals/nettodeals` kann geschrieben werden.
- Das Archiv `nettodeals-v3.1.2.zip` wurde in einen separaten Ordner entpackt.
- Die produktive SQLite-Datei und alle Orbit-Umgebungsvariablen wurden gesichert.

Geheimnisse wie `ADMIN_TOKEN`, Awin- oder TradeDoubler-Tokens dürfen niemals in
Git eingecheckt werden. Die echte `.env` und Datenbankdateien werden durch
`.gitignore` ausgeschlossen.

## 2. Repository aktualisieren

```bash
git clone https://github.com/nettodeals/nettodeals.git
cd nettodeals
git switch main
git pull --ff-only origin main
git tag backup-before-v3.1.2
git push origin backup-before-v3.1.2
git switch -c release/3.1.2
```

Kopiere nun den Inhalt des entpackten 3.1.2-Ordners in diesen Arbeitsordner.
Die lokale `.git`-Struktur, eine vorhandene `.env` und Datenbankdateien dürfen
nicht ersetzt oder gelöscht werden.

Auf Linux oder macOS kann aus dem entpackten Versionsordner heraus verwendet
werden:

```bash
rsync -av \
  --exclude='.git/' \
  --exclude='.env' \
  --exclude='*.db' \
  --exclude='*.sqlite*' \
  ./ /pfad/zum/geklonten/nettodeals/
```

Kein `--delete` verwenden. So bleiben unbekannte Dateien zunächst sichtbar und
können bewusst geprüft werden.

## 3. Betreiberangaben ausfüllen

Öffne `nettodeals/templates/info.html` und ersetze im Impressum:

- `[Vorname Nachname oder Firma]`
- `[Strasse und Hausnummer]`
- `[PLZ und Ort]`
- `[geschäftliche Kontaktadresse]`

Prüfe anschließend Datenschutz- und Redaktionstext gegen die tatsächlich
verwendeten Hosting-, Analyse- und Affiliate-Dienste.

## 4. Änderungen prüfen und testen

```bash
git status --short
git diff --check
git diff
python -m venv .venv
source .venv/bin/activate
python -m pip install --requirement requirements.txt --requirement requirements-dev.txt
ruff check .
python -m pytest
bandit -q -r nettodeals main.py
```

Danach lokal starten:

```bash
cp .env.example .env
# ADMIN_TOKEN in .env ersetzen
set -a
source .env
set +a
DB_PATH=./nettodeals.db COOKIE_SECURE=false python -m uvicorn main:app --reload
```

Mindestens diese URLs kontrollieren:

- `/`
- `/admin/login`
- `/robots.txt`
- `/sitemap.xml`
- `/ueber-nettodeals`
- `/redaktion`
- `/datenschutz`
- `/impressum`
- eine veröffentlichte `/deal/{id}/{slug}`-Seite

Zusätzlich zwei echte Toppreise-HTML- oder MHTML-Dateien importieren und kontrollieren, ob
Titel, „Ab“-Preis, Quelle und Prüfzeitpunkt stimmen.

## 5. Commit und Pull Request

```bash
git add --all
git status --short
git commit -m "release: prepare NettoDeals 3.1.2"
git push --set-upstream origin release/3.1.2
```

Auf GitHub anschließend einen Pull Request von `release/3.1.2` nach `main`
erstellen. Im Pull Request dokumentieren:

- Datenbankmigrationen;
- neue öffentliche Routen;
- Toppreise-Importgrenzen;
- Testergebnis;
- erforderliche Variable `SITE_URL=https://nettodeals.ch`;
- ausgefüllte Betreiberangaben;
- geprüfte Persistenz der Flux-Instanzen.

Erst zusammenführen, wenn alle GitHub-Actions-Checks erfolgreich sind. Für dieses
Release ist „Squash and merge“ geeignet.

## 6. Release markieren und ausrollen

```bash
git switch main
git pull --ff-only origin main
git tag -a v3.1.2 -m "NettoDeals 3.1.2"
git push origin v3.1.2
```

In Orbit anschließend `SITE_URL=https://nettodeals.ch` ergänzen und zuerst einen
normalen Pull-&-Build beziehungsweise Redeploy durchführen. Einen Hard Redeploy
nur verwenden, wenn der normale Build den neuen Commit nicht übernimmt.

Nach dem Deploy prüfen:

```text
https://nettodeals.ch/health
https://nettodeals.ch/robots.txt
https://nettodeals.ch/sitemap.xml
```

Danach einen Admin-Login, einen Import, eine Veröffentlichung und einen Neustart
testen. Die Veröffentlichung darf nach dem Neustart nicht verschwunden sein.

## 7. Rückkehr zu Version 3.0

Wenn ein kritischer Fehler auftritt, in Orbit wieder den vor dem Merge verwendeten
Commit oder das Tag `backup-before-v3.1.2` ausrollen. Die zuvor gesicherte
SQLite-Datei nur dann zurückspielen, wenn die automatische Migration oder neue
Daten selbst die Fehlerquelle sind.
