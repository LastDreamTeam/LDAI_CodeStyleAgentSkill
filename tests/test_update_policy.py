# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Consent policy is independent from frequency, idleness and native safety gates.
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

SCRIPT = Path(__file__).resolve().parents[1]/'skills/ld-codestyle-online/scripts/maintain.py'
spec = importlib.util.spec_from_file_location('policy', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class UpdatePolicyTests(unittest.TestCase):
    def test_default_and_force_check_never_authorize_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill, data = Path(tmp)/'skill', Path(tmp)/'data'
            (skill/'assets').mkdir(parents=True)
            data.mkdir()
            manifest = skill/'assets/version.json'
            m.save_json(manifest, {'version': '0.1.0'})
            fetch = Mock(return_value={'name': m.NAME, 'version': '0.2.0'})
            def install(*_):
                m.save_json(manifest, {'version': '0.2.0'})
                return {'backend': 'test-double'}
            updater = Mock(side_effect=install)
            result = m.synchronize(skill, data, m.DEFAULTS, idle=True, force=True,
                                   fetch=fetch, updater=updater)
            self.assertEqual(result['status'], 'update_confirmation_required')
            updater.assert_not_called()
            self.assertEqual(m.load_json(manifest, {})['version'], '0.1.0')
            self.assertNotIn('last_update_attempt_at', result['state'])
            again = m.synchronize(skill, data, m.DEFAULTS, idle=True,
                                  fetch=fetch, updater=updater)
            self.assertEqual(again['status'], 'not_due')
            self.assertEqual(fetch.call_count, 1)
            updater.assert_not_called()

    def test_one_time_approval_keeps_auto_off_and_still_requires_idle(self):
        import inspect
        self.assertIn('approved', inspect.signature(m.synchronize).parameters,
                      'A one-time approval must not require enabling automatic updates')
        with tempfile.TemporaryDirectory() as tmp:
            skill, data = Path(tmp)/'skill', Path(tmp)/'data'
            (skill/'assets').mkdir(parents=True)
            data.mkdir()
            manifest = skill/'assets/version.json'
            m.save_json(manifest, {'version': '0.1.0'})
            fetch = Mock(return_value={'name': m.NAME, 'version': '0.2.0'})
            def install(*_):
                m.save_json(manifest, {'version': '0.2.0'})
                return {'backend': 'test-double'}
            updater = Mock(side_effect=install)
            config = dict(m.DEFAULTS)
            result = m.synchronize(skill, data, config, idle=False, approved=True,
                                   fetch=fetch, updater=updater)
            self.assertEqual(result['status'], 'deferred_until_idle')
            updater.assert_not_called()
            result = m.synchronize(skill, data, config, idle=True, approved=True,
                                   fetch=fetch, updater=updater)
            self.assertEqual(result['status'], 'updated')
            self.assertIs(config['auto_update'], False)
            fetch.return_value = {'name': m.NAME, 'version': '0.3.0'}
            result = m.synchronize(skill, data, config, idle=True, force=True,
                                   fetch=fetch, updater=updater)
            self.assertEqual(result['status'], 'update_confirmation_required')
            self.assertEqual(updater.call_count, 1)

    def test_enabled_auto_update_does_not_turn_check_into_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill, data = Path(tmp)/'skill', Path(tmp)/'data'
            (skill/'assets').mkdir(parents=True)
            data.mkdir()
            manifest = skill/'assets/version.json'
            m.save_json(manifest, {'version': '0.1.0'})
            fetch = Mock(return_value={'name': m.NAME, 'version': '0.2.0'})
            config = dict(m.DEFAULTS, auto_update=True)
            result = m.check(data, config, '0.1.0', force=True, fetch=fetch)
            self.assertEqual(result['status'], 'update_available')
            self.assertEqual(m.load_json(manifest, {})['version'], '0.1.0')
            def install(*_):
                m.save_json(manifest, {'version': '0.2.0'})
                return {'backend': 'test-double'}
            updater = Mock(side_effect=install)
            result = m.synchronize(skill, data, config, idle=True, fetch=fetch, updater=updater)
            self.assertEqual(result['status'], 'updated')
            self.assertEqual(updater.call_count, 1)
            self.assertEqual(fetch.call_count, 1)


if __name__ == '__main__':
    unittest.main()
