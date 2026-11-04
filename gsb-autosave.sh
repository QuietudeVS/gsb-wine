#!/usr/bin/env bash
# Run inside the container. Automatically request in-game saves on a timer.
# The server's console command lock is shared with manual saves and shutdown.
set -Eeuo pipefail

interval="${GSB_AUTOSAVE_INTERVAL_SECONDS:-1800}"
case "$interval" in
  *[!0-9]*|'') echo "[gsb-autosave] ERROR: GSB_AUTOSAVE_INTERVAL_SECONDS must be a positive integer." >&2; exit 2 ;;
esac
# Avoid accidentally hammering the console due to a typo.
if (( 10#$interval < 60 )); then
  echo '[gsb-autosave] ERROR: Minimum save interval is 60 seconds.' >&2
  exit 2
fi
interval=$((10#$interval))

sleeper_pid=''
stopping=0
stop() {
  stopping=1
  trap - TERM INT
  if [[ -n "$sleeper_pid" ]]; then
    kill "$sleeper_pid" 2>/dev/null || true
    wait "$sleeper_pid" 2>/dev/null || true
    sleeper_pid=''
  fi
  exit 0
}
trap stop TERM INT

# Keep the wait interruptible; don't send anything until the correct Wine
# console is uniquely discoverable. Xvfb and Wine may take time to initialize.
echo "[gsb-autosave] Enabled: every ${interval}s (in-game save; no backup archive)."
while ! /usr/local/bin/gsb-console probe >/dev/null 2>&1; do
  sleep 5 & sleeper_pid=$!
  wait "$sleeper_pid" || true
  sleeper_pid=''
done
echo '[gsb-autosave] MZ Server Console detected; starting save timer.'

while :; do
  sleep "$interval" & sleeper_pid=$!
  wait "$sleeper_pid" || true
  sleeper_pid=''
  (( stopping == 0 )) || exit 0

  # Another console operation (including shutdown) holds the same lock.
  # This logs delivery only: an actual save confirmation is game-generated.
  if /usr/local/bin/gsb-console save; then
    echo '[gsb-autosave] Scheduled save command delivered.'
  else
    echo '[gsb-autosave] WARNING: Could not deliver scheduled save; will retry next interval.' >&2
  fi
done
