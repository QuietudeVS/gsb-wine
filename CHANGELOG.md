# Changelog

## v10.1.0 — environment configuration and optional Compose

- Add `GSB_SERVER_NAME`, `GSB_SERVER_DESCRIPTION`, `GSB_SERVER_PORT`,
  `GSB_SERVER_MAX_PLAYERS`, `GSB_SERVER_PUBLIC`, and `GSB_SERVER_PASSWORD`
  as optional `docker run -e` or Compose settings.
- Add optional `GSB_SERVER_PASSWORD_FILE` for reading a mounted secret file.
- Apply game-setting environment overrides at startup while preserving all
  unspecified fields and existing saves and configs.
- Add optional `compose.yaml` and `.env.example`, no host management scripts.
- Document versioned image updates and persistent volume preservation.
- Keep v10.0.1's graceful shutdown, 30-minute autosave, console reader, UID/GID
  mapping, and GHCR publishing workflow unchanged.
- Unit tests added for first-run configuration, override behavior, validation,
  password handling, and non-rewriting of unchanged configuration.

## Previous versions

See the earlier Docker v10 source release for v10.0.x changes.
