#!/usr/bin/env bash
# Docker's SIGTERM arrives here, not at Wine/Xvfb. Keep the virtual display
# alive while the game's own 'shutdown' command saves and exits.
set -Eeuo pipefail

stopping=0
server_pid=''
autosave_pid=''
stop_autosave() {
  if [[ -n "$autosave_pid" ]]; then
    kill -TERM "$autosave_pid" 2>/dev/null || true
    wait "$autosave_pid" 2>/dev/null || true
    autosave_pid=''
  fi
}
stop_server() {
  if (( stopping )); then return; fi
  stopping=1
  # The Docker stop grace period is the hard deadline; repeated TERM signals
  # must not interrupt a save that is already in progress.
  trap '' TERM INT
  # Cancel periodic saves before sending the game's own shutdown command.
  stop_autosave
  echo '[gsb] Docker stop received; requesting game console shutdown (includes save)...'
  if /usr/local/bin/gsb-console shutdown; then
    echo '[gsb] Shutdown keys delivered; waiting for game/Wine to exit.'
  else
    echo '[gsb] WARNING: Unable to send shutdown command. Game save NOT confirmed.' >&2
    echo '[gsb] Waiting for the Docker grace period; inspect docker exec gsb gsbctl windows and docker logs gsb.' >&2
  fi
}
trap stop_server TERM INT

/usr/local/bin/gsb-entrypoint &
server_pid=$!

# A separate in-container scheduler uses the same gsb-console input lock as
# the manual commands. It stops on Docker TERM or when the game process exits.
case "${GSB_AUTOSAVE_ENABLED:-1}" in
  1|true|TRUE|yes|YES)
    /usr/local/bin/gsb-autosave &
    autosave_pid=$!
    ;;
  0|false|FALSE|no|NO)
    echo '[gsb-autosave] Disabled by GSB_AUTOSAVE_ENABLED.'
    ;;
  *)
    echo '[gsb-autosave] WARNING: Invalid GSB_AUTOSAVE_ENABLED; using enabled default.' >&2
    /usr/local/bin/gsb-autosave &
    autosave_pid=$!
    ;;
esac

# Bash wait is interrupted by a trapped signal. Re-enter wait rather than
# exiting the container and cutting off the still-running game/Xvfb.
while :; do
  if wait "$server_pid"; then
    rc=0
  else
    rc=$?
  fi
  if kill -0 "$server_pid" 2>/dev/null; then
    continue
  fi
  # The TERM trap can interrupt wait with 128+signal just as the game exits.
  # Reap the child again to report its real exit status where possible.
  if (( stopping && rc >= 128 )); then
    if wait "$server_pid"; then rc=0; else rc=$?; fi
  fi
  break
done

# Prevent an orphaned timer if the game exits unexpectedly.
stop_autosave

if (( stopping )); then
  echo "[gsb] Game process stopped (exit code $rc)."
else
  echo "[gsb] Game process exited (exit code $rc)."
fi
exit "$rc"
