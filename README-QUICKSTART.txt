GSB Docker v10 — end-user quickstart (NO host scripts)

1. You already have an existing Windows GSB dedicated server directory containing
   MZServer.exe, steamclient DLLs, and the MZClient folder.
2. Publish the GHCR image first (see README.md). It has NOT been published yet.
3. Replace ghcr.io/OWNER/REPOSITORY with your actual image path and run:

docker run -dit --name gsb --platform linux/amd64 --network host \
  --restart unless-stopped --stop-timeout 120 --shm-size 512m \
  -e GSB_UID="$(id -u)" -e GSB_GID="$(id -g)" \
  --mount type=bind,source="$HOME/GSBPTESTSVR",target=/server \
  --mount type=volume,source=gsb-wine-data,target=/home/gsb/.wine-gsb \
  ghcr.io/OWNER/REPOSITORY:v10.0.0

MANAGE:
  docker logs -f gsb
  docker exec gsb gsbctl probe
  docker exec gsb gsbctl status
  docker exec gsb gsbctl players
  docker exec gsb gsbctl save
  docker stop -t 120 gsb
  docker start gsb

Autosave: enabled every 30 minutes; normal stop sends game's save+shutdown.
Do not use docker kill or run two servers against one save folder.
