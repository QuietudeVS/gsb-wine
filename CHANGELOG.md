# Changelog

## v10.0.0 — host-script-free runtime image (source release)
- Fully in-image `gsbctl` for status, players, save, console, config and backups.
- Automatic creation of game config from the game-provided sample.
- Host user UID/GID configurable through two `docker run -e` flags, rather than a build.
- Empty persistent Docker Wine named-volume ownership initialized safely.
- Preserve in-container 30-minute autosave and 120-second graceful shutdown.
- Preserve the conservative console text reader and filter from v9.
- No host setup script or Compose file necessary; one `docker run` command suffices.
- GitHub Actions workflow publishes images to GHCR on tag pushes.
- Does NOT contain the proprietary Windows server binaries.

Note: v10 needs a live Wine/game validation. Source checked locally; not yet built/published to registry.
