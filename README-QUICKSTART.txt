GSB Docker v10.1.0 — two ways to deploy (NO host scripts)

The published image will be ghcr.io/quietudevs/gsb-wine:v10.1.0 AFTER
GitHub Actions publishes the v10.1.0 tag. It is NOT yet published.

Prerequisite: You own Windows game server files in ~/GSBPTESTSVR including
MZServer.exe. Docker on a Linux x86-64 host; UDP game ports accessible.

OPTION A — single docker run (change folder / settings):

docker run -dit --name gsb --platform linux/amd64 --network host \
  --restart unless-stopped --stop-timeout 120 --shm-size 512m \
  --security-opt no-new-privileges \
  -e GSB_UID="$(id -u)" -e GSB_GID="$(id -g)" \
  -e GSB_SERVER_NAME="My Birmingham Server" \
  -e GSB_SERVER_MAX_PLAYERS=8 \
  -e GSB_SERVER_PUBLIC=true \
  --mount type=bind,source="$HOME/GSBPTESTSVR",target=/server \
  --mount type=volume,source=gsb-wine-data,target=/home/gsb/.wine-gsb \
  ghcr.io/quietudevs/gsb-wine:v10.1.0

OPTION B — optional Compose (place compose.yaml beside GSBPTESTSVR):

  cp .env.example .env    # optional; edit values to suit
  docker compose up -d

COMMANDS:
  docker exec gsb gsbctl status
  docker exec gsb gsbctl players
  docker exec gsb gsbctl save
  docker stop -t 120 gsb                 # graceful game save and shutdown

UPDATING:
  docker pull ghcr.io/quietudevs/gsb-wine:NEW_VERSION
  docker stop -t 120 gsb && docker rm gsb
  # Re-run OPTION A with new tag, SAME mounts and UID/GID.

  OR (for Compose, after setting GSB_IMAGE_TAG to the new version):
  docker compose pull && docker compose up -d

IMPORTANT: pulling does not replace a running container. Preserve /server
and the named volume gsb-wine-data; never use docker kill for normal stops.
