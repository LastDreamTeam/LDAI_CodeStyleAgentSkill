# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 用真实临时库复现快照结构及恢复资料的一致性边界。"""
from contextlib import closing
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/ld-codestyle-online/scripts/memory_history.py'


class HistoryIntegrityTests(unittest.TestCase):
    """OpenAI: 每个用例建立独立源库和目标库，所有记录均为合成数据。"""

    def setUp(self):
        """OpenAI: 初始化同责任区库，生成一条记录和一份真正由工具保存的旧文快照。"""
        spec = importlib.util.spec_from_file_location('history_integrity', SCRIPT)
        assert spec is not None and spec.loader is not None
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.area = self.make_area('source')
        self.target = self.make_area('target')
        record = dict(id='u-1', kind='user', scope='fixture', title='合成要求', content='保留对象。',
                      source='synthetic:test', occurred_at='2026-01-01', related_paths=['Scripts/Foo.cs'],
                      relevance='合成生命周期', status='confirmed', evidence=[], supersedes=None, redacted=False)
        self.module.append_record(self.area, record, reviewed=True)
        self.snapshot = self.module.replace_summary(self.area, 'USER.md', '保留对象。[u-1]',
                                                    self.module.digest(''), ['u-1'], reviewed=True)['snapshot_id']

    def make_area(self, label):
        """OpenAI: 建立明确同scope的隔离目录，不读写实际项目。"""
        area = self.root / label / 'Agentic'
        area.mkdir(parents=True)
        (area.parent / 'README.md').write_text('# 合成区域', encoding='utf-8')
        self.module.initialize(area, '../README.md', 'fixture', '合成区域', 'private')
        return area

    def repack(self, bundle, changes):
        """OpenAI: 重算全部hash以单独检验语义结构，不让字节不匹配提前掩盖缺陷。"""
        result = copy.deepcopy(bundle)
        row = result['snapshots'][0]
        payload = json.loads(row['payload'])
        payload.update(changes)
        row['payload'] = self.module.canonical(payload)
        row['sha256'] = row['id'] = self.module.digest(row['payload'])
        result['sha256'] = self.module.digest(self.module.canonical(
            {key: value for key, value in result.items() if key != 'sha256'}))
        return result

    def test_malformed_snapshots_reject_entire_import(self):
        """OpenAI: 字典来源、无效hash、重复/坏ID或缺引用均拒绝，先导入的记录一起回滚。"""
        bundle = self.module.export_history(self.area, reviewed=True)
        before = self.module.export_history(self.target, reviewed=True)
        for changes in ({'records': {'u-1': 'invalid'}}, {'records': []}, {'records': ['u-1', 'u-1']},
                        {'records': [1]}, {'records': ['bad id']}, {'records': ['missing']},
                        {'new_sha256': 'not-a-sha'}, {'old_sha256': '0' * 64}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self.module.import_history(self.target, self.repack(bundle, changes), reviewed=True)
                self.assertEqual(self.module.export_history(self.target, reviewed=True), before)

    def test_literal_search_uses_decoded_values_before_pagination(self):
        """OpenAI: 引号、反斜杠及真实换行按原文字面匹配，JSON键不命中，分页按命中数计算。"""
        original = self.module.read_record(self.area, 'u-1')['record']
        text = '合成"原话" C:\\Data\n第一行\n第二行'
        for record_id in ('u-2', 'u-3'):
            self.module.append_record(self.area, dict(original, id=record_id, content=text), reviewed=True)
        for query in ('"原话"', 'C:\\Data', '第一行\n第二行'):
            with self.subTest(query=query):
                first = self.module.search_records(self.area, query, limit=1, kind='user', from_date='2026-01-01')
                self.assertEqual([item['id'] for item in first['items']], ['u-2'])
                self.assertTrue(first['has_more'])
                second = self.module.search_records(self.area, query, limit=1, offset=first['next_offset'])
                self.assertEqual([item['id'] for item in second['items']], ['u-3'])
                self.assertFalse(second['has_more'])
        self.assertEqual(self.module.search_records(self.area, 'content')['items'], [])

    def test_search_detects_projection_drift_even_if_filter_would_hide_it(self):
        """OpenAI: 精选库有投影漂移时拒绝结果，不把损坏伪装成零命中。"""
        with closing(sqlite3.connect(self.area / 'history.sqlite3')) as db:
            with db:
                db.execute("UPDATE records SET kind='debug' WHERE id='u-1'")
        with self.assertRaises(ValueError):
            self.module.search_records(self.area, kind='user')

    def test_snapshot_primary_key_drift_rejected_by_all_read_paths(self):
        """OpenAI: 同一损坏不能在verify/export报正常、直到迁移import才被拒绝。"""
        with closing(sqlite3.connect(self.area / 'history.sqlite3')) as db:
            with db:
                db.execute('UPDATE snapshots SET id=?', ('wrong-id',))
        for action in (lambda: self.module.verify_history(self.area),
                       lambda: self.module.read_snapshot(self.area, 'wrong-id'),
                       lambda: self.module.export_history(self.area, reviewed=True)):
            with self.subTest(action=action), self.assertRaises(ValueError):
                action()

    def test_limits_report_committed_state_when_summary_readback_fails(self):
        """OpenAI: 写成功而文件回读失败必须明确区分，不能诱导用户盲重放。"""
        (self.area / 'USER.md').write_bytes(b'\xff')
        limits = {'USER.md': 3000, 'MEMORY.md': 5000, 'DEBUG.md': 5000}
        result = self.module.configure_limits(self.area, limits)
        self.assertTrue(result['committed'])
        self.assertEqual(result['limits'], limits)
        self.assertIn('status_error', result)
        with closing(sqlite3.connect(self.area / 'history.sqlite3')) as db:
            stored = json.loads(db.execute("SELECT value FROM metadata WHERE key='limits'").fetchone()[0])
        self.assertEqual(stored, limits)

    def test_missing_snapshot_reference_rejected_before_export(self):
        """OpenAI: 完整性检查和导出必须检查恢复资料的引用可达性。"""
        with closing(sqlite3.connect(self.area / 'history.sqlite3')) as db:
            with db:
                db.execute('DELETE FROM records')
        with self.assertRaises(ValueError):
            self.module.verify_history(self.area)
        with self.assertRaises(ValueError):
            self.module.read_snapshot(self.area, self.snapshot)
        with self.assertRaises(ValueError):
            self.module.export_history(self.area, reviewed=True)


if __name__ == '__main__':
    unittest.main()
