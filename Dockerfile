# God Save Birmingham dedicated server — standalone Docker image (no host scripts).
# Supply legally acquired Windows server files as a writable /server bind mount.
# The proprietary game executable is NOT redistributed in this image.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    LANG=C.UTF-8 \
    HOME=/home/gsb \
    WINEPREFIX=/home/gsb/.wine-gsb \
    WINEARCH=win64 \
    GSB_APP_ID=3891040 \
    GSB_AUTOSAVE_ENABLED=1 \
    GSB_AUTOSAVE_INTERVAL_SECONDS=1800

RUN dpkg --add-architecture i386 \
 && apt-get update \
 && apt-get install -y --no-install-recommends \
      wine wine64 wine32:i386 winetricks xvfb xauth cabextract \
      curl ca-certificates winbind tini unzip fonts-liberation \
      xdotool x11-utils util-linux imagemagick gosu python3-minimal \
 && rm -rf /var/lib/apt/lists/*

# Remove Ubuntu's image account if it owns UID 1000; runtime UID mapping is done
# once by gsb-bootstrap, before dropping all privileges to gsb.
RUN if getent passwd ubuntu >/dev/null; then userdel -r ubuntu 2>/dev/null || userdel ubuntu; fi; \
    if getent group ubuntu >/dev/null; then groupdel ubuntu || true; fi; \
    groupadd -g 1001 gsb \
 && useradd -u 1001 -g 1001 -m -d /home/gsb -s /bin/bash gsb \
 && mkdir -p /server /home/gsb/.wine-gsb /tmp/.X11-unix /usr/local/lib/gsb \
 && chown -R 1001:1001 /home/gsb \
 && chmod 1777 /tmp/.X11-unix

COPY --chmod=0755 gsb-bootstrap.sh /usr/local/bin/gsb-bootstrap
COPY --chmod=0755 entrypoint.sh /usr/local/bin/gsb-entrypoint
COPY --chmod=0755 gsb-console.sh /usr/local/bin/gsb-console
COPY --chmod=0755 gsb-supervisor.sh /usr/local/bin/gsb-supervisor
COPY --chmod=0755 gsb-autosave.sh /usr/local/bin/gsb-autosave
COPY --chmod=0755 gsb-read-console-internal.sh /usr/local/bin/gsb-read-console
COPY --chmod=0755 gsbctl /usr/local/bin/gsbctl
COPY --chmod=0644 gsb-console-reader.exe /usr/local/lib/gsb/gsb-console-reader.exe
COPY --chmod=0644 gsb-format-console.py /usr/local/lib/gsb/gsb-format-console.py
COPY --chmod=0644 serverctl.py /usr/local/lib/gsb/serverctl.py

WORKDIR /server
EXPOSE 7777/udp 27015/udp
STOPSIGNAL SIGTERM
# tini sends TERM to supervisor, which sends the game's save+shutdown command.
# Docker run MUST specify --stop-timeout 120 (default Linux timeout is 10s).
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/gsb-bootstrap"]
