# God Save Birmingham — Docker v10.1.0

A **self-contained Linux/amd64 Docker image**, using Wine to run the Windows dedicated server. **No host-side setup scripts** and no host-side `gsbctl` required. Run by **one `docker run` command** or by the included **optional `compose.yaml`**.

**Published image location (after releasing v10.1.0):** `ghcr.io/quietudevs/gsb-wine:v10.1.0`.

> Release status: this v10.1.0 source has passed local shell/Python tests, but has not yet been built on GitHub or tested with the live GSB game. The previously published `v10.0.1` image is a distinct release; it does **not** support the new `GSB_SERVER_*` settings. Never claim v10.1.0 is published until the Actions job succeeds.

## Requirements

- Linux host with Docker Engine and Linux/amd64 support; source game files for the Windows GSB dedicated server including `MZServer.exe`, DLLs, and the `MZClient` folder.
- A **writable persistent directory** on the host, e.g. `$HOME/GSBPTESTSVR`. The image does **not** distribute/download proprietary game files.
- Free game ports. This uses host networking, matching the proven earlier Docker deployment; default game UDP ports are `7777` and `27015`. Configure your firewall/router separately.
- Do not run another GSB process against the same folder at the same time.

## Option A: single `docker run` command

No setup scripts, Compose files, or image build. The image pulls automatically if it is absent:

```bash
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
  -e GSB_SERVER_NAME="My Birmingham Server" \
  -e GSB_SERVER_DESCRIPTION="Survival with friends" \
  -e GSB_SERVER_PORT=7777 \
  -e GSB_SERVER_MAX_PLAYERS=8 \
  -e GSB_SERVER_PUBLIC=true \
  --mount type=bind,source="$HOME/GSBPTESTSVR",target=/server \
  --mount type=volume,source=gsb-wine-data,target=/home/gsb/.wine-gsb \
  ghcr.io/quietudevs/gsb-wine:v10.1.0
```

You can omit **any** `GSB_SERVER_*` lines to keep the preexisting `serverconfig.json` value for that field. On first boot, missing configuration is created from the game's own sample file. Existing fields not specified in the command are preserved. Supplied overrides are applied at **each container start**, so if you later change a setting manually using `gsbctl configure`, remove that setting's environment variable before recreating the container if you want the manual change to persist.

If already running another GSB container, stop it gracefully before running this command with the same folder or container name. Do not simultaneously run v8/v9/v10 or native Wine against the same saves.

### Configuration options

| Env variable | Description | If omitted |
|---|---|---|
| `GSB_SERVER_NAME` | Game server display name | Preserve saved value / game default |
| `GSB_SERVER_DESCRIPTION` | Server description | Preserve |
| `GSB_SERVER_PORT` | Game listen port, 1–65535 | Preserve |
| `GSB_SERVER_MAX_PLAYERS` | Positive integer | Preserve |
| `GSB_SERVER_PUBLIC` | `true` or `false` | Preserve |
| `GSB_SERVER_PASSWORD` | Game join password (including `""` to clear) | Preserve |
| `GSB_SERVER_PASSWORD_FILE` | File path inside container holding the join password | Preserve |
| `GSB_AUTOSAVE_ENABLED` | `1` (default) or `0` | Autosave on |
| `GSB_AUTOSAVE_INTERVAL_SECONDS` | Autosave interval, defaults `1800` | Every 30 minutes |
| `GSB_UID`, `GSB_GID` | Host file ownership IDs | Both default to 1000 in image |

The game config is persisted in `/server/MZClient/Saved/Config/serverconfig.json`, i.e. the bind-mounted host directory. The image only edits existing keys recognized from the game's sample; it does not synthesize unrecognized keys.

**Security:** Avoid `-e GSB_SERVER_PASSWORD=...` for real passwords: Docker environment variables can be exposed by Docker inspect, process inspection and other privileged tooling. To configure a secret interactively after launch, use `docker exec -it gsb gsbctl configure --password-prompt`. Alternatively, mount a password file read-only and provide `-e GSB_SERVER_PASSWORD_FILE=/run/secrets/gsb_password`; the file must be readable to the in-container `gsb` user. The password file must not be committed to GitHub. Both password environment variants cannot be set at once.

## Option B: optional Docker Compose

The **same image** can be run by `compose.yaml` (included in this repository). Copy `compose.yaml` to your Linux deployment folder. By default it expects a sibling `./GSBPTESTSVR` containing the game files, or set `GSB_SERVER_DIR` in `.env` to an absolute host path.

An optional `.env.example` is included to show available settings. To customize settings, copy it to `.env` alongside `compose.yaml` and uncomment only your desired values. The Compose file uses `- GSB_SERVER_NAME`-style pass-through so unset settings are **not** forwarded to the container. Your `.env` belongs on your deployment machine, not in your public GitHub repository.

```bash
# In the directory containing compose.yaml:
cp .env.example .env                 # optional; edit GSB_SERVER_DIR, UID/GID and server settings
# If your host UID/GID aren't 1000, set GSB_UID=$(id -u), GSB_GID=$(id -g) in .env.
docker compose up -d
docker compose logs -f gsb
```

If you don't want to create an `.env`, configure the optional settings through shell environment variables, e.g. `GSB_SERVER_NAME='Birmingham' GSB_SERVER_MAX_PLAYERS=8 docker compose up -d`. If a port other than 7777 is chosen, open it in your firewall/router; host networking means no `ports:` mapping.

### Game commands (both deployment methods)

```bash
docker exec gsb gsbctl probe
docker exec gsb gsbctl status
docker exec gsb gsbctl players
docker exec gsb gsbctl save
docker exec gsb gsbctl console
# Show/change a setting without environment variables:
docker exec gsb gsbctl configure
# On-demand on-disk backup (make sure world has saved first):
docker exec gsb gsbctl backup

# The game 'shutdown' command saves the world and exits cleanly:
docker stop -t 120 gsb
# Or with Compose:
docker compose stop gsb
```

Autosave runs inside the container every 30 minutes by default. Normal Docker stop is supervised: Docker's SIGTERM is forwarded as the game's graceful `shutdown` console command. Docker `kill`, `rm -f`, power loss or a stop timeout cannot guarantee save completion. The console reader can show prior responses; the text filter removes some known corrupted console lines but does not modify game memory.

## Updating the image later

**Docker can pull new images, but `docker pull` by itself does not update a running container.** You must recreate the container while keeping the same mounts.

### `docker run` users

```bash
# 1. Save and make an optional backup:
docker exec gsb gsbctl save
# 2. Stop gracefully and remove only the container, NOT the saved data:
docker stop -t 120 gsb
docker rm gsb
# 3. Pull the new version:
docker pull ghcr.io/quietudevs/gsb-wine:NEW_VERSION
# 4. Repeat the original docker run command, changing only the image tag.
#    Reuse the EXACT same /server bind mount and named volume gsb-wine-data.
```

### Compose users

Change `GSB_IMAGE_TAG` in `.env` (or update the `image:` tag in `compose.yaml`) to the new version, then:

```bash
docker compose pull
docker compose up -d
```

Compose will stop/recreate containers whose images changed, preserving bind mounts and named volumes. The `stop_grace_period: 120s` gives the game time to shut down gracefully. Versioned image tags are preferable to mutable `latest`. **Do not run `docker compose down -v`**, which removes named volumes. Docker does not automatically apply updates on a timer unless you separately configure an updater. Docker's official documentation covers this behavior.

## GitHub publishing (maintainers)

Image has a public registry address only once the GitHub Actions job for tag `v10.1.0` succeeds. The included `.github/workflows/publish-image.yml` builds the image for Linux/amd64, tests scripts, and publishes `ghcr.io/<repo-owner>/<repo-name>:v10.1.0` and `:latest` using `GITHUB_TOKEN`.

To publish from a Windows browser, upload the changed v10.1.0 source files to **the root** of the existing `QuietudeVS/gsb-wine` GitHub repository, commit the changes on `main`, and **only then** create the new release/tag `v10.1.0` targeted at `main`. Don't delete the existing `.github/workflows/publish-image.yml` workflow; it's unchanged. Watch the workflow under the **Actions** tab. If the GHCR package is already public, its new version should inherit package visibility.

Do **not** upload game binaries, save games, real passwords, or Wine data to GitHub. See `GITHUB_UPDATE_BROWSER.md` for specific click-by-click instructions.

## Validation status

The shell syntax checks, Python compilation, local unit tests for configuration/backup and environment override behavior, and YAML parsing passed locally. The optional Compose file has been statically validated but has not been tested with a Docker daemon here. **The real v10.1.0 image startup, runtime settings, and graceful stop still need verification on a live host.** Proven production behavior in previous versions does not constitute a v10.1.0 live test.
