#!/usr/bin/env bash
set -euo pipefail
TUTOR_URL="${TUTOR_URL:-http://127.0.0.1:5000}"
for _ in $(seq 1 30); do
  if [[ -n "${DISPLAY:-}" ]] && xset q >/dev/null 2>&1; then break; fi
  sleep 1
done
if command -v xset >/dev/null; then
  xset s off 2>/dev/null || true
  xset s noblank 2>/dev/null || true
  xset -dpms 2>/dev/null || true
fi
for _ in $(seq 1 60); do
  if curl --silent --fail --max-time 2 "$TUTOR_URL/api/health" >/dev/null; then break; fi
  sleep 1
done
for browser_bin in chromium chromium-browser google-chrome; do
  if command -v "$browser_bin" >/dev/null; then
    exec "$browser_bin" --start-fullscreen --no-first-run --noerrdialogs \
      --user-data-dir="$HOME/.config/ai-tutor-browser" "$TUTOR_URL"
  fi
done
echo 'No supported Chromium browser found' >&2
exit 1
