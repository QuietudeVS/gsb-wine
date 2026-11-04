#!/usr/bin/env bash
# Send a restricted command to the MZ server console running in Wine/Xvfb.
# Run INSIDE the container. Does not rely on a fixed X11 window ID.
set -Eeuo pipefail

usage() {
  echo 'Usage: gsb-console {status|players|save|shutdown|probe|windows}' >&2
  exit 2
}

COMMAND="${1:-}"
[[ $# -eq 1 ]] || usage
case "$COMMAND" in
  status|players|save|shutdown|probe|windows) ;;
  *) usage ;;
esac

fail() { echo "[gsb-console] ERROR: $*" >&2; exit 1; }
command -v xdotool >/dev/null || fail 'xdotool is missing: rebuild the updated image.'
command -v xwininfo >/dev/null || fail 'xwininfo is missing: rebuild the updated image.'

# Match the verified inspection commands: discover the Xvfb display and its
# authentication file from its actual argv rather than hardcoding :99 or :102.
XVFB_PID="$(pgrep -x Xvfb | head -1 || true)"
[[ -n "$XVFB_PID" ]] || fail 'Xvfb is not running.'
mapfile -d '' -t xvfb_args < "/proc/$XVFB_PID/cmdline"
export DISPLAY=''
export XAUTHORITY=''
for (( i=0; i<${#xvfb_args[@]}; i++ )); do
  case "${xvfb_args[i]}" in
    :[0-9]*) [[ -z "$DISPLAY" ]] && DISPLAY="${xvfb_args[i]}" ;;
    -auth) if (( i + 1 < ${#xvfb_args[@]} )); then XAUTHORITY="${xvfb_args[i+1]}"; fi ;;
  esac
done
[[ -n "$DISPLAY" ]] || fail 'Could not identify the Xvfb display.'
[[ -r "$XAUTHORITY" ]] || fail 'Could not read the Xvfb authentication file.'

# It is important to list window titles before guessing a selector. The X11
# IDs change when Wine or the server starts again.
if [[ "$COMMAND" == windows ]]; then
  echo "[gsb-console] Display $DISPLAY; visible X11 windows:"
  while IFS= read -r win; do
    [[ -n "$win" ]] || continue
    name="$(xdotool getwindowname "$win" 2>/dev/null || true)"
    klass="$(xprop -id "$win" WM_CLASS 2>/dev/null || true)"
    printf '  %s  title=%q  %s\n' "$win" "$name" "$klass"
  done < <(xdotool search --onlyvisible --name '.*' 2>/dev/null || true)
  exit 0
fi

# Explicit window selection is an escape hatch for unusual Wine window titles.
# Do not permanently set a window ID: it changes after a restart.
if [[ -n "${GSB_CONSOLE_WINDOW:-}" ]]; then
  WIN="$GSB_CONSOLE_WINDOW"
else
  # The game has TWO windows: the MZ game window and the command console.
  # Select by console-specific X11 title, NEVER by 'MZ' alone or by z-order.
  # Prefer an explicit console window over a possible game window titled
  # "MZ Dedicated Server". Try progressively broader names only if needed.
  if [[ -n "${GSB_CONSOLE_MATCH:-}" ]]; then
    patterns=("$GSB_CONSOLE_MATCH")
  else
    patterns=('MZ[[:space:]]*Server[[:space:]]*Console|MZServerConsole' 'MZ.*Console' '^MZ Dedicated Server$')
  fi
  windows=()
  match=''
  for candidate in "${patterns[@]}"; do
    mapfile -t windows < <(xdotool search --onlyvisible --name "$candidate" 2>/dev/null | sort -u || true)
    match="$candidate"
    (( ${#windows[@]} > 0 )) && break
  done
  (( ${#windows[@]} > 0 )) || fail "No console window matched supported titles. Run docker exec gsb gsbctl windows and optionally pass GSB_CONSOLE_MATCH via docker run -e."
  (( ${#windows[@]} == 1 )) || fail "Multiple windows matched '$match' (${windows[*]}). Run docker exec gsb gsbctl windows and narrow GSB_CONSOLE_MATCH."
  WIN="${windows[0]}"
fi

if ! xwininfo -id "$WIN" 2>/dev/null | grep -q 'Map State: IsViewable'; then
  fail "Window $WIN is not currently viewable. Run docker exec gsb gsbctl windows."
fi
TITLE="$(xdotool getwindowname "$WIN" 2>/dev/null || true)"
if [[ "$COMMAND" == probe ]]; then
  echo "[gsb-console] Ready: display=$DISPLAY window=$WIN title=$TITLE"
  exit 0
fi

# Prevent overlapping console input from two gsbctl calls (or a simultaneous
# Docker stop and manual save). The stop handler uses the same lock.
exec 9> /tmp/gsb-console-input.lock
flock -w 10 9 || fail 'Console is busy; could not obtain input lock in 10 seconds.'

xdotool windowfocus --sync "$WIN" || fail "Could not focus console window $WIN."
xdotool type --clearmodifiers --delay 75 -- "$COMMAND" || fail "Could not type $COMMAND."
xdotool key Return || fail 'Could not press Enter.'
echo "[gsb-console] Sent '$COMMAND' to window $WIN ($TITLE)."
# Console replies remain in the Wine window; success here means key delivery,
# not confirmation of the game's response.
