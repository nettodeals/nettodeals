# NettoDeals 3.1.2 auf Android aktualisieren

Dieses kleine Update setzt eine vollständig installierte Version 3.1.1 voraus.
Es ergänzt den direkten Import von MHT-/MHTML-Webarchiven aus Chrome für Android.

## Update in Termux

Das Archiv `nettodeals-update-3.1.2.zip` in den Android-Ordner `Download` laden.
Danach in Termux:

```bash
cd ~/netto-update-v311/repo
git switch main
git pull --ff-only
git switch -c release/3.1.2
unzip -o ~/storage/downloads/nettodeals-update-3.1.2.zip -d .
sed -n '1p' CHANGELOG.md
python -m compileall main.py nettodeals
git status
git add --all
git commit -m "Add Android MHTML import in version 3.1.2"
git push -u origin release/3.1.2
```

Die erste Zeile des Changelogs muss `# NettoDeals 3.1.2 – Überarbeitung`
lauten. Die vollständigen Tests laufen anschließend über GitHub Actions.

Den Pull Request kann Termux so erstellen:

```bash
gh pr create --base main --head release/3.1.2 \
  --title "Release NettoDeals 3.1.2" \
  --body "Unterstützt HTML sowie MHT/MHTML aus Chrome für Android beim Toppreise-Import."
```

Nach erfolgreichen Prüfungen den Pull Request in GitHub zusammenführen und in
Orbit zuerst einen normalen Pull & Build beziehungsweise Redeploy auslösen.

## Funktionstest

1. In Chrome für Android die Top-100-Seite als `.mht` speichern.
2. Bei „Neue Toppreise“ zuerst 48 Stunden auswählen und auch diese Seite speichern.
3. Beide Dateien im Adminbereich hochladen und die 48-Stunden-Bestätigung setzen.
4. Kontrollieren, ob die Produkte als prüfpflichtige Entwürfe erscheinen.

Webarchive dürfen höchstens 20 MB gross sein. Aus jedem Archiv wird nur der erste
HTML-Teil bis höchstens 5 MB ausgewertet; Bilder und andere Ressourcen werden
nicht übernommen.
