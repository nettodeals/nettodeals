# NettoDeals 3.2.0 auf GitHub aktualisieren

Die folgenden Befehle werden in **Termux** auf dem Galaxy Fold eingegeben.

```bash
cd ~/netto-update-v311/repo
git fetch origin --prune
git switch main
git pull --ff-only origin main
```

Entpacke danach das bereitgestellte Release-Paket in einen eigenen Ordner und
kopiere dessen Inhalt über das Repository. Falls das ZIP unter `Download` liegt:

```bash
cd ~/storage/downloads
unzip -o nettodeals-3.2.0.zip -d ~/nettodeals-3.2.0
cp -a ~/nettodeals-3.2.0/. ~/netto-update-v311/repo/
cd ~/netto-update-v311/repo
```

Prüfung ohne Installation problematischer Android-Binärpakete:

```bash
python -m compileall main.py nettodeals tests
git status --short
git diff --stat
```

Danach eigener Branch, Commit und Push:

```bash
git switch -c release/3.2.0
git add --all
git commit -m "Release NettoDeals 3.2.0"
git push -u origin release/3.2.0
gh pr create --base main --head release/3.2.0 --title "Release NettoDeals 3.2.0" --body "Automatisierte Deal-Anreicherung, Direktlinks, Kurzchecks, Gutscheine und 48h-Archiv."
```

Nach dem Merge in GitHub Orbit zunächst **Pull & Build** oder **Redeploy**
ausführen. Ein Hard Redeploy ist nur nötig, wenn Orbit den neuen Commit nicht
übernimmt oder der Produktions-Symlink fehlerhaft ist.

Optional kann in Orbit `YOUTUBE_API_KEY` ergänzt werden. Ohne diesen Schlüssel
funktioniert die Anwendung vollständig, lediglich YouTube-Verweise entfallen.
`DEAL_LIFETIME_HOURS=48` ist optional, da 48 bereits der Standardwert ist.
