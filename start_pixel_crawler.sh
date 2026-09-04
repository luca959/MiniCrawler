#!/bin/zsh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv-frida"
CACHE_DIR="$PROJECT_DIR/.cache/frida"
FRIDA_VERSION="17.17.0"
FRIDA_ARCHIVE="$CACHE_DIR/frida-server-${FRIDA_VERSION}-android-arm64.xz"
FRIDA_BINARY="$CACHE_DIR/frida-server-${FRIDA_VERSION}-android-arm64"
FRIDA_URL="https://github.com/frida/frida/releases/download/${FRIDA_VERSION}/frida-server-${FRIDA_VERSION}-android-arm64.xz"
FRIDA_SHA256="09d1fad867b27d69562a79289f4c412e85867f5d38ab72877036ed35e4223021"
REMOTE_BINARY="/data/local/tmp/mc-instrument"
INSTRUMENTATION_STARTED=0

cleanup() {
  set +e
  if [[ "$INSTRUMENTATION_STARTED" == "1" ]]; then
    adb shell su -c 'killall mc-instrument 2>/dev/null || true' >/dev/null 2>&1
    adb shell su -c 'rm -f /data/local/tmp/mc-instrument' >/dev/null 2>&1
    adb forward --remove tcp:27042 >/dev/null 2>&1
    adb forward --remove tcp:27043 >/dev/null 2>&1
    adb shell svc power stayon false >/dev/null 2>&1
    echo "Crawler arrestato. Checkpoint e CSV sono stati conservati."
  fi
}

trap cleanup EXIT

cd "$PROJECT_DIR"

if ! command -v adb >/dev/null 2>&1; then
  echo "Errore: adb non è installato o non è disponibile nel PATH."
  exit 1
fi

if [[ "$(adb get-state 2>/dev/null || true)" != "device" ]]; then
  echo "Errore: Pixel non collegato o debug USB non autorizzato."
  echo "Sblocca il telefono, accetta il debug USB e riprova."
  exit 1
fi

if ! adb shell su -c id 2>/dev/null | grep -q "uid=0"; then
  echo "Errore: accesso root non disponibile sul Pixel."
  exit 1
fi

if [[ "$(adb shell getprop ro.product.cpu.abi | tr -d '\r')" != "arm64-v8a" ]]; then
  echo "Errore: questo script è configurato per il Pixel arm64-v8a."
  exit 1
fi

if [[ ! -x "$VENV_DIR/bin/frida" ]]; then
  echo "Creo l'ambiente Python per Frida..."
  python3 -m venv "$VENV_DIR"
  "$VENV_DIR/bin/pip" install "frida==$FRIDA_VERSION" "frida-tools==14.10.4"
fi

mkdir -p "$CACHE_DIR"
if [[ ! -f "$FRIDA_ARCHIVE" ]]; then
  echo "Scarico Frida Server $FRIDA_VERSION..."
  curl -fL "$FRIDA_URL" -o "$FRIDA_ARCHIVE"
fi

ACTUAL_SHA256="$(shasum -a 256 "$FRIDA_ARCHIVE" | awk '{print $1}')"
if [[ "$ACTUAL_SHA256" != "$FRIDA_SHA256" ]]; then
  echo "Errore: checksum di Frida Server non valido."
  exit 1
fi

if [[ ! -x "$FRIDA_BINARY" ]]; then
  echo "Decomprimo Frida Server..."
  "$VENV_DIR/bin/python" -c 'import lzma, pathlib, sys; pathlib.Path(sys.argv[2]).write_bytes(lzma.decompress(pathlib.Path(sys.argv[1]).read_bytes()))' "$FRIDA_ARCHIVE" "$FRIDA_BINARY"
  chmod 755 "$FRIDA_BINARY"
fi

CURRENT_ACTIVITIES="$(adb shell dumpsys activity activities 2>/dev/null || true)"
if [[ "$CURRENT_ACTIVITIES" != *"MMFTSSOSHomeWebViewUI"* ]]; then
  echo "Apri ora WeChat e vai alla pagina della ricerca globale."
  read -r "?Quando la ricerca è visibile sul Pixel, premi Invio... "
fi

CURRENT_ACTIVITIES="$(adb shell dumpsys activity activities 2>/dev/null || true)"
if [[ "$CURRENT_ACTIVITIES" != *"MMFTSSOSHomeWebViewUI"* ]]; then
  echo "Errore: la pagina di ricerca WeChat non è stata rilevata."
  exit 1
fi

echo "Avvio l'instrumentazione temporanea sul Pixel..."
INSTRUMENTATION_STARTED=1
adb push "$FRIDA_BINARY" "$REMOTE_BINARY" >/dev/null
adb shell su -c 'killall mc-instrument 2>/dev/null || true' >/dev/null 2>&1
adb shell su -c 'chmod 755 /data/local/tmp/mc-instrument' >/dev/null
adb shell su -c 'nohup /data/local/tmp/mc-instrument >/dev/null 2>&1 </dev/null &' >/dev/null
adb forward tcp:27042 tcp:27042 >/dev/null
adb forward tcp:27043 tcp:27043 >/dev/null
adb shell svc power stayon true >/dev/null
adb shell input keyevent KEYCODE_WAKEUP >/dev/null
adb shell wm dismiss-keyguard >/dev/null

READY=0
for _ in {1..15}; do
  if "$VENV_DIR/bin/frida-ps" -H 127.0.0.1:27042 >/dev/null 2>&1; then
    READY=1
    break
  fi
  sleep 1
done

if [[ "$READY" != "1" ]]; then
  echo "Errore: Frida Server non ha risposto."
  exit 1
fi

echo "Pixel pronto. Riprendo MiniCrawler dal checkpoint esistente."
echo "Per fermare correttamente usa Ctrl+C una sola volta."

python3 MetadataCrawler/pixel_batch_crawler.py \
  --target 200000 \
  --batch-size 8 \
  --batch-pause 5 \
  --delay-ms 2000 \
  --max-pages 5 \
  "$@"
