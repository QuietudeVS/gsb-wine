#!/usr/bin/env python3
"""In-container configuration and manual backup CLI for GSB.

Reads the game's own serverconfig_sample.json as the source of defaults and keys.
No personal server settings are shipped with this tool.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import getpass
import io
import json
import os
from pathlib import Path
import re
import sys
import tarfile
import tempfile

HERE = Path(__file__).resolve().parent
CONFIG_REL = Path('MZClient/Saved/Config/serverconfig.json')
SAMPLE_REL = Path('MZClient/Saved/Config/serverconfig_sample.json')
FIELDS = ('port', 'name', 'description', 'public', 'password', 'maxPlayers')
ALIASES = {
    'port': ('port', 'serverport', 'gameport', 'listenport'),
    'name': ('name', 'servername', 'serverdisplayname'),
    'description': ('description', 'serverdescription', 'serverdesc'),
    'public': ('public', 'ispublic', 'publicserver', 'islisted', 'serverpublic', 'bpublic', 'bispublic', 'ispublicserver'),
    'password': ('password', 'serverpassword', 'joinpassword'),
    'maxPlayers': ('maxplayers', 'maxplayercount', 'maxclients', 'playerlimit', 'playerslimit'),
}


def fail(message: str):
    raise SystemExit(f'ERROR: {message}')


def json_without_comments(source: str) -> str:
    """Accept JSON/JSONC sample files while respecting comment characters in strings."""
    out = []
    in_string = False
    escaped = False
    i = 0
    while i < len(source):
        c = source[i]
        if in_string:
            out.append(c)
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            out.append(c)
            i += 1
            continue
        if source[i:i+2] == '//':
            i += 2
            while i < len(source) and source[i] != '\n':
                i += 1
            continue
        if source[i:i+2] == '/*':
            end = source.find('*/', i + 2)
            if end < 0:
                fail('Unclosed /* comment in configuration')
            i = end + 2
            continue
        out.append(c)
        i += 1
    no_comments = ''.join(out)
    # Remove commas before } or ], but not those within quoted strings.
    out = []
    in_string = False
    escaped = False
    i = 0
    while i < len(no_comments):
        c = no_comments[i]
        if in_string:
            out.append(c)
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
            out.append(c)
        elif c == ',':
            j = i + 1
            while j < len(no_comments) and no_comments[j].isspace():
                j += 1
            if j < len(no_comments) and no_comments[j] in '}]':
                i += 1
                continue
            out.append(c)
        else:
            out.append(c)
        i += 1
    return ''.join(out)


def read_config(path: Path) -> dict:
    try:
        obj = json.loads(json_without_comments(path.read_text(encoding='utf-8-sig')))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f'Could not parse {path}: {exc}')
    if not isinstance(obj, dict):
        fail(f'{path} must contain a JSON object')
    return obj


def normalize(s: str) -> str:
    return re.sub(r'[^a-z0-9]', '', s.casefold())


def matching_paths(root: dict, field: str) -> list[tuple[str, ...]]:
    acceptable = set(ALIASES[field])
    matches = []

    def walk(obj, path=()):
        if not isinstance(obj, dict):
            return
        for key, value in obj.items():
            p = path + (key,)
            if normalize(key) in acceptable:
                matches.append(p)
            if isinstance(value, dict):
                walk(value, p)

    walk(root)
    return matches


def resolve(root: dict, field: str, required=True):
    paths = matching_paths(root, field)
    if not paths:
        if required:
            fail(f'Could not find field {field!r} in game JSON. Run with a supported sample/config file; do not invent a new JSON key.')
        return None
    if len(paths) > 1:
        # A shallow key is unambiguous only if exactly one lives at the shallowest depth.
        depth = min(len(p) for p in paths)
        shortest = [p for p in paths if len(p) == depth]
        if len(shortest) != 1:
            fail(f'Ambiguous {field!r} fields: {", ".join(".".join(p) for p in paths)}')
        return shortest[0]
    return paths[0]


def value_at(root, path):
    for key in path:
        root = root[key]
    return root


def assign(root, path, value):
    for key in path[:-1]:
        root = root[key]
    root[path[-1]] = value


def server_dir_from_env() -> Path:
    # Running inside the Docker image; no host-side .env/setup.sh needed.
    return Path('/server')


def config_paths(server_dir: Path):
    sample = server_dir / SAMPLE_REL
    config = server_dir / CONFIG_REL
    if not sample.is_file():
        fail(f'Game-supplied defaults missing: {sample}')
    return sample, config


def write_config(path: Path, obj: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2) + '\n'
    # Atomic replacement: a failed write cannot leave partially written JSON.
    fd, temp = tempfile.mkstemp(prefix='.gsb-config-', dir=path.parent, text=True)
    try:
        if path.exists():
            os.fchmod(fd, path.stat().st_mode & 0o777)
        else:
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def apply_identity_defaults(obj, sample):
    for field in ('name', 'description'):
        source = resolve(sample, field)
        target = resolve(obj, field)
        assign(obj, target, copy.deepcopy(value_at(sample, source)))


def parse_bool(value):
    if value.casefold() in ('true', 'yes', '1', 'on'):
        return True
    if value.casefold() in ('false', 'no', '0', 'off'):
        return False
    fail('--public must be true or false')


def updates_from_args(args):
    out = {}
    for field, arg in (('port', 'port'), ('name', 'name'), ('description', 'description'),
                       ('public', 'public'), ('password', 'password'), ('maxPlayers', 'max_players')):
        value = getattr(args, arg, None)
        if value is None:
            continue
        if field in ('port', 'maxPlayers'):
            try:
                value = int(value)
            except ValueError:
                fail(f'--{arg.replace("_", "-")} must be an integer')
            if field == 'port' and not (1 <= value <= 65535):
                fail('--port must be 1–65535')
            if field == 'maxPlayers' and value <= 0:
                fail('--max-players must be positive')
        elif field == 'public':
            value = parse_bool(value)
        out[field] = value
    if getattr(args, 'password_prompt', False):
        if 'password' in out:
            fail('Use either --password or --password-prompt')
        out['password'] = getpass.getpass('Server password (blank for none): ')
    return out


def apply_updates(obj, changes):
    for field, value in changes.items():
        path = resolve(obj, field)
        old = value_at(obj, path)
        # Respect the game's own JSON schema; don't add unknown keys.
        if isinstance(old, bool):
            if not isinstance(value, bool):
                fail(f'Game field {field} expects a boolean')
        elif isinstance(old, int) and not isinstance(old, bool):
            if not isinstance(value, int) or isinstance(value, bool):
                fail(f'Game field {field} expects an integer')
        elif isinstance(old, str):
            if not isinstance(value, str):
                fail(f'Game field {field} expects a string')
        elif old is not None:
            fail(f'Unsupported game schema type for {field}: {type(old).__name__}')
        assign(obj, path, value)


def display_config(obj):
    print('Server settings (password value hidden):')
    for field in FIELDS:
        p = resolve(obj, field, required=False)
        if not p:
            print(f'  {field}: <not found>')
            continue
        val = value_at(obj, p)
        if field == 'password':
            val = '<set>' if val else '<empty>'
        print(f'  {field}: {val}')


def configure(args):
    server_dir = Path(args.server_dir).resolve() if args.server_dir else server_dir_from_env()
    sample_path, config_path = config_paths(server_dir)
    sample = read_config(sample_path)
    if config_path.is_file():
        obj = read_config(config_path)
    else:
        obj = copy.deepcopy(sample)
        print('[gsb] Created config from the game-supplied sample defaults.')
    if args.reset_identity:
        apply_identity_defaults(obj, sample)
        print('[gsb] Reset server name and description to sample defaults.')
    changes = updates_from_args(args)
    apply_updates(obj, changes)
    if args.command == 'init' or args.reset_identity or changes or not config_path.is_file():
        write_config(config_path, obj)
        print(f'[gsb] Configuration ready: {config_path}')
    display_config(obj)


def backup(args):
    server_dir = Path(args.server_dir).resolve() if args.server_dir else server_dir_from_env()
    saved = server_dir / 'MZClient/Saved'
    if not saved.is_dir():
        fail(f'Missing saved-data directory: {saved}')
    dest = Path(args.output).expanduser().resolve() if args.output else server_dir / '.gsb-backups'
    dest.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    filename = dest / f'gsb-backup-{stamp}.tar.gz'
    if filename.exists():
        fail(f'Backup already exists: {filename}; retry in a second')
    partial = filename.with_suffix('.tar.gz.partial')
    print('NOTE: This copies the last saved on-disk state; it cannot trigger an in-game save.')
    print('For a consistent backup, first run docker exec gsb gsbctl save, confirm the game saved, then let writes finish.')
    try:
        with tarfile.open(partial, 'w:gz') as archive:
            archive.add(saved, arcname='game/MZClient/Saved', recursive=True)
            # Some Unreal builds save into the Wine user's Local AppData instead.
            wine_users = Path(os.getenv('WINEPREFIX', '/home/gsb/.wine-gsb')) / 'drive_c/users'
            if wine_users.is_dir():
                for appdata in wine_users.glob('*/AppData/Local'):
                    for game_name in ('MZClient', 'MZServer'):
                        game_saved = appdata / game_name / 'Saved'
                        if game_saved.is_dir():
                            username = appdata.parents[1].name
                            archive.add(game_saved, arcname=f'wine/{username}/{game_name}/Saved')
            manifest = json.dumps({
                'createdUTC': datetime.now(timezone.utc).isoformat(),
                'warning': 'Snapshot of disk files only; no game save command issued.',
                'serverData': 'game/MZClient/Saved',
                'wineGameSavedData': 'wine/ when present',
            }, indent=2).encode()
            info = tarfile.TarInfo('manifest.json')
            info.size = len(manifest)
            info.mode = 0o600
            archive.addfile(info, io.BytesIO(manifest))
        os.replace(partial, filename)
    finally:
        if partial.exists():
            partial.unlink()
    os.chmod(filename, 0o600)
    print(f'Backup created: {filename}')
    print('Backups may contain configuration passwords. Store them privately.')


def add_config_options(parser):
    parser.add_argument('--port', help='UDP game listening port')
    parser.add_argument('--name', help='Server display name')
    parser.add_argument('--description', help='Server description')
    parser.add_argument('--public', help='true or false')
    parser.add_argument('--password', help='Server password (shell history warning)')
    parser.add_argument('--password-prompt', action='store_true', help='Secure interactive password prompt')
    parser.add_argument('--max-players', dest='max_players', help='Maximum players')
    parser.add_argument('--reset-identity', action='store_true', help='Restore name and description from the included game sample')


def main():
    parser = argparse.ArgumentParser(description='Configure GSB game server and create optional backups.')
    subs = parser.add_subparsers(dest='command', required=True)
    for cmd in ('init', 'configure'):
        p = subs.add_parser(cmd, help='Initialize or edit six supported game settings')
        p.add_argument('--server-dir', help='Game directory (default /server)')
        add_config_options(p)
    p = subs.add_parser('backup', help='Manually back up on-disk saves and configuration')
    p.add_argument('--server-dir', help='Game directory (default /server)')
    p.add_argument('--output', help='Backup destination (default ./backups/)')
    args = parser.parse_args()
    if args.command in ('init', 'configure'):
        configure(args)
    else:
        backup(args)


if __name__ == '__main__':
    main()
