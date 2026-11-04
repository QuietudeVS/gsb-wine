#!/usr/bin/env python3
"""Conservative text-only filter for Wine's 80-column console buffer.

We DON'T modify the game console or Windows buffer. Wine may overwrite old
screen cells, so only print intact recognizable responses. If a future game
version changes the response, show recent raw text instead of concealing it.
The result is a console *snapshot*, not a confirmed reply to the newest command.
"""
import re
import sys

if len(sys.argv) != 2 or sys.argv[1] not in ("status", "players", "save"):
    raise SystemExit("Usage: gsb-format-console.py {status|players|save}")
command = sys.argv[1]
lines = sys.stdin.read().splitlines()

# Exclude obvious partially-overwritten echoes, but never mutate the original.
patterns = {
    "status": [r"^>\s*Server is running\. Map: .+\. Players: \d+\.$"],
    "players": [r"^>\s*No players connected\.$"],
    "save": [r"^>\s*Save completed\.$"],
}
found = [line for line in lines if any(re.match(p, line) for p in patterns[command])]
if found:
    for line in found[-5:]:
        print(line)
else:
    print("[gsbctl] No recognized response in console snapshot; recent raw lines follow:")
    recent = [s for s in lines if s.strip() and not s.startswith("MZ Server Console [Wine PID")]
    for line in recent[-12:]:
        print(line)
