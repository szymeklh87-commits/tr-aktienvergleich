#!/usr/bin/env bash
# Startet den Android-Emulator für den Workflow „Android-Emulator prüfen“ (ab 1.17). Fehler erscheinen als Hinweis
# mit Zeile und Befehl in der Laufübersicht (die Protokolle selbst sind dort nicht immer abrufbar).
set -euo pipefail
trap 'echo "::error title=Emulator-Start::Zeile ${LINENO}: ${BASH_COMMAND}"' ERR

SDK="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-/usr/local/lib/android/sdk}}"
IMAGE="${AVD_IMAGE:-system-images;android-35;google_apis;x86_64}"
export ANDROID_AVD_HOME="${ANDROID_AVD_HOME:-$HOME/.android/avd}"
mkdir -p "$ANDROID_AVD_HOME"
SDKMANAGER="$SDK/cmdline-tools/latest/bin/sdkmanager"
AVDMANAGER="$SDK/cmdline-tools/latest/bin/avdmanager"
if [ ! -x "$SDKMANAGER" ]; then
  SDKMANAGER="$(ls -d "$SDK"/cmdline-tools/*/bin/sdkmanager | head -n 1)"
  AVDMANAGER="$(dirname "$SDKMANAGER")/avdmanager"
fi
echo "::notice title=Emulator-Start::SDK ${SDK}, Abbild ${IMAGE}, AVD-Ordner ${ANDROID_AVD_HOME}, KVM $( [ -w /dev/kvm ] && echo ja || echo nein )"

yes | "$SDKMANAGER" --licenses > /dev/null || true
"$SDKMANAGER" --install "$IMAGE" "emulator" "platform-tools" > "$RUNNER_TEMP/sdkmanager.log" 2>&1 || { tail -n 5 "$RUNNER_TEMP/sdkmanager.log" | sed 's/^/::error title=sdkmanager::/'; exit 1; }
echo "no" | "$AVDMANAGER" create avd -n s25 -k "$IMAGE" --force > "$RUNNER_TEMP/avdmanager.log" 2>&1 || { tail -n 5 "$RUNNER_TEMP/avdmanager.log" | sed 's/^/::error title=avdmanager::/'; exit 1; }
CONFIG="$ANDROID_AVD_HOME/s25.avd/config.ini"
[ -f "$CONFIG" ] || { echo "::error title=Emulator-Start::config.ini nicht gefunden: $(ls -R "$ANDROID_AVD_HOME" | head -n 20 | tr '\n' ' ')"; exit 1; }
printf 'hw.keyboard=no\nhw.lcd.width=1080\nhw.lcd.height=2340\nhw.lcd.density=450\nhw.ramSize=3072\n' >> "$CONFIG"

nohup "$SDK/emulator/emulator" -avd s25 -no-window -no-audio -no-boot-anim -no-snapshot -gpu swiftshader_indirect -camera-back none -camera-front none > "$RUNNER_TEMP/emulator.log" 2>&1 &
ADB="$SDK/platform-tools/adb"
"$ADB" wait-for-device
booted=""
for _ in $(seq 1 150); do
  if [ "$("$ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; then booted="ja"; break; fi
  sleep 4
done
if [ -z "$booted" ]; then
  tail -n 8 "$RUNNER_TEMP/emulator.log" | sed 's/^/::error title=Emulator-Protokoll::/'
  exit 1
fi
echo "$SDK/platform-tools" >> "$GITHUB_PATH"
echo "::notice title=Emulator-Start::gestartet (Android $("$ADB" shell getprop ro.build.version.release | tr -d '\r'), Chrome installiert: $("$ADB" shell pm list packages com.android.chrome | grep -c chrome || true))"
