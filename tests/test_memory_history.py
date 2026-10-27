# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 使用隔离的真实 SQLite 验证精选历史，不读取任何真实项目或会话。"""
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/ld-codestyle-online/scripts/memory_history.py'


class MemoryHistoryTests(unittest.TestCase):
    """OpenAI: 每项测试使用独立责任区，避免污染共享历史。"""

    def setUp(self):
        """OpenAI: 建立合成 README 与 Agentic；缺实现以明确断言失败。"""
        self.assertTrue(SCRIPT.exists(), '缺少可运行的区域历史工具')
        spec = importlib.util.spec_from_file_location('memory_history', SCRIPT)
        assert spec is not None and spec.loader is not None
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'README.md').write_text('# 合成音频区域', encoding='utf-8')
        self.area = self.root / 'Agentic'
        self.area.mkdir()
        self.module.initialize(self.area, '../README.md', 'audio', '音频模块；不含账户与其他区域', 'private')

    def record(self, **changes):
        """OpenAI: 返回仅供测试的有来源原话，调用者可覆盖字段测试边界。"""
        data = dict(id='u-1', kind='user', scope='audio', title='播放要求',
                    content='播放时不要重建对象；停止不代表删除。', source='synthetic:request-1',
                    occurred_at='2026-01-01', related_paths=['Scripts/Player.cs'],
                    relevance='约束本区域播放生命周期', status='confirmed', evidence=[],
                    supersedes=None, redacted=False)
        data.update(changes)
        return data

    def test_selective_record_roundtrip_and_chinese_search(self):
        """OpenAI: 原话完整读回，重复ID幂等，中文子串检索不把全文注入列表。"""
        original = self.record()
        first = self.module.append_record(self.area, original, reviewed=True)
        again = self.module.append_record(self.area, original, reviewed=True)
        self.assertEqual(first['sha256'], again['sha256'])
        self.assertEqual(self.module.read_record(self.area, 'u-1')['record'], original)
        hits = self.module.search_records(self.area, '不要重建', limit=5, offset=0)
        self.assertEqual([item['id'] for item in hits['items']], ['u-1'])
        self.assertNotIn('content', hits['items'][0])
        self.assertFalse(hits['has_more'])
        self.assertEqual(self.module.verify_history(self.area)['records'], 1)


    def test_selection_rejects_unverified_outside_scope_or_conflicting_records(self):
        """OpenAI: 不因有数据库就存全部对话，错误载荷不得污染已存记录。"""
        for data in (self.record(scope='other'), self.record(kind='chat'),
                     self.record(source=''), self.record(related_paths=['../secret']),
                     self.record(kind='debug', status='proposed'),
                     self.record(kind='debug', status='verified', evidence=[])):
            with self.subTest(data=data), self.assertRaises(ValueError):
                self.module.append_record(self.area, data, reviewed=True)
        self.module.append_record(self.area, self.record(), reviewed=True)
        with self.assertRaises(ValueError):
            self.module.append_record(self.area, self.record(content='覆盖旧原话'), reviewed=True)
        self.assertEqual(self.module.verify_history(self.area)['records'], 1)

    def test_summary_limits_and_archive_first_preserve_original_on_failure(self):
        """OpenAI: 先归档再压缩；超额或旧hash漂移不覆盖摘要。"""
        target = self.area / 'USER.md'
        old = '# 原摘要\n播放时不要重建对象；停止不代表删除。\n'
        # OpenAI: hash绑定准确字节；避免Windows写文本时自动改为CRLF导致夹具失真。
        target.write_bytes(old.encode('utf-8'))
        self.module.append_record(self.area, self.record(), reviewed=True)
        before = self.module.digest(old)
        with self.assertRaises(ValueError):
            self.module.replace_summary(self.area, 'USER.md', '中' * 4001, before, ['u-1'], reviewed=True)
        with self.assertRaises(ValueError):
            self.module.replace_summary(self.area, 'USER.md', '# 新摘要', '0' * 64, ['u-1'], reviewed=True)
        self.assertEqual(target.read_text(encoding='utf-8'), old)
        result = self.module.replace_summary(self.area, 'USER.md', '# 当前要求\n保留对象；停止≠删除。 [u-1]\n', before, ['u-1'], reviewed=True)
        self.assertEqual(result['old_sha256'], before)
        self.assertIn('u-1', target.read_text(encoding='utf-8'))
        snapshot = self.module.read_snapshot(self.area, result['snapshot_id'])
        self.assertEqual(snapshot['content'], old)
        self.assertEqual(snapshot['records'], ['u-1'])
        limits = self.module.summary_status(self.area)
        self.assertEqual(limits['limits']['USER.md'], 4000)
        self.assertFalse(limits['files']['USER.md']['over_limit'])


    def test_export_import_is_complete_atomic_and_detects_corruption(self):
        """OpenAI: 跨机只交换校验后的精选载荷；整批冲突回滚而非覆盖历史。"""
        self.module.append_record(self.area, self.record(), reviewed=True)
        original = '# 原摘要\r\n停止≠删除\r\n'
        (self.area / 'USER.md').write_bytes(original.encode('utf-8'))
        change = self.module.replace_summary(self.area, 'USER.md', '# 当前\n停止≠删除 [u-1]',
                                             self.module.digest(original), ['u-1'], reviewed=True)
        bundle = self.module.export_history(self.area, reviewed=True)
        other = self.root / 'copy' / 'Agentic'
        other.mkdir(parents=True)
        (other.parent / 'README.md').write_text('# 合成音频区域', encoding='utf-8')
        self.module.initialize(other, '../README.md', 'audio', '音频模块；不含账户与其他区域', 'private')
        self.module.import_history(other, bundle, reviewed=True)
        self.assertEqual(self.module.export_history(other, reviewed=True), bundle)
        self.assertEqual(self.module.read_snapshot(other, change['snapshot_id'])['content'], original)
        self.module.append_record(other, self.record(id='u-2', content='另一台机器的不同原话'), reviewed=True)
        self.module.append_record(self.area, self.record(id='u-2', content='原话修订'), reviewed=True)
        before = self.module.export_history(other, reviewed=True)
        with self.assertRaises(ValueError):
            self.module.import_history(other, self.module.export_history(self.area, reviewed=True), reviewed=True)
        self.assertEqual(self.module.export_history(other, reviewed=True), before)
        with sqlite3.connect(self.area / 'history.sqlite3') as db:
            db.execute('UPDATE records SET payload=? WHERE id=?', ('{}', 'u-1'))
        with self.assertRaises(ValueError):
            self.module.verify_history(self.area)

    def test_real_cli_and_write_failure_preserve_old_summary(self):
        """OpenAI: 实跑公开命令；模拟磁盘替换失败时旧文和已存快照均可恢复。"""
        self.module.append_record(self.area, self.record(), reviewed=True)
        target = self.area / 'USER.md'
        target.write_text('原文', encoding='utf-8')
        with mock.patch.object(self.module.os, 'replace', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):
                self.module.replace_summary(self.area, 'USER.md', '摘要 [u-1]',
                                            self.module.digest('原文'), ['u-1'], reviewed=True)
        self.assertEqual(target.read_text(encoding='utf-8'), '原文')
        self.assertFalse((self.area / '.history-summary.lock').exists())
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--area', str(self.area),
                                 'search', '不要重建', '--limit', '1'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['items'][0]['id'], 'u-1')
        missing = subprocess.run([sys.executable, '-B', str(SCRIPT), '--area', str(self.area),
                                  'get', 'no-such-id'], capture_output=True, text=True)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn('error', json.loads(missing.stdout))


    def test_memory_only_compaction_and_readonly_missing_database(self):
        """OpenAI: 一般模块知识不伪造用户/debug来源；缺库查询不创建文件。"""
        target = self.area / 'MEMORY.md'
        target.write_text('模块使用集中入口。', encoding='utf-8')
        result = self.module.replace_summary(self.area, 'MEMORY.md', '集中入口。',
                                             self.module.digest('模块使用集中入口。'), [], reviewed=True)
        self.assertEqual(self.module.read_snapshot(self.area, result['snapshot_id'])['records'], [])
        empty = self.root / 'empty' / 'Agentic'
        empty.mkdir(parents=True)
        with self.assertRaises(ValueError):
            self.module.search_records(empty, '任何词')
        self.assertFalse((empty / 'history.sqlite3').exists())
        for bad in (0, -1, True, 100001):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.module.configure_limits(self.area, {'USER.md': bad, 'MEMORY.md': 6000, 'DEBUG.md': 6000})
        self.module.configure_limits(self.area, {'USER.md': 3000, 'MEMORY.md': 5000, 'DEBUG.md': 5000})
        self.assertEqual(self.module.summary_status(self.area)['limits']['USER.md'], 3000)

    def test_documentation_and_templates_expose_limits_and_history(self):
        """OpenAI: 直接打开任一模板可发现有限摘要与原文检索入口。"""
        skill = SCRIPT.parent.parent
        spec = (skill / 'references/memory-history.md').read_text(encoding='utf-8')
        for term in ('history.sqlite3', '完整', '4000', '6000', '80%', '不全库注入', '不无限分卷', '先归档', '单writer'):
            self.assertIn(term, spec)
        for kind in ('user', 'memory', 'debug', 'readme'):
            text = (skill / f'templates/module-{kind}.md').read_text(encoding='utf-8')
            header = text.split('\n## ', 1)[0]
            with self.subTest(kind=kind):
                for term in ('history.sqlite3', 'Unicode字符', 'scope', '内容压缩', '不全库注入'):
                    self.assertIn(term, header)
        for kind in ('user', 'debug'):
            data = json.loads((skill / f'templates/history-{kind}.example.json').read_text(encoding='utf-8'))
            self.module.validate_record(data, {'scope': 'example-audio'})
            self.assertIn('合成', data['content'])


if __name__ == '__main__':
    unittest.main()
