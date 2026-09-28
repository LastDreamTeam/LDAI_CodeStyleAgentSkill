# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Safety and persistence regression checks use isolated temporary directories.
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1]/'skills/ld-codestyle-online/scripts/maintain.py'
spec = importlib.util.spec_from_file_location('maintain', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class Guards(unittest.TestCase):
    def test_corrupt_config_is_not_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'config.json'
            p.write_text('{broken')
            with self.assertRaises(ValueError):
                m.config_at(Path(tmp))
            self.assertEqual(p.read_text(), '{broken')

    def test_unknown_schema_is_not_migrated(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'config.json'
            p.write_text(json.dumps(dict(m.DEFAULTS, schema_version=99)))
            with self.assertRaises(ValueError):
                m.config_at(Path(tmp))

    def test_lock_refuses_second_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            with m.locked(Path(tmp)):
                with self.assertRaises(FileExistsError):
                    with m.locked(Path(tmp)):
                        self.fail('two writers acquired same lock')
            self.assertFalse((Path(tmp)/'maintenance.lock').exists())

    def test_failed_check_is_not_success_and_is_throttled(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            fetch = Mock(side_effect=OSError('offline'))
            with self.assertRaises(OSError):
                m.check(directory, m.DEFAULTS, '0.1.0', fetch=fetch, now=1000)
            state = m.load_json(directory/'state.json', {})
            self.assertNotIn('last_success_at', state)
            self.assertEqual(state['last_error'], 'OSError')
            self.assertEqual(m.check(directory, m.DEFAULTS, '0.1.0', fetch=fetch, now=1100)['status'], 'not_due')
            self.assertEqual(fetch.call_count, 1)

    def test_wrong_identity_and_version_are_rejected(self):
        for manifest in ({'name': 'other', 'version': '0.2.0'},
                         {'name': m.NAME, 'version': '../malformed'}):
            with self.subTest(manifest=manifest), tempfile.TemporaryDirectory() as tmp:
                with self.assertRaises(ValueError):
                    m.check(Path(tmp), m.DEFAULTS, '0.1.0', fetch=lambda: manifest)

    def test_detected_hermes_state_is_outside_replaceable_skill(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(m.os.environ, {}, clear=True):
            home = Path(tmp)
            (home/'skills/.hub').mkdir(parents=True)
            (home/'skills/.hub/lock.json').write_text('{}')
            skill = home/'skills'/m.NAME
            skill.mkdir()
            directory = m.data_dir(skill)
            self.assertTrue(directory.is_relative_to(home/'skill-data'))
            self.assertFalse(directory.is_relative_to(skill))

    def test_backup_retains_three_and_excludes_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'SKILL.md').write_text('fixture')
            data = root/'.ld-codestyle-data/schema-1'
            data.mkdir(parents=True)
            (data/'config.json').write_text('{}')
            for _ in range(4):
                m.backup_skill(root, data)
            backups = list((data/'backups').glob('*.zip'))
            self.assertEqual(len(backups), 3)
            import zipfile
            for archive in backups:
                with zipfile.ZipFile(archive) as z:
                    self.assertEqual(z.namelist(), ['SKILL.md'])

    def test_busy_sync_does_not_update_and_idle_reuses_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp)/'skill'
            data = Path(tmp)/'data'
            (skill/'assets').mkdir(parents=True)
            data.mkdir()
            manifest = skill/'assets/version.json'
            m.save_json(manifest, {'version': '0.1.0'})
            fetch = Mock(return_value={'name': m.NAME, 'version': '0.2.0'})
            def install(*_):
                m.save_json(manifest, {'version': '0.2.0'})
                return {'backend': 'test-double'}
            updater = Mock(side_effect=install)
            result = m.synchronize(skill, data, m.DEFAULTS, idle=False, fetch=fetch, updater=updater)
            self.assertEqual(result['status'], 'deferred_until_idle')
            updater.assert_not_called()
            result = m.synchronize(skill, data, m.DEFAULTS, idle=True, fetch=fetch, updater=updater)
            self.assertEqual(result['status'], 'updated')
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(updater.call_count, 1)

    def test_exit_zero_without_version_change_is_not_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill, data = Path(tmp)/'skill', Path(tmp)/'data'
            (skill/'assets').mkdir(parents=True)
            data.mkdir()
            m.save_json(skill/'assets/version.json', {'version': '0.1.0'})
            with self.assertRaisesRegex(ValueError, 'did not install'):
                m.synchronize(skill, data, m.DEFAULTS, idle=True,
                              fetch=lambda: {'name': m.NAME, 'version': '0.2.0'},
                              updater=lambda *_: {'exit_code': 0})
            state = m.load_json(data/'state.json', {})
            self.assertNotIn('last_updated_at', state)
            self.assertEqual(state['observed_version'], '0.1.0')
            self.assertEqual(state['last_update_error'], 'ValueError')

    def test_invalid_git_install_does_not_rotate_backups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill = root/'repo/skills'/m.NAME
            skill.mkdir(parents=True)
            (root/'repo/.git').mkdir()
            data = root/'data'
            data.mkdir()
            with patch.object(m, 'backup_skill') as backup:
                with self.assertRaises(ValueError):
                    m.apply_update(skill, data)
                backup.assert_not_called()

if __name__ == '__main__':
    unittest.main()
