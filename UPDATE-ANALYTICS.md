# NettoDeals: Google Analytics mit Einwilligung

Grundlage: main, Commit 836dfc00a1d30b8a0582776633f7ba486e89c44f (Version 3.5.0).
Mess-ID: G-GQGD9NXG70. Keine zusätzlichen Python-Pakete oder Orbit-ENV nötig.

## Verhalten

- Alle öffentlichen HTML-Seiten enthalten die gemeinsame Einwilligungsoberfläche.
- Google Analytics lädt erst nach „Analyse erlauben“. Ablehnen ist gleichwertig erreichbar.
- Die Auswahl gilt 180 Tage in diesem Browser und auf diesem Hostnamen.
- „Datenschutz-Einstellungen“ am Seitenende öffnet die Auswahl erneut.
- Beim Widerruf wird Analytics sofort deaktiviert, die zugehörigen Cookies werden entfernt und eine bereits messende Seite neu geladen. Die Auswahländerung wirkt auch in anderen geöffneten Tabs desselben Ursprungs.
- Adminseiten enthalten weder Analytics-Script noch Google-Scriptfreigabe. Eigene Besuche auf öffentlichen Seiten werden bei erteilter Zustimmung jedoch mitgemessen.
- Google Signals, Werbespeicherung und Werbepersonalisierung werden im Tag ausgeschaltet. Seitenadresse und Referrer werden ohne Suchparameter/Fragment übergeben.
- Die Datenschutzerklärung beschreibt die Integration. Die bestehende Betreiberangabe wurde nicht geändert. Kontoeinstellungen und tatsächlich aktivierte Google-Funktionen müssen dazu passen.
- Bei blockiertem JavaScript oder nicht erteilter Zustimmung findet keine Analytics-Messung statt. Das gilt nicht für bereits vorhandene externe Produktbilder und YouTube-Vorschaubilder.

## Vor dem Produktivstart in Google Analytics

1. Verwaltung → Datenerhebung und -änderung → Datenstreams → Webstream für nettodeals.ch öffnen (Bezeichnungen können je nach Oberfläche abweichen).
2. „Optimierte Analysen“ / Enhanced measurement für diesen Stream ausschalten. Normale Seitenaufrufe werden weiterhin durch den hier eingebauten Google-Tag erfasst. So vermeiden wir zusätzliche automatische Such-, Formular-, Link- und URL-Ereignisse ausserhalb dieser kontrollierten Einbindung.
3. Google Signals und Werbepersonalisierung in den Property-Einstellungen nicht aktivieren; keine weiteren Tag-Ziele anschliessen.
4. Aufbewahrung der Nutzer-/Ereignisdaten bewusst konfigurieren, beispielsweise 2 Monate. Die Cookie-Laufzeit im Code ist davon unabhängig.
5. Nicht parallel einen zweiten Google-Tag oder einen Tag Manager mit derselben Mess-ID einbauen: sonst drohen doppelte Aufrufe.
6. www.nettodeals.ch und nettodeals.ch möglichst auf einen einzigen kanonischen Host umleiten. Die lokal gespeicherte Einwilligung ist je Host getrennt.

## Termux: Update ohne Repository-Austausch

Das Download-Paket enthält einen geprüften Git-Patch, geänderte Dateien unter files/ und diese Anleitung. Verwende den Patch; er erkennt abweichende Dateien statt sie unbemerkt zu überschreiben.

Zuerst ZIP als nettodeals-analytics-update.zip im Download-Ordner speichern. Befehle blockweise kopieren, ohne die Terminal-Prompt-Zeichen.

```sh
termux-setup-storage
pkg install unzip
unzip ~/storage/downloads/nettodeals-analytics-update.zip -d ~/nettodeals-analytics-update
cd ~/netto-update-v311/repo
git config --local core.pager cat
git status -sb
```

Falls hier geänderte oder unbekannte Dateien erscheinen: nicht löschen, nicht mit git add --all aufnehmen. Erst sichern/klären. Bei sauberem Stand:

```sh
git fetch origin --prune
git switch main
git pull --ff-only origin main
git switch -c fix/ga4-consent
```

Jetzt zunächst prüfen:

```sh
git apply --check ~/nettodeals-analytics-update/nettodeals-analytics.patch
```

Keine Ausgabe bedeutet: anwendbar. Bei einem Fehler stoppen und die Meldung weitergeben. Nicht mit Gewalt anwenden.

```sh
git apply --index ~/nettodeals-analytics-update/nettodeals-analytics.patch
git diff --cached --stat
git commit -m "Add consent-based GA4 analytics"
git push -u origin fix/ga4-consent
```

```sh
gh pr create --repo nettodeals/nettodeals --base main --head fix/ga4-consent --title "Google Analytics mit Einwilligung" --body "GA4 auf öffentlichen Seiten, Aurora-Einwilligungsbanner, Widerruf, Admin-Ausschluss und angepasste Sicherheitsrichtlinie."
```

Auf GitHub die CI-Prüfungen abwarten. Nur bei erfolgreichen Prüfungen zusammenführen. Anschliessend in Orbit den aktuellen main-Stand neu bauen und deployen. Ein Löschen der App, der Instanzen oder der Datenbank ist dafür nicht nötig. Tests mit Rust-Abhängigkeiten nicht in Termux installieren; die Projektprüfungen laufen in GitHub Actions.

## Nach dem Deploy prüfen

1. Website im privaten Browserfenster öffnen: Banner sichtbar, noch keine Analytics-Zustimmung.
2. „Ohne Analyse weiter“ wählen: Website bleibt nutzbar.
3. Über „Datenschutz-Einstellungen“ die Analyse erlauben.
4. In GA4 unter Berichte → Echtzeit den Testbesuch prüfen; Werbeblocker können ihn verhindern.
5. Eine weitere öffentliche Seite öffnen. Es darf kein zweiter Banner erscheinen.
6. Einstellungen erneut öffnen und ablehnen: Cookies werden entfernt; die Seite wird neu geladen.
7. Adminseite öffnen: kein Banner und kein Analytics-Tag.

Es werden keine vergangenen Besuche nachträglich rekonstruiert. Nicht zustimmende oder blockierte Besucher fehlen in diesen Daten. Werte bei Rakuten daher als gemessene Analytics-Reichweite verstehen.

## Rücknahme

Den zugehörigen Commit/PR über Git revert zurücknehmen und erneut deployen. Der Patch verändert weder die Datenbank noch Umgebungsvariablen.

## Validierung dieses Pakets

106 Python-Tests und 7 JavaScript-Tests bestanden; Ruff und Bandit ohne Befund. Die JavaScript-Tests prüfen die Einwilligungslogik mit einer simulierten Browserumgebung. Ein echter Browser-/Netzwerktest war in der Ausführungsumgebung nicht möglich (Browserdownload fehlgeschlagen). Die Übermittlung an deine GA4-Property wurde nicht live getestet. Nach dem Deploy den oben beschriebenen Echtzeittest durchführen.
