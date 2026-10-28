# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Public rendering must not read or echo private identity/configuration.
import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/ld-codestyle-online/scripts/maintain.py'


class PublicCommitPrivacyTests(unittest.TestCase):
    def test_public_json_survives_legacy_console_encodings(self):
        """OpenAI: 验证公开中文摘要在两种旧控制台编码下仍可按 ASCII JSON 读取。"""
        for encoding in ('cp936', 'cp1252'):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    [sys.executable, '-B', str(SCRIPT), '--data-root', tmp,
                     'commit-header', '--visibility', 'public', '--summary', '公开摘要 🌙 café'],
                    env=dict(os.environ, PYTHONIOENCODING=encoding), capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout.decode('ascii')),
                                 {'header': '公开摘要 🌙 café', 'visibility': 'public'})

    def test_private_still_requires_model(self):
        """OpenAI: 确认私有提交头缺少明确模型时不会返回有效头字段。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, '-B', str(SCRIPT), '--data-root', tmp,
                 'commit-header', '--visibility', 'private', '--summary', '私有摘要'],
                capture_output=True, text=True, encoding='utf-8', timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('"header"', result.stdout)

    def test_rules_and_all_copyable_memory_templates_include_public_exception(self):
        """OpenAI: 核对仓库规则与可复制模板均声明公开/私有隐私边界。"""
        skill = ROOT / 'skills/ld-codestyle-online'
        for path in (ROOT/'README.md', ROOT/'CONTRIBUTING.md', skill/'SKILL.md',
                     skill/'references/commit.md', skill/'references/directory-context.md',
                     skill/'references/agentic.md', *sorted((skill/'templates').glob('module-*.md'))):
            text = path.read_text(encoding='utf-8')
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertIn('公开', text)
                self.assertIn('私有', text)
                self.assertIn('隐私', text)
        spec = (skill/'references/commit.md').read_text(encoding='utf-8')
        for term in ('待推送提交', '中间版本', '证件号', '密钥', '撤销/轮换',
                     'private=false', 'internal', '不是通用脱敏器', '--visibility public',
                     '未知/查询失败不默认私有', '不重写旧提交'):
            self.assertIn(term, spec)

    def test_visibility_must_be_explicit_and_unknown_must_not_fall_back_to_private(self):
        """OpenAI: 未提供或不认识的可见性不能悄悄回退为私有身份头。"""
        for visibility in ((), ('--visibility', 'unknown'), ('--visibility', 'internal')):
            with self.subTest(visibility=visibility), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    [sys.executable, '-B', str(SCRIPT), '--data-root', tmp,
                     'commit-header', '--model', 'vendor/model', '--summary', '可见性待核',
                     *visibility], capture_output=True, text=True, encoding='utf-8', timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('"header"', result.stdout)

    def test_direct_renderer_rejects_unknown_visibility_and_does_not_read_host_for_public(self):
        """OpenAI: 直接调用渲染器时拒绝未知可见性，公开分支不可读取本机名。"""
        spec = importlib.util.spec_from_file_location('public_commit_fixture', SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for visibility in (None, '', 'unknown', 'internal'):
            with self.subTest(visibility=visibility), self.assertRaises(ValueError):
                module.commit_header(module.DEFAULTS, 'vendor/model', '', '可见性待核',
                                     visibility=visibility)
        with patch.object(module.socket, 'gethostname', side_effect=AssertionError('must not read host')):
            self.assertEqual(module.commit_header(None, None, '', '公开摘要', visibility='public'),
                             '公开摘要')

    def test_public_rejects_reintroduced_identity_and_malformed_summary(self):
        """OpenAI: 拒绝公开摘要中的身份字段及格式异常内容，并检查报错不回显原文。"""
        for summary in ('', ' leading', 'trailing ', 'x\ny', 'x|y',
                        '##模型：vendor/model', '##主人 + 模型：vendor/model',
                        '模型:vendor/model', '计算机：PRIVATE-HOST'):
            with self.subTest(summary=summary), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    [sys.executable, '-B', str(SCRIPT), '--data-root', tmp,
                     'commit-header', '--visibility', 'public', '--summary', summary],
                    capture_output=True, text=True, encoding='utf-8', timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('"header"', result.stdout)
                if summary:
                    self.assertNotIn(summary, result.stdout)

    def test_public_discards_identity_flags_and_private_configuration(self):
        """OpenAI: 验证公开命令忽略私有身份标志、不读取或改写显式数据目录。"""
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / 'data'
            data.mkdir()
            before = data / 'config.json'
            before.write_text('{"human_commit_name":"PRIVATE-PERSON"}', encoding='utf-8')
            raw = before.read_bytes()
            result = subprocess.run(
                [sys.executable, '-B', str(SCRIPT), '--skill-root', tmp, '--data-root', str(data),
                 'commit-header', '--visibility', 'public', '--summary', '公开摘要',
                 '--model', 'private-model', '--bot', 'private-bot', '--named-bot',
                 '--mixed-human', '--computer-name', 'PRIVATE-HOST'],
                capture_output=True, text=True, encoding='utf-8', timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout), {'header': '公开摘要', 'visibility': 'public'})
            self.assertEqual(before.read_bytes(), raw)
            self.assertEqual(list(data.iterdir()), [before])

    def test_public_cli_needs_only_summary_and_does_not_create_local_data(self):
        """OpenAI: 公开摘要不依赖现存技能安装，也不生成任何本地私有数据。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill, data = Path(tmp) / 'skill', Path(tmp) / 'private-data'
            result = subprocess.run(
                [sys.executable, '-B', str(SCRIPT), '--skill-root', str(skill),
                 '--data-root', str(data), 'commit-header', '--visibility', 'public',
                 '--summary', '补充公开提交隐私规则'],
                capture_output=True, text=True, encoding='utf-8', timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout),
                             {'header': '补充公开提交隐私规则', 'visibility': 'public'})
            self.assertEqual(result.stderr, '')
            self.assertFalse(data.exists())
            self.assertFalse(skill.exists())


if __name__ == '__main__':
    unittest.main()
