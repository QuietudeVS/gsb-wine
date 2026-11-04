# God Save Birmingham — Docker v10 (host-script-free image)

**One Docker image; no host-side `setup.sh`, `gsbctl`, cron, or Compose files.**

The image packages Ubuntu 24.04, Wine, Xvfb, runtime libraries, console commands, a text console reader, and autosave/graceful-stop supervision. It **does not include the Windows game server**. Each server owner must have a legitimate Windows dedicated-server installation, such as `/home/gsb/GSBPTESTSVR`, with `MZServer.exe` and its accompanying files.

> **Release state:** The v10 sources are prepared and have local syntax/unit checks, but v10 has **not** been built against Docker or tested with the real game in this workspace. Docker v8 and native Linux v2 were previously proven on real hosts. The GHCR image is **not yet published**. Do not use the example GHCR address until the workflow has successfully published an image and you have made the package public.

## End-user setup (after image is published)

Host prerequisites: Linux amd64 Docker engine, the Windows server files in a writable host directory, and free network ports. By default the server uses UDP `7777` and `27015` (check actual game config). `--network host` mirrors the proven Docker v8 behavior; no `-p` mappings are needed. Configure a firewall/router separately.

You can **skip `docker pull`**: `docker run` will automatically pull the image if it is not present.

```bash
# Optional: pre-pull the published image
docker pull ghcr.io/OWNER/REPOSITORY:v10.0.0

# One-time start: no host scripts; host directory must already exist.
docker run -dit \
  --name gsb \
  --platform linux/amd64 \
  --network host \
  --restart unless-stopped \
  --stop-timeout 120 \
  --shm-size 512m \
  --security-opt no-new-privileges \
  -e GSB_UID="$(id -u)" \
  -e GSB_GID="$(id -g)" \
  --mount type=bind,source="$HOME/GSBPTESTSVR",target=/server \
  --mount type=volume,source=gsb-wine-data,target=/home/gsb/.wine-gsb \
  ghcr.io/OWNER/REPOSITORY:v10.0.0
```

Replace `OWNER/REPOSITORY` with the actual GitHub repository, and adjust `$HOME/GSBPTESTSVR` to the **absolute** location of your own Windows server files. The image does not download the game. The directory must be **writable** by the UID/GID supplied. The named Docker volume keeps the Wine prefix across container recreation, and `SaveGame.sav` remains directly in the bind-mounted host game folder.

The `-it` flags preserve the allocated interactive TTY used by our previously working Docker/Wine setup; console input still uses the Wine/Xvfb window internally.

The image initializes `MZClient/Saved/Config/serverconfig.json` from the **game's own sample** when missing; it never overwrites an existing config. First launch may take several minutes for Wine prefix creation and Microsoft VC++ redistribution. Network access is required on first launch to obtain the runtime if not already installed.

## Normal operations (standard Docker commands)

```bash
docker logs -f gsb                    # startup logs and 30-min autosave

docker exec gsb gsbctl probe         # find MZ Server Console
docker exec gsb gsbctl status        # display server status
docker exec gsb gsbctl players       # player count/list
docker exec gsb gsbctl save          # save without stopping
docker exec gsb gsbctl console       # full raw Windows console snapshot

docker stop -t 120 gsb               # in-game 'shutdown' = save + exit
docker start gsb                     # restart later
docker restart -t 120 gsb            # graceful restart
```

`docker exec gsb gsbctl` runs console and Wine commands as the non-root `gsb` user even though `docker exec` defaults to root. Each command reports console text where supported. **Console text is a snapshot**, and Wine may retain or partially overwrite older lines; the filter does not modify the actual game or console.

> **Do not use `docker kill`, `docker rm -f`, or a too-short stop timeout.** Docker sends SIGKILL if it hits the timeout. A forced kill or power failure cannot guarantee the world is saved. Do not simultaneously run this container and a native/Docker game instance against the same world directory.

### Server settings

```bash
# See current game settings (password hidden)
docker exec gsb gsbctl configure

# Configure using the game's original schema; settings may require a restart
docker exec gsb gsbctl configure --name 'My Birmingham' --max-players 8 --public false
```

The serverconfig file is owned by the host user and remains at `~/GSBPTESTSVR/MZClient/Saved/Config/serverconfig.json` (if that is the host bind mount). To set a password without shell history exposure, use `docker exec -it gsb gsbctl configure --password-prompt` (a terminal is required). Never include secrets in a published repository or screenshots.

### Autosave and manual backups

Autosave is **enabled every 30 minutes**; it runs completely inside the image, calls the same game `save` console command, and does not generate archives. Optional environment flags in `docker run`:

```text
-e GSB_AUTOSAVE_ENABLED=0
-e GSB_AUTOSAVE_INTERVAL_SECONDS=1800
```

For an on-demand snapshot archive (separate from the game's periodic backup `.sav` files):

```bash
docker exec gsb gsbctl save
docker exec gsb gsbctl backup
```

`backup` writes a `.tar.gz` under `/server/.gsb-backups` (so it persists in the host game directory). It copies saved files **on disk** and does not itself trigger a game save. Store external copies of backups; a backup next to game files does not protect against a disk failure.

### Image update without losing saved data

1. Make a backup and use `docker stop -t 120 gsb`.
2. Pull the new image with `docker pull ghcr.io/OWNER/REPOSITORY:NEW_TAG`.
3. `docker rm gsb` (do **not** delete your Windows server files or the `gsb-wine-data` volume).
4. Repeat the `docker run` command with the new tag, same bind mount, same volume, UID/GID.

When `--restart unless-stopped` is used, Docker restores a previously running container at boot when Docker starts, but does not revive a container you intentionally stopped. A real reboot test is still recommended.

## Publishing to GitHub Container Registry (maintainer)

1. Create a GitHub repo (e.g. `YOURNAME/gsb-wine`).
2. Commit the contents of **this source kit at repository root** (including `.github/workflows/publish-image.yml`, `Dockerfile`, shell scripts, reader source/executable). **Never commit the game files**, your `serverconfig.json`, your `.env`, or saves.
3. Push tag `v10.0.0`. The GitHub Actions workflow builds `linux/amd64` and pushes image `ghcr.io/YOURNAME/REPOSITORY:v10.0.0` plus `:latest` using the repository-scoped `GITHUB_TOKEN` with `packages: write`.
4. GitHub Container Registry packages are **private by default**. In your package settings, set visibility to **Public** to let others pull without logging in.
5. Test the published image on a spare server directory before recommending it for production. Check in-game save, 30-minute autosave, `docker stop -t 120` and restart persistence.

See [GitHub's official GHCR documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) for public visibility and package permissions.

## Development and known limitations

- Wine/Windows server targets `linux/amd64` only. An ARM Linux host must support amd64 emulation and may be too slow.
- Ubuntu 24.04 in container works independently of a Ubuntu 26 host; users only need Docker.
- First-run VC++ installer downloads an executable from a Microsoft HTTPS URL. Failures must be handled according to logs.
- `GSB_UID` and `GSB_GID` default to `1000:1000`. Provide `$(id -u)` and `$(id -g)` in the run command for hosts with different IDs. This helps keep game files writable without root-running the game. Existing volume ownership from other IDs may require manual correction.
- The game uses the Xvfb virtual desktop internally. Console windows are auto-discovered rather than identified by a persistent X11 window ID.
- Default UDP ports are based on observed prior game config. Check your actual server settings and network topology.
- No automated image publication has occurred in this sandbox; the workflow needs your GitHub repository and Actions permissions.
- The v10 changes require a real Docker image build and live server test before relying on them. Source unit checks cannot substitute for a full Wine/game integration test.
