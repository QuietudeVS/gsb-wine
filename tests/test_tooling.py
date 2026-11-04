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


class EnvironmentConfigurationTest(unittest.TestCase):
    def make_server(self, root):
        config_dir = root / 'MZClient/Saved/Config'
        config_dir.mkdir(parents=True)
        sample = {'ServerSettings': {'Port': 7777, 'Name': 'Unnamed Server',
                   'Description': 'Default', 'IsPublic': True,
                   'Password': '', 'MaxPlayers': 4, 'NonStandardSetting': 'keep'},
                  'Version': 1}
        (config_dir/'serverconfig_sample.json').write_text(json.dumps(sample))
        return config_dir/'serverconfig.json'

    def invoke(self, root, variables):
        # Scrub all GSB_SERVER_* names inherited from the ambient environment.
        env = {k: v for k, v in os.environ.items() if not k.startswith('GSB_SERVER_')}
        env.update(variables)
        return subprocess.run([sys.executable, str(ROOT/'serverctl.py'),
                               'configure-env', '--server-dir', str(root)],
                              capture_output=True, text=True, env=env)

    def test_initial_defaults_and_only_explicit_overrides(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            config = self.make_server(root)
            proc = self.invoke(root, {})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            initial = json.loads(config.read_text())
            self.assertEqual(initial['ServerSettings']['Name'], 'Unnamed Server')
            self.assertEqual(initial['ServerSettings']['NonStandardSetting'], 'keep')

            proc = self.invoke(root, {'GSB_SERVER_NAME': 'Birmingham Test',
                                      'GSB_SERVER_MAX_PLAYERS': '8',
                                      'GSB_SERVER_PUBLIC': 'false',
                                      'GSB_SERVER_PORT': '7788',
                                      'GSB_SERVER_DESCRIPTION': 'Friends only'})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            modified = json.loads(config.read_text())
            self.assertEqual(modified['ServerSettings']['Name'], 'Birmingham Test')
            self.assertEqual(modified['ServerSettings']['MaxPlayers'], 8)
            self.assertIs(modified['ServerSettings']['IsPublic'], False)
            self.assertEqual(modified['ServerSettings']['Port'], 7788)
            self.assertEqual(modified['ServerSettings']['Description'], 'Friends only')
            self.assertEqual(modified['ServerSettings']['Password'], '')
            self.assertEqual(modified['ServerSettings']['NonStandardSetting'], 'keep')
            old_bytes = config.read_bytes()
            old_ns = config.stat().st_mtime_ns
            proc = self.invoke(root, {})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(config.read_bytes(), old_bytes)
            self.assertEqual(config.stat().st_mtime_ns, old_ns)

            # Even explicitly provided unchanged values do not rewrite files.
            proc = self.invoke(root, {'GSB_SERVER_NAME': 'Birmingham Test'})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(config.stat().st_mtime_ns, old_ns)

    def test_password_file_and_override_conflict(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            config = self.make_server(root)
            pwfile = root/'password.txt'
            pwfile.write_text('MySecretString!\n')
            proc = self.invoke(root, {'GSB_SERVER_PASSWORD_FILE': str(pwfile)})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(config.read_text())['ServerSettings']['Password'],
                             'MySecretString!')
            self.assertNotIn('MySecretString!', proc.stdout)
            self.assertNotIn('MySecretString!', proc.stderr)
            proc = self.invoke(root, {'GSB_SERVER_PASSWORD': 'plain',
                                      'GSB_SERVER_PASSWORD_FILE': str(pwfile)})
            self.assertNotEqual(proc.returncode, 0)
            self.assertNotIn('plain', proc.stderr)
            proc = self.invoke(root, {'GSB_SERVER_PASSWORD': ''})
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(config.read_text())['ServerSettings']['Password'], '')

    def test_validation_keeps_existing_file_unchanged(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            config = self.make_server(root)
            self.assertEqual(self.invoke(root, {}).returncode, 0)
            before = config.read_bytes()
            for env in ({'GSB_SERVER_PORT': 'bad'}, {'GSB_SERVER_PORT': '0'},
                        {'GSB_SERVER_MAX_PLAYERS': '0'},
                        {'GSB_SERVER_PUBLIC': 'maybe'}, {'GSB_SERVER_NAME': '   '}):
                with self.subTest(env=env):
                    proc = self.invoke(root, env)
                    self.assertNotEqual(proc.returncode, 0)
                    self.assertEqual(config.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
