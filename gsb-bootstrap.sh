#!/usr/bin/env bash
# PID 1 bootstrap: map arbitrary host UID/GID, then run Wine as non-root gsb.
set -Eeuo pipefail
fail() { echo "[gsb] ERROR: $*" >&2; exit 2; }
uid="${GSB_UID:-1000}"
gid="${GSB_GID:-1000}"
for n in "$uid" "$gid"; do
  [[ "$n" =~ ^[0-9]{1,5}$ ]] || fail 'GSB_UID/GSB_GID must be integer IDs 100–60000.'
  (( 10#$n >= 100 && 10#$n <= 60000 )) || fail 'GSB_UID/GSB_GID must be 100–60000.'
done
[[ "$(id -u)" == 0 ]] || fail 'Start container with the default user (root bootstrap drops privileges).'

if [[ "$(id -u gsb)" != "$uid" ]]; then
  other="$(getent passwd "$uid" | cut -d: -f1 || true)"
  [[ -z "$other" || "$other" == gsb ]] || fail "UID $uid is owned by $other inside image."
  usermod -u "$uid" gsb
fi
if [[ "$(id -g gsb)" != "$gid" ]]; then
  if ! getent group "$gid" >/dev/null; then
    groupmod -g "$gid" gsb
  fi
  usermod -g "$gid" gsb
fi
chown "$uid:$gid" /home/gsb
[[ -d /server && -f /server/MZServer.exe ]] || fail 'Bind mount your existing Windows server files at /server (MZServer.exe missing).'
[[ -d "$WINEPREFIX" ]] || fail 'A writable Wine prefix volume is required at /home/gsb/.wine-gsb.'

# Docker may initialize an empty named volume with either root's ownership or
# the image build user's UID 1001, while the real host user may be UID 1000.
# Fix ONLY the root directory of an EMPTY prefix; never recursively chown
# a populated prefix or the user's Windows server files.
if [[ -z "$(find "$WINEPREFIX" -mindepth 1 -maxdepth 1 -print -quit)" ]] &&    [[ "$(stat -c %u:%g "$WINEPREFIX")" != "$uid:$gid" ]]; then
  chown "$uid:$gid" "$WINEPREFIX"
  echo '[gsb] Initialized ownership of empty Docker Wine volume.'
fi

gosu gsb test -w /server || fail "Game files /server are not writable by UID:GID $uid:$gid. Check your bind mount permissions."
gosu gsb test -w "$WINEPREFIX" || fail "Wine prefix volume is not writable by UID:GID $uid:$gid. Keep the same IDs or adjust ownership before retrying."
echo "[gsb] Launching Wine as non-root UID:GID $uid:$gid"
exec gosu gsb /usr/local/bin/gsb-supervisor "$@"
