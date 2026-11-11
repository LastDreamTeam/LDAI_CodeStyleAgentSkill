# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Daily maintenance keeps update consent, idleness and backend safety independent.
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

SCRIPT = Path(__file__).resolve().parents[1]/'skills/ld-codestyle-online/scripts/maintain.py'
spec = importlib.util.spec_from_file_location('policy', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class UpdatePolicyTests(unittest.TestCase):
    def fixture(self, root):
        """OpenAI: 创建隔离版本清单和数据目录，并返回可观察的安装后端。"""
        skill, data = root/'skill', root/'data'
        (skill/'assets').mkdir(parents=True)
        data.mkdir()
        manifest = skill/'assets/version.json'
        m.save_json(manifest, {'version': '0.1.0'})

        def install(*_):
            """OpenAI: 模拟后端成功写入新版本，供真实维护协调逻辑核验。"""
            m.save_json(manifest, {'version': '0.2.0'})
            return {'backend': 'test-double'}

        return skill, data, manifest, Mock(side_effect=install)

    def test_default_sync_updates_once_but_check_only_reports(self):
        """OpenAI: 默认同步自动更新，单独check即使force也不安装。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill, data, manifest, updater = self.fixture(Path(tmp))
            fetch = Mock(return_value={'name': m.NAME, 'version': '0.2.0'})
            result = m.check(data, m.DEFAULTS, '0.1.0', force=True, fetch=fetch, now=100000)
            self.assertEqual(result['status'], 'update_available')
            self.assertEqual(m.load_json(manifest, {})['version'], '0.1.0')
            self.assertIn('version_behind', result['health']['reasons'])
            result = m.synchronize(skill, data, m.DEFAULTS, idle=True, force=True,
                                   fetch=fetch, updater=updater, now=100001)
            self.assertEqual(result['status'], 'updated')
            self.assertEqual(result['health']['status'], 'healthy')
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(updater.call_count, 1)
            self.assertEqual(m.load_json(data/'health.json', {})['installed_version'], '0.2.0')

    def test_disabled_updates_preserve_preference_and_prompt_only_once(self):
        """OpenAI: 显式关闭始终保留，同日缓存不会反复询问或被force改成同意。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill, data, manifest, updater = self.fixture(Path(tmp))
            fetch = Mock(return_value={'name': m.NAME, 'version': '0.2.0'})
            config = dict(m.DEFAULTS, auto_update=False)
            result = m.synchronize(skill, data, config, idle=True, force=True,
                                   fetch=fetch, updater=updater, now=100000)
            self.assertEqual(result['status'], 'update_confirmation_required')
            self.assertIn('auto_update_disabled', result['health']['reasons'])
            self.assertIn('version_behind', result['health']['reasons'])
            result = m.synchronize(skill, data, config, idle=True, force=True,
                                   fetch=fetch, updater=updater, now=100001)
            self.assertEqual(result['status'], 'not_due')
            self.assertIs(config['auto_update'], False)
            updater.assert_not_called()
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(m.load_json(manifest, {})['version'], '0.1.0')

    def test_one_time_approval_keeps_auto_off_and_still_requires_idle(self):
        """OpenAI: 单次同意仅影响本次安装，空档条件与长期关闭偏好不变。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill, data, _, updater = self.fixture(Path(tmp))
            fetch = Mock(return_value={'name': m.NAME, 'version': '0.2.0'})
            config = dict(m.DEFAULTS, auto_update=False)
            result = m.synchronize(skill, data, config, idle=False, approved=True,
                                   fetch=fetch, updater=updater, now=100000)
            self.assertEqual(result['status'], 'deferred_until_idle')
            updater.assert_not_called()
            result = m.synchronize(skill, data, config, idle=True, approved=True,
                                   fetch=fetch, updater=updater, now=100001)
            self.assertEqual(result['status'], 'updated')
            self.assertIs(config['auto_update'], False)
            self.assertTrue(result['health']['dirty'])
            self.assertEqual(result['health']['reasons'], ['auto_update_disabled'])
            # OpenAI: A later release needs its own approval; the old approved call does not grant a preference.
            fetch.return_value = {'name': m.NAME, 'version': '0.3.0'}
            result = m.synchronize(skill, data, config, idle=True, force=True,
                                   fetch=fetch, updater=updater, now=186400)
            self.assertEqual(result['status'], 'update_confirmation_required')
            self.assertEqual(updater.call_count, 1)

    def test_cached_new_release_can_update_after_busy_call_same_day(self):
        """OpenAI: 首次使用仍忙时只检查，同日空档直接复用新鲜缓存更新。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill, data, _, updater = self.fixture(Path(tmp))
            fetch = Mock(return_value={'name': m.NAME, 'version': '0.2.0'})
            result = m.synchronize(skill, data, m.DEFAULTS, idle=False,
                                   fetch=fetch, updater=updater, now=100000)
            self.assertEqual(result['status'], 'deferred_until_idle')
            updater.assert_not_called()
            result = m.synchronize(skill, data, m.DEFAULTS, idle=True,
                                   fetch=fetch, updater=updater, now=100060)
            self.assertEqual(result['status'], 'updated')
            self.assertFalse(result['network_checked'])
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(updater.call_count, 1)

    def test_failed_update_is_daily_throttled_even_with_force(self):
        """OpenAI: 后端失败也消耗当日尝试，force和时钟倒退不能密集重试。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill, data, _, updater = self.fixture(Path(tmp))
            updater.side_effect = OSError('offline backend')
            fetch = Mock(return_value={'name': m.NAME, 'version': '0.2.0'})
            with self.assertRaises(OSError):
                m.synchronize(skill, data, m.DEFAULTS, idle=True,
                              fetch=fetch, updater=updater, now=100000)
            self.assertIn('update_failed', m.load_json(data/'health.json', {})['reasons'])
            for now in (100060, 186399):
                result = m.synchronize(skill, data, m.DEFAULTS, idle=True, force=True,
                                       fetch=fetch, updater=updater, now=now)
                self.assertEqual(result['status'], 'update_retry_not_due')
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(updater.call_count, 1)
            with self.assertRaises(OSError):
                m.synchronize(skill, data, m.DEFAULTS, idle=True, force=True,
                              fetch=fetch, updater=updater, now=186400)
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual(updater.call_count, 2)

    def test_failed_check_is_recorded_before_network_and_cannot_retry(self):
        """OpenAI: 断网前状态已标为不健康，失败保留时间并拒绝force重查。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill, data, _, updater = self.fixture(Path(tmp))

            def fail_fetch():
                """OpenAI: 在联网边界观察落盘状态，再抛出确定的离线错误。"""
                self.assertEqual(m.load_json(data/'state.json', {})['last_attempt_at'], 100000)
                self.assertTrue(m.load_json(data/'health.json', {})['dirty'])
                raise OSError('offline')

            fetch = Mock(side_effect=fail_fetch)
            with self.assertRaises(OSError):
                m.synchronize(skill, data, m.DEFAULTS, idle=True,
                              fetch=fetch, updater=updater, now=100000)
            for now in (100001, 186399, 99999):
                result = m.synchronize(skill, data, m.DEFAULTS, idle=True, force=True,
                                       fetch=fetch, updater=updater, now=now)
                self.assertEqual(result['status'], 'not_due')
                self.assertTrue(result['health']['dirty'])
            self.assertEqual(fetch.call_count, 1)
            updater.assert_not_called()
            self.assertNotIn('last_success_at', m.load_json(data/'state.json', {}))

    def test_partial_update_failure_reports_observed_disk_version(self):
        """OpenAI: 后端部分写入后失败仍报告磁盘实际版本并保持失败脏状态。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill, data, manifest, updater = self.fixture(Path(tmp))

            def partial_update(*_):
                """OpenAI: 模拟先写新版本后失败，验证不能据版本相等冒称安装健康。"""
                m.save_json(manifest, {'version': '0.2.0'})
                raise OSError('partial update')

            updater.side_effect = partial_update
            with self.assertRaises(OSError):
                m.synchronize(skill, data, m.DEFAULTS, idle=True,
                              fetch=lambda: {'name': m.NAME, 'version': '0.2.0'},
                              updater=updater, now=100000)
            health = m.load_json(data/'health.json', {})
            self.assertEqual(health['installed_version'], '0.2.0')
            self.assertTrue(health['dirty'])
            self.assertIn('update_failed', health['reasons'])
            self.assertNotIn('version_behind', health['reasons'])


if __name__ == '__main__':
    unittest.main()
