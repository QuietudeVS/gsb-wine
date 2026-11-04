"""Source-level smoke tests; no Wine or Docker daemon required."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def run(args, **kwargs):
    return subprocess.run([sys.executable, str(ROOT / args[0]), *args[1:]],
                          capture_output=True, text=True, check=True, **kwargs)


class ConsoleFormatterTest(unittest.TestCase):
    def test_status_drops_known_corrupt_lines(self):
        sample = "> statusicated Server\n> status is running. Map: Birmingham_Ver01_WP. Players: 0.\n> Server is running. Map: Birmingham_Ver01_WP. Players: 0.\n"
        p = run(['gsb-format-console.py', 'status'], input=sample)
        self.assertEqual(p.stdout.strip(), '> Server is running. Map: Birmingham_Ver01_WP. Players: 0.')

    def test_players_and_save(self):
        self.assertEqual(run(['gsb-format-console.py', 'players'], input='> No players connected.\n').stdout.strip(), '> No players connected.')
        self.assertEqual(run(['gsb-format-console.py', 'save'], input='> Save completed.\n').stdout.strip(), '> Save completed.')


class ServerctlTest(unittest.TestCase):
    def test_config_and_backup(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            config_dir = root / 'MZClient/Saved/Config'
            config_dir.mkdir(parents=True)
            sample = {
                'ServerSettings': {
                    'Port': 7777, 'Name': 'Unnamed Server', 'Description': 'Default',
                    'IsPublic': True, 'Password': '', 'MaxPlayers': 4,
                }
            }
            (config_dir/'serverconfig_sample.json').write_text(json.dumps(sample))
            run(['serverctl.py', 'init', '--server-dir', t])
            run(['serverctl.py', 'configure', '--server-dir', t, '--name', 'Test Birmingham', '--max-players', '6'])
            run(['serverctl.py', 'init', '--server-dir', t])
            cfg = json.loads((config_dir/'serverconfig.json').read_text())
            self.assertEqual(cfg['ServerSettings']['Name'], 'Test Birmingham')
            self.assertEqual(cfg['ServerSettings']['MaxPlayers'], 6)
            saved = root / 'MZClient/Saved/SaveGames/Multi'
            saved.mkdir(parents=True)
            (saved/'SaveGame.sav').write_bytes(b'fixture-data')
            proc = run(['serverctl.py', 'backup', '--server-dir', t])
            self.assertIn('Backup created:', proc.stdout)
            backup = next((root/'.gsb-backups').glob('*.tar.gz'))
            self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
            with tarfile.open(backup, 'r:gz') as f:
                self.assertIn('game/MZClient/Saved/SaveGames/Multi/SaveGame.sav', f.getnames())


if __name__ == '__main__':
    unittest.main()
