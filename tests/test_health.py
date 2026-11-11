# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: Exercise offline health and opt-in gates through real CLI processes and persisted state."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1]/'skills/ld-codestyle-online/scripts/maintain.py'
spec = importlib.util.spec_from_file_location('health_maintenance', SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

# OpenAI: Subprocesses still parse the actual CLI; only external network/update side effects are replaced.
CLI_DRIVER = '''
import importlib.util
import json
from pathlib import Path
import sys
script, mode, event_path = sys.argv[1:4]
sys.argv = [script] + sys.argv[4:]
spec = importlib.util.spec_from_file_location('cli_under_test', script)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
def record(event):
    """OpenAI: Persist external-effect calls so the parent observes attempts across CLI invocations."""
    with Path(event_path).open('a', encoding='utf-8') as out:
        out.write(event + '\\n')
def fetch():
    """OpenAI: Replace a bounded manifest request with a deterministic success or network failure."""
    record('fetch')
    if mode == 'offline':
        raise OSError('fixture network unavailable')
    if mode == 'no-network':
        raise AssertionError('offline operation unexpectedly used network')
    return {'name': m.NAME, 'version': '0.2.0'}
def update(skill, directory):
    """OpenAI: Replace backend downloads while preserving installed-version verification and errors."""
    record('update')
    health = m.load_json(directory / 'health.json', {})
    assert health['dirty'] and health['update_error'] == 'update_in_progress'
    m.save_json(skill / 'assets/version.json', {'version': '0.2.0'})
    if mode == 'partial-failure':
        raise OSError('fixture updater changed files before failure')
    return {'backend': 'fixture'}
m.fetch_version = fetch
m.apply_update = update
raise SystemExit(m.main())
'''


class HealthTests(unittest.TestCase):
    def fixture(self, root, installed='0.2.0', latest='0.2.0'):
        """OpenAI: 创建真实CLI可读取的临时安装、配置及新鲜已验证版本状态。"""
        skill, data_root = root/'skill', root/'data'
        (skill/'assets').mkdir(parents=True)
        m.save_json(skill/'assets/version.json', {'name': m.NAME, 'version': installed})
        directory = m.data_dir(skill, data_root)
        directory.mkdir(parents=True)
        m.save_json(directory/'config.json', dict(m.DEFAULTS))
        now = time.time()
        m.save_json(directory/'state.json', {'schema_version': 1, 'latest_version': latest,
                                            'last_attempt_at': now, 'last_success_at': now,
                                            'last_error': None})
        return skill, data_root, directory

    def invoke(self, skill, data_root, *args, mode=None):
        """OpenAI: 运行独立CLI进程；可选替换网络边界但保持参数解析、状态与退出码。"""
        prefix = [sys.executable, '-B', str(SCRIPT)]
        if mode is not None:
            prefix = [sys.executable, '-B', '-c', CLI_DRIVER, str(SCRIPT), mode,
                      str(data_root.parent/'events.txt')]
        return subprocess.run(prefix + ['--skill-root', str(skill), '--data-root', str(data_root), *args],
                              capture_output=True, text=True, encoding='utf-8', timeout=15,
                              env=dict(os.environ, PYTHONIOENCODING='ascii'))

    def decode(self, process, expected=0):
        """OpenAI: 验证真实退出码与ASCII安全JSON协议后返回响应对象。"""
        self.assertEqual(process.returncode, expected, process.stdout + process.stderr)
        self.assertTrue(process.stdout.isascii())
        return json.loads(process.stdout)

    def test_health_is_offline_recomputed_and_persisted(self):
        """OpenAI: 离线CLI重算标准健康JSON，不相信旧快照或旧observed_version。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill, data_root, directory = self.fixture(root)
            m.save_json(directory/'health.json', {'status': 'dirty', 'dirty': True})
            state = m.load_json(directory/'state.json', {})
            state['installed_version'] = '0.1.0'
            state['observed_version'] = '0.1.0'
            m.save_json(directory/'state.json', state)
            before = (directory/'state.json').read_bytes()
            result = self.decode(self.invoke(skill, data_root, 'health', mode='no-network'))
            self.assertEqual(result['status'], 'healthy')
            self.assertFalse(result['dirty'])
            self.assertEqual(result['schema_version'], 1)
            self.assertEqual(result['installed_version'], '0.2.0')
            self.assertEqual(result['latest_version'], '0.2.0')
            self.assertEqual(result['freshness'], 'fresh')
            self.assertIs(result['auto_update'], True)
            self.assertEqual(result['reasons'], [])
            self.assertIsNotNone(result['checked_at'])
            self.assertEqual(result['expires_at'] - result['checked_at'], 86400)
            persisted = m.load_json(directory/'health.json', {})
            self.assertEqual(persisted, {key: value for key, value in result.items() if key != 'gate_exit_code'})
            self.assertEqual((directory/'state.json').read_bytes(), before)
            self.assertFalse((root/'events.txt').exists())
            # OpenAI: A real CLI call after a local rollback must report disk truth, not the prior green file.
            m.save_json(skill/'assets/version.json', {'version': '0.1.0'})
            result = self.decode(self.invoke(skill, data_root, 'health'))
            self.assertIn('version_behind', result['reasons'])
            self.assertTrue(result['dirty'])

    def test_disabled_or_behind_each_independently_makes_dirty(self):
        """OpenAI: 更新关闭与版本落后单独足以标脏，普通health不全局封禁。"""
        for disabled, installed in ((True, '0.2.0'), (False, '0.1.0'), (True, '0.1.0')):
            with self.subTest(disabled=disabled, installed=installed), tempfile.TemporaryDirectory() as tmp:
                skill, data_root, directory = self.fixture(Path(tmp), installed=installed)
                m.save_json(directory/'config.json', dict(m.DEFAULTS, auto_update=not disabled))
                result = self.decode(self.invoke(skill, data_root, 'health'))
                self.assertTrue(result['dirty'])
                self.assertEqual('auto_update_disabled' in result['reasons'], disabled)
                self.assertEqual('version_behind' in result['reasons'], installed == '0.1.0')
                self.decode(self.invoke(skill, data_root, 'health', '--require-healthy'), 3)

    def test_optional_version_gates_have_distinct_exit_codes(self):
        """OpenAI: 依赖方可独立选版本或健康门禁，组合时版本不满足优先返回4。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill, data_root, directory = self.fixture(Path(tmp))
            self.decode(self.invoke(skill, data_root, 'health', '--min-version', '0.1.9', '--require-healthy'))
            self.decode(self.invoke(skill, data_root, 'health', '--require-version', '0.2.0'))
            self.decode(self.invoke(skill, data_root, 'health', '--min-version', '0.2.1'), 4)
            self.decode(self.invoke(skill, data_root, 'health', '--require-version', '0.1.0'), 4)
            m.save_json(directory/'config.json', dict(m.DEFAULTS, auto_update=False))
            self.decode(self.invoke(skill, data_root, 'health', '--min-version', '0.1.0'))
            self.decode(self.invoke(skill, data_root, 'health', '--require-healthy'), 3)
            self.decode(self.invoke(skill, data_root, 'health', '--min-version', '0.3.0', '--require-healthy'), 4)
            self.decode(self.invoke(skill, data_root, 'health', '--min-version', 'invalid'), 1)

    def test_unknown_or_missing_manifest_never_passes_healthy_or_version_gate(self):
        """OpenAI: 尚未安装的版本信息保持unknown，show仍兼容空安装目录。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill, data_root = root/'empty', root/'data'
            skill.mkdir()
            shown = self.decode(self.invoke(skill, data_root, 'show'))
            self.assertEqual(shown['health']['status'], 'unknown')
            result = self.decode(self.invoke(skill, data_root, 'health'))
            self.assertTrue(result['dirty'])
            self.assertIsNone(result['installed_version'])
            self.assertIsNone(result['latest_version'])
            self.assertEqual(result['freshness'], 'unknown')
            self.decode(self.invoke(skill, data_root, 'health', '--require-healthy'), 3)
            self.decode(self.invoke(skill, data_root, 'health', '--min-version', '0.1.0'), 4)

    def test_stale_and_interrupted_or_failed_checks_and_updates_fail_closed(self):
        """OpenAI: 检查过期、失败或中断不能被较早的成功结果遮蔽。"""
        variants = (
            ({'last_attempt_at': 1000, 'last_success_at': 1000}, 'check_stale'),
            ({'last_error': 'OSError'}, 'check_failed'),
            ({'last_error': 'check_in_progress'}, 'check_failed'),
            ({'last_update_error': 'OSError'}, 'update_failed'),
            ({'last_update_error': 'update_in_progress'}, 'update_failed'),
            ({'last_update_attempt_at': time.time()}, 'update_incomplete'),
            ({'last_attempt_at': time.time() + 600}, 'clock_rollback'),
        )
        for changes, expected in variants:
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as tmp:
                skill, data_root, directory = self.fixture(Path(tmp))
                state = m.load_json(directory/'state.json', {})
                state.update(changes)
                m.save_json(directory/'state.json', state)
                result = self.decode(self.invoke(skill, data_root, 'health', '--require-healthy'), 3)
                self.assertIn(expected, result['reasons'])
                self.assertTrue(result['dirty'])
                self.assertNotEqual(result['status'], 'healthy')

    def test_malformed_state_and_config_are_preserved_and_reported_unknown(self):
        """OpenAI: 损坏配置或非数字时间戳不重置原文件，健康按未知关闭门禁。"""
        corruptions = (
            ('config.json', '{broken', 'config_invalid'),
            ('state.json', '{broken', 'state_invalid'),
            ('state.json', json.dumps({'schema_version': 99}), 'state_invalid'),
            ('state.json', json.dumps({'schema_version': True}), 'state_invalid'),
            ('state.json', '{"schema_version":1,"last_error":NaN}', 'state_invalid'),
            ('state.json', json.dumps({'schema_version': 1, 'last_attempt_at': 'today'}), 'state_invalid'),
            ('state.json', json.dumps({'schema_version': 1, 'last_attempt_at': True}), 'state_invalid'),
            ('state.json', '{"schema_version":1,"last_success_at":NaN}', 'state_invalid'),
        )
        for filename, raw, expected in corruptions:
            with self.subTest(filename=filename, raw=raw), tempfile.TemporaryDirectory() as tmp:
                skill, data_root, directory = self.fixture(Path(tmp))
                target = directory/filename
                target.write_text(raw, encoding='utf-8')
                before = target.read_bytes()
                result = self.decode(self.invoke(skill, data_root, 'health', '--require-healthy'), 3)
                self.assertEqual(result['status'], 'unknown')
                self.assertIn(expected, result['reasons'])
                self.assertTrue(m.load_json(directory/'health.json', {})['dirty'])
                self.assertEqual(target.read_bytes(), before)

    def test_lock_failure_is_standard_unknown_without_overwriting_active_state(self):
        """OpenAI: 健康读取遇持锁者时返回非健康JSON，不抢锁或覆盖旧快照。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill, data_root, directory = self.fixture(Path(tmp))
            self.decode(self.invoke(skill, data_root, 'health'))
            before = (directory/'health.json').read_bytes()
            lock = directory/'maintenance.lock'
            lock.write_text('active writer', encoding='utf-8')
            result = self.decode(self.invoke(skill, data_root, 'health', '--require-healthy'), 1)
            self.assertTrue(result['dirty'])
            self.assertIs(result['health_persisted'], False)
            self.assertIn('health_unavailable', result['reasons'])
            self.assertEqual((directory/'health.json').read_bytes(), before)
            self.assertEqual(lock.read_text(encoding='utf-8'), 'active writer')

    def test_corrupt_state_blocks_force_check_without_network_or_reset(self):
        """OpenAI: 损坏尝试时间不能变成首次检查授权，CLI保留原状态并返回脏健康。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill, data_root, directory = self.fixture(root)
            state_file = directory/'state.json'
            raw = '{"schema_version":1,"last_attempt_at":"invalid"}'
            state_file.write_text(raw, encoding='utf-8')
            result = self.decode(self.invoke(skill, data_root, 'check', '--force', mode='no-network'), 1)
            self.assertIn('state_invalid', result['health']['reasons'])
            self.assertTrue(m.load_json(directory/'health.json', {})['dirty'])
            self.assertEqual(state_file.read_text(encoding='utf-8'), raw)
            self.assertFalse((root/'events.txt').exists())

    def test_cli_check_failure_is_persisted_and_force_cannot_retry(self):
        """OpenAI: 跨进程CLI失败保留尝试时间与脏状态，下一force调用复用缓存。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill, data_root, directory = self.fixture(root, installed='0.1.0')
            m.save_json(directory/'state.json', {'schema_version': 1})
            result = self.decode(self.invoke(skill, data_root, 'check', '--force', mode='offline'), 1)
            self.assertIn('check_failed', result['health']['reasons'])
            state = m.load_json(directory/'state.json', {})
            self.assertIsNotNone(state['last_attempt_at'])
            self.assertNotIn('last_success_at', state)
            result = self.decode(self.invoke(skill, data_root, 'check', '--force', mode='offline'))
            self.assertEqual(result['status'], 'not_due')
            self.assertFalse(result['network_checked'])
            self.assertEqual((root/'events.txt').read_text().splitlines(), ['fetch'])
            self.decode(self.invoke(skill, data_root, 'health', '--require-healthy'), 3)

    def test_cli_cached_check_updates_without_second_check_and_reports_partial_failure(self):
        """OpenAI: 同日缓存可执行后端，部分更新失败的CLI响应与持久健康均准确。"""
        for mode in ('success', 'partial-failure'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                skill, data_root, directory = self.fixture(root, installed='0.1.0')
                m.save_json(directory/'state.json', {'schema_version': 1})
                checked = self.decode(self.invoke(skill, data_root, 'check', mode=mode))
                self.assertEqual(checked['status'], 'update_available')
                result = self.decode(self.invoke(skill, data_root, 'sync', '--idle', '--force', mode=mode),
                                     1 if mode == 'partial-failure' else 0)
                self.assertEqual((root/'events.txt').read_text().splitlines(), ['fetch', 'update'])
                health = m.load_json(directory/'health.json', {})
                self.assertEqual(health['installed_version'], '0.2.0')
                self.assertEqual(health['dirty'], mode == 'partial-failure')
                self.assertEqual(result['health']['dirty'], health['dirty'])
                again = self.decode(self.invoke(skill, data_root, 'sync', '--idle', '--force', mode=mode))
                self.assertEqual(again['status'], 'not_due')
                self.assertEqual((root/'events.txt').read_text().splitlines(), ['fetch', 'update'])


if __name__ == '__main__':
    unittest.main()
