#!/usr/bin/env bash
# Read Wine's text console directly; game state and console input remain untouched.
# This is installed in the prebuilt image, so no 'docker compose cp' is required.
set -Eeuo pipefail
xvfb_pid="$(pgrep -x Xvfb | head -1 || true)"
[[ -n "$xvfb_pid" ]] || { echo '[gsb-reader] Xvfb is not running.' >&2; exit 1; }
mapfile -d '' -t args < "/proc/$xvfb_pid/cmdline"
export DISPLAY=''
export XAUTHORITY=''
for (( i=0; i<${#args[@]}; i++ )); do
  case "${args[i]}" in
    :[0-9]*) [[ -n "$DISPLAY" ]] || DISPLAY="${args[i]}" ;;
    -auth) XAUTHORITY="${args[i+1]:-}" ;;
  esac
done
[[ -n "$DISPLAY" && -r "$XAUTHORITY" ]] || { echo '[gsb-reader] Xvfb display or auth not available.' >&2; exit 1; }
textfile="$(mktemp /tmp/gsb-console-out.XXXXXXXX.txt)"
trap 'rm -f -- "$textfile"' EXIT
winpath="Z:\\tmp\\$(basename "$textfile")"
if ! WINEDEBUG=-all timeout -k 2s 25s wine /usr/local/lib/gsb/gsb-console-reader.exe "$winpath"; then
  echo '[gsb-reader] Wine console read failed.' >&2
  exit 1
fi
[[ -s "$textfile" ]] || { echo '[gsb-reader] Console returned no text.' >&2; exit 1; }
if grep -q '^ERROR:' "$textfile"; then cat "$textfile" >&2; exit 1; fi
cat "$textfile"
