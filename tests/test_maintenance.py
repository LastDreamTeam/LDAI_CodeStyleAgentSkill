# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Exercise real per-install configuration through the public CLI.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/ld-codestyle-online/scripts/maintain.py'

class MaintenanceTests(unittest.TestCase):
    def run_cli(self, install, data, *args):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--skill-root', str(install),
                               '--data-root', str(data), *args], capture_output=True, text=True,
                              encoding='utf-8', timeout=15)

    def test_config_is_per_install_and_persists_human_name(self):
        self.assertTrue(SCRIPT.is_file(), 'configuration helper must exist')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('codex-cli', 'codex-desktop'):
                (root/name).mkdir()
            a = self.run_cli(root/'codex-cli', root/'data', 'config', '--human-name', '梦')
            self.assertEqual(a.returncode, 0, a.stderr)
            b = self.run_cli(root/'codex-desktop', root/'data', 'show')
            self.assertEqual(b.returncode, 0, b.stderr)
            va, vb = json.loads(a.stdout), json.loads(b.stdout)
            self.assertNotEqual(va['data_dir'], vb['data_dir'])
            self.assertEqual(va['config']['human_name'], '梦')
            self.assertEqual(vb['config']['human_name'], 'LD')
            self.assertEqual(vb['config']['interval_days'], 7)
            again = self.run_cli(root/'codex-cli', root/'data', 'show')
            self.assertEqual(json.loads(again.stdout)['config']['human_name'], '梦')

    def test_auto_update_is_opt_in_persistent_and_per_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            install, other, data = root/'install', root/'other', root/'data'
            install.mkdir()
            other.mkdir()
            result = self.run_cli(install, data, 'show')
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertIs(value['config'].get('auto_update'), False)
            legacy = {'schema_version': 1, 'human_name': '保留', 'interval_days': 9}
            config_file = Path(value['data_dir'])/'config.json'
            config_file.write_text(json.dumps(legacy), encoding='utf-8')
            result = self.run_cli(install, data, 'show')
            self.assertEqual(result.returncode, 0, result.stderr)
            value = json.loads(result.stdout)
            self.assertIs(value['config']['auto_update'], False)
            self.assertEqual(value['config']['human_name'], '保留')
            self.assertEqual(value['config']['interval_days'], 9)
            result = self.run_cli(install, data, 'config', '--auto-update', 'on')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIs(json.loads(result.stdout)['config']['auto_update'], True)
            result = self.run_cli(install, data, 'show')
            self.assertIs(json.loads(result.stdout)['config']['auto_update'], True)
            result = self.run_cli(other, data, 'show')
            self.assertIs(json.loads(result.stdout)['config']['auto_update'], False)
            result = self.run_cli(install, data, 'config', '--auto-update', 'off')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIs(json.loads(result.stdout)['config']['auto_update'], False)
            bad = dict(legacy, auto_update='false')
            raw = json.dumps(bad)
            config_file.write_text(raw, encoding='utf-8')
            result = self.run_cli(install, data, 'show')
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(config_file.read_text(encoding='utf-8'), raw)

    def test_weekly_check_throttles_network_and_records_success(self):
        import importlib.util
        from unittest.mock import Mock
        spec = importlib.util.spec_from_file_location('maintenance', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(getattr(module, 'check', None)), 'weekly check must exist')
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fetch = Mock(return_value={'name': 'ld-codestyle-online', 'version': '0.2.0'})
            result = module.check(directory, module.DEFAULTS, '0.1.0', fetch=fetch, now=1000000)
            self.assertEqual(result['status'], 'update_available')
            result = module.check(directory, module.DEFAULTS, '0.1.0', fetch=fetch, now=1000060)
            self.assertEqual(result['status'], 'not_due')
            self.assertEqual(fetch.call_count, 1)
            state = json.loads((directory/'state.json').read_text())
            self.assertEqual(state['last_success_at'], 1000000)
            result = module.check(directory, module.DEFAULTS, '0.1.0', fetch=fetch,
                                  now=1000000 + 7*24*60*60)
            self.assertEqual(result['status'], 'update_available')
            self.assertEqual(fetch.call_count, 2)

    def test_git_update_fast_forwards_and_refuses_dirty_tree(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('maintenance', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertTrue(callable(getattr(module, 'update_git', None)), 'safe git updater must exist')
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            upstream, installed = base/'upstream', base/'installed'
            def git(where, *args):
                return subprocess.run(['git', '-C', str(where), *args], check=True,
                                      capture_output=True, text=True, timeout=10).stdout.strip()
            upstream.mkdir()
            git(upstream, 'init', '-b', 'main')
            git(upstream, 'config', 'user.name', 'Fixture')
            git(upstream, 'config', 'user.email', 'fixture@example.invalid')
            skill = upstream/'skills/ld-codestyle-online'
            skill.mkdir(parents=True)
            (skill/'SKILL.md').write_text('fixture v1')
            git(upstream, 'add', '.')
            git(upstream, 'commit', '-m', 'fixture v1')
            git(base, 'clone', str(upstream), str(installed))
            git(installed, 'remote', 'set-url', 'origin', 'https://github.com/LastDreamTeam/LDCodeStyleAgentSkill.git')
            (skill/'SKILL.md').write_text('fixture v2')
            git(upstream, 'add', '.')
            git(upstream, 'commit', '-m', 'fixture v2')
            def runner(args, **kwargs):
                args = list(args)
                if 'fetch' in args:
                    args[args.index('origin')] = str(upstream)
                return module.run(args, **kwargs)
            target = installed/'skills/ld-codestyle-online'
            module.update_git(target, runner=runner)
            self.assertEqual((target/'SKILL.md').read_text(), 'fixture v2')
            (target/'SKILL.md').write_text('human local edit')
            with self.assertRaisesRegex(ValueError, 'local edits'):
                module.update_git(target, runner=runner)
            self.assertEqual((target/'SKILL.md').read_text(), 'human local edit')
            (target/'SKILL.md').write_text('fixture v2')
            (installed/'.git/info/exclude').write_text('private.local\n')
            (installed/'private.local').write_text('local must survive')
            (upstream/'private.local').write_text('upstream conflicting file')
            git(upstream, 'add', '.')
            git(upstream, 'commit', '-m', 'fixture ignored conflict')
            with self.assertRaises(ValueError):
                module.update_git(target, runner=runner)
            self.assertEqual((installed/'private.local').read_text(), 'local must survive')

if __name__ == '__main__':
    unittest.main()
