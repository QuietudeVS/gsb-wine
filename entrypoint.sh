#!/usr/bin/env bash
set -Eeuo pipefail

cd /server
export HOME=/home/gsb
export WINEPREFIX="${WINEPREFIX:-/home/gsb/.wine-gsb}"
export WINEARCH=win64
export GSB_APP_ID="${GSB_APP_ID:-3891040}"

for required in MZServer.exe steamclient64.dll steamclient.dll \
  MZClient/Binaries/Win64/MZServer-Win64-Shipping.exe; do
  if [[ ! -f "/server/$required" ]]; then
    echo "[gsb] ERROR: Missing /server/$required; check GSB_SERVER_DIR." >&2
    exit 2
  fi
done

# Xvfb must not use a fixed display number. Docker may restart the same
# container after the game exits, leaving an X display lock in /tmp.
# Re-enter this script through xvfb-run -a so it selects an available display
# each time and owns the lifetime of Xvfb. The guard avoids recursion.
if [[ "${GSB_XVFB_ACTIVE:-0}" != "1" ]]; then
  export GSB_XVFB_ACTIVE=1
  echo "[gsb] Starting automatic virtual display (Xvfb)..."
  exec xvfb-run -a -e /dev/stderr \
    -s "-screen 0 1280x800x24 -nolisten tcp" \
    /usr/local/bin/gsb-entrypoint
fi

echo "[gsb] Xvfb is available on $DISPLAY"

if [[ ! -s "$WINEPREFIX/system.reg" ]]; then
  echo "[gsb] First run: initializing Wine prefix at $WINEPREFIX"
  wineboot --init
fi

# No host-side setup script is needed. Create config using the game's own
# sample only when missing; never replace an existing serverconfig.json.
if [[ ! -f /server/MZClient/Saved/Config/serverconfig.json ]]; then
  python3 /usr/local/lib/gsb/serverctl.py init --server-dir /server
fi

# The Microsoft VC++ x64 runtime was the blocker in the original Windows
# error dialog. Keep the prefix persistent, and verify the runtime in the
# registry rather than assuming an installer exit code means success.
vc_runtime_installed() {
  wine reg query 'HKLM\Software\Microsoft\VisualStudio\14.0\VC\Runtimes\x64' \
    /v Installed 2>/dev/null | grep -Eqi '0x0*1([[:space:]]|$)'
}

if ! vc_runtime_installed; then
  echo "[gsb] Installing Microsoft Visual C++ runtime into $WINEPREFIX"

  # Ubuntu/Debian often install /usr/bin/wine as a shell wrapper. Older
  # Winetricks misidentifies its architecture and can exit immediately.
  # WINE64 points at the real 64-bit Wine ELF executable (when installed).
  if [[ -x /usr/lib/wine/wine64 ]]; then
    export WINE64=/usr/lib/wine/wine64
    echo "[gsb] Winetricks workaround: WINE64=$WINE64"
  fi

  if ! winetricks -q vcrun2022; then
    echo "[gsb] Winetricks could not finish; trying the official Microsoft x64 installer."
  fi

  if ! vc_runtime_installed; then
    echo "[gsb] Downloading VC++ x64 Redistributable directly from Microsoft..."
    tmpdir="$(mktemp -d)"
    redist="$tmpdir/vc_redist.x64.exe"
    # Microsoft maintains this link for the Visual Studio 2022 channel.
    url='https://aka.ms/vs/17/release/vc_redist.x64.exe'
    if ! curl -fL --retry 3 --connect-timeout 20 --output "$redist" "$url"; then
      echo "[gsb] ERROR: Could not download the VC++ installer from Microsoft." >&2
      rm -rf -- "$tmpdir"
      exit 4
    fi
    if [[ "$(head -c 2 "$redist")" != 'MZ' ]]; then
      echo "[gsb] ERROR: Download did not look like a Windows executable." >&2
      rm -rf -- "$tmpdir"
      exit 4
    fi
    # Ignore installer exit status until the registry is checked. Under
    # Wine, the bootstrapper may return before its worker process finishes.
    echo "[gsb] Installing VC++ x64 quietly..."
    wine "$redist" /install /quiet /norestart || true
    wineserver -w || true
    rm -rf -- "$tmpdir"
  fi

  if ! vc_runtime_installed; then
    echo "[gsb] ERROR: VC++ x64 runtime is still not registered after both installers." >&2
    echo "[gsb] Check Microsoft installer logs in the Wine prefix's Temp directory." >&2
    exit 4
  fi
  echo "[gsb] Microsoft VC++ x64 runtime verified."
else
  echo "[gsb] Microsoft VC++ x64 runtime already present."
fi

# Same Steam DLL registry entries that fixed the user's native Wine server.
STEAM64="$(winepath -w /server/steamclient64.dll)"
STEAM32="$(winepath -w /server/steamclient.dll)"
STEAMPATH="$(winepath -w /server)"
STEAMKEY='HKCU\Software\Valve\Steam\ActiveProcess'
wine reg add "$STEAMKEY" /v SteamClientDll64 /t REG_SZ /d "$STEAM64" /f >/dev/null
wine reg add "$STEAMKEY" /v SteamClientDll /t REG_SZ /d "$STEAM32" /f >/dev/null
wine reg add "$STEAMKEY" /v SteamPath /t REG_SZ /d "$STEAMPATH" /f >/dev/null

# The game itself set SteamAppId=3891040 in the successful host trace.
# The server folder is a writable bind mount; preserve all other game files.
printf '%s\n' "$GSB_APP_ID" > /server/steam_appid.txt

export SteamAppId="$GSB_APP_ID"
export SteamGameId="$GSB_APP_ID"

echo "[gsb] Starting MZServer.exe using Wine; App ID $GSB_APP_ID"
echo "[gsb] Steam DLL: $STEAM64"
echo "[gsb] Server directory: /server (host bind mount)"
echo "[gsb] Expect UDP 7777 and 27015 with default server config."

# The Windows launcher starts MZServer-Win64-Shipping.exe and MZServerConsole.exe.
# Keep the Windows process in the foreground for Docker's restart policy.
wine ./MZServer.exe -useperfthreads -log LOG=MZServer.log
