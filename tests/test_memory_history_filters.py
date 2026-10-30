# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 用真实SQLite和CLI核独立日期/类型列及组合筛选，不接触业务数据库。"""
from contextlib import closing
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/ld-codestyle-online/scripts/memory_history.py'


class HistoryFilterTests(unittest.TestCase):
    """OpenAI: 每个用例使用单独临时责任区，核SQL结构和用户可用查询。"""

    def setUp(self):
        """OpenAI: 建立隔离库与合成原话，不借现有项目数据作测试。"""
        spec = importlib.util.spec_from_file_location('history_filters', SCRIPT)
        assert spec and spec.loader
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / 'README.md').write_text('# 合成责任区', encoding='utf-8')
        self.area = self.root / 'Agentic'
        self.area.mkdir()
        self.module.initialize(self.area, '../README.md', 'audio', '合成音频模块', 'private')

    def record(self, record_id='u-1', when='2026-01-01', kind='user'):
        """OpenAI: 制造明确标注的合成记录，debug包含合成验证来源。"""
        return dict(id=record_id, kind=kind, scope='audio', title='合成播放记录',
                    content='合成记录：停止不删除对象。', source='synthetic:test',
                    occurred_at=when, related_paths=['Scripts/Player.cs'], relevance='合成生命周期',
                    status='verified' if kind == 'debug' else 'confirmed',
                    evidence=['synthetic:verified'] if kind == 'debug' else [],
                    supersedes=None, redacted=False)

    def test_independent_columns_indexes_and_roundtrip(self):
        """OpenAI: 日期类型确实是SQL列且有索引，不只是JSON里出现同名键。"""
        source = self.record()
        self.module.append_record(self.area, source, reviewed=True)
        with closing(sqlite3.connect(self.area / 'history.sqlite3')) as db:
            columns = {row[1] for row in db.execute('PRAGMA table_info(records)')}
            self.assertTrue({'kind', 'occurred_at'} <= columns, columns)
            self.assertEqual(db.execute('SELECT kind,occurred_at FROM records').fetchone(), ('user', '2026-01-01'))
            indexes = {row[1] for row in db.execute('PRAGMA index_list(records)')}
            self.assertTrue({'records_kind_occurred_at_idx', 'records_occurred_at_idx'} <= indexes)
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 2)
        self.assertEqual(self.module.read_record(self.area, 'u-1')['record'], source)

    def test_type_date_combination_and_cli_pagination(self):
        """OpenAI: 查询按来源日历日期含首尾日筛选，支持不带关键词和组合分页。"""
        for item in (self.record('u-1'), self.record('u-2', '2026-01-31T23:59:59+08:00'),
                     self.record('u-3', '2026-02-01'), self.record('d-1', '2026-01-15', 'debug'),
                     self.record('u-4', 'unknown')):
            self.module.append_record(self.area, item, reviewed=True)
        result = subprocess.run([sys.executable, '-B', str(SCRIPT), '--area', str(self.area),
                                 'search', '--kind', 'user', '--from-date', '2026-01-01',
                                 '--to-date', '2026-01-31', '--limit', '1'],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        page = json.loads(result.stdout)
        self.assertEqual([item['id'] for item in page['items']], ['u-1'])
        self.assertTrue(page['has_more'])
        second = self.module.search_records(self.area, '', limit=1, offset=page['next_offset'],
                                           kind='user', from_date='2026-01-01', to_date='2026-01-31')
        self.assertEqual([item['id'] for item in second['items']], ['u-2'])
        self.assertFalse(second['has_more'])
        self.assertEqual(len(self.module.search_records(self.area, '停止', kind='debug')['items']), 1)
        self.assertEqual(len(self.module.search_records(self.area, '', to_date='2026-01-31')['items']), 3)
        self.assertEqual(len(self.module.search_records(self.area, '', from_date='2026-02-01')['items']), 1)
        self.assertEqual(len(self.module.search_records(self.area, '', kind='user')['items']), 4)


    def test_invalid_dates_and_projection_drift_are_rejected(self):
        """OpenAI: 非法日期/时区不修猜，列被改但原JSON不变时仍能检出。"""
        for value in ('2026-02-30', '2026-1-1', '2026-01-01T00:00:00',
                      '2026-01-01T00:00:00+08:60', '2026-01-01T25:00:00Z'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.module.append_record(self.area, self.record(when=value), reviewed=True)
        self.assertEqual(self.module.verify_history(self.area)['records'], 0)
        for filters in ({'from_date': '2026-02-30'}, {'from_date': '2026-02-01', 'to_date': '2026-01-01'},
                        {'kind': 'chat'}, {'to_date': "2026-01-01' OR 1=1"}):
            with self.subTest(filters=filters), self.assertRaises(ValueError):
                self.module.search_records(self.area, '播放', **filters)
        self.module.append_record(self.area, self.record(), reviewed=True)
        with closing(sqlite3.connect(self.area / 'history.sqlite3')) as db:
            with db:
                db.execute("UPDATE records SET occurred_at='2025-01-01' WHERE id='u-1'")
        with self.assertRaises(ValueError):
            self.module.verify_history(self.area)
        with self.assertRaises(ValueError):
            self.module.read_record(self.area, 'u-1')

    def test_legacy_export_preserves_payload_and_atomic_import(self):
        """OpenAI: 旧版交换包导入新库补列但不改原文；非法新投影使整批回滚。"""
        self.module.append_record(self.area, self.record(when='unknown'), reviewed=True)
        bundle = self.module.export_history(self.area, reviewed=True)
        legacy = json.loads(json.dumps(bundle))
        legacy['schema'] = 1
        for row in legacy['records']:
            del row['kind'], row['occurred_at']
        legacy['sha256'] = self.module.digest(self.module.canonical(
            {key: value for key, value in legacy.items() if key != 'sha256'}))
        other = self.root / 'copy' / 'Agentic'
        other.mkdir(parents=True)
        (other.parent / 'README.md').write_text('# 合成副本', encoding='utf-8')
        self.module.initialize(other, '../README.md', 'audio', '合成音频模块', 'private')
        self.module.import_history(other, legacy, reviewed=True)
        self.assertEqual(self.module.export_history(other, reviewed=True), bundle)
        self.module.append_record(self.area, self.record('u-2'), reviewed=True)
        bad = self.module.export_history(self.area, reviewed=True)
        bad['records'][1]['kind'] = 'debug'
        bad['sha256'] = self.module.digest(self.module.canonical(
            {key: value for key, value in bad.items() if key != 'sha256'}))
        with self.assertRaises(ValueError):
            self.module.import_history(other, bad, reviewed=True)
        self.assertEqual(self.module.export_history(other, reviewed=True), bundle)
        # OpenAI: 版本门槛先拒绝；不靠查询或初始化偷偷改写旧库结构。
        with closing(sqlite3.connect(other / 'history.sqlite3')) as db:
            with db:
                db.execute('PRAGMA user_version=1')
        before = (other / 'history.sqlite3').read_bytes()
        with self.assertRaises(ValueError):
            self.module.search_records(other, '播放')
        self.assertEqual((other / 'history.sqlite3').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
