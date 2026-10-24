#!/usr/bin/env bash
# Chrome im Android-Emulator vorbereiten (ab 1.18 gemeinsam für „Android-Emulator prüfen“ und den Job „android“ von
# „App mit echten Daten prüfen“): Bildschirm im Format des S25+ (1080 × 2340, 450 dpi), keine Animationen, Chrome ohne
# Einrichtungsdialog und mit lesbarer Befehlszeile. Fehler erscheinen als Hinweis mit Zeile und Befehl.
set -euo pipefail
trap 'echo "::error title=Chrome-Vorbereitung::Zeile ${LINENO}: ${BASH_COMMAND}"' ERR

adb root || true
adb wait-for-device
adb shell wm size 1080x2340
adb shell wm density 450
adb shell settings put global window_animation_scale 0
adb shell settings put global transition_animation_scale 0
adb shell settings put global animator_duration_scale 0
adb shell "echo '_ --disable-fre --no-default-browser-check --no-first-run --disable-features=SigninPromo' > /data/local/tmp/chrome-command-line"
adb shell chmod 644 /data/local/tmp/chrome-command-line
adb shell am set-debug-app --persistent com.android.chrome
