# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: Public defaults expose only intended identity, with explicit user overrides."""
import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/ld-codestyle-online/scripts/maintain.py'
IDENTITY = ROOT / 'skills/ld-codestyle-online/scripts/commit_identity.py'
SPEC = importlib.util.spec_from_file_location('public_identity_fixture', IDENTITY)
identity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(identity)


class PublicCommitPrivacyTests(unittest.TestCase):
    def invoke(self, data, *args):
        """OpenAI: 在指定临时数据根运行真实 CLI，不替调用方补任何身份信息。"""
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--data-root', str(data),
                               'commit-header', *args], capture_output=True, text=True,
                              encoding='utf-8', timeout=10)

    def test_public_json_survives_legacy_console_encodings(self):
        """OpenAI: 含身份的公开中文结果在旧控制台编码下仍是可读 ASCII JSON。"""
        for encoding in ('cp936', 'cp1252'):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as tmp:
                result = subprocess.run(
                    [sys.executable, '-B', str(SCRIPT), '--data-root', tmp,
                     'commit-header', '--visibility', 'public', '--bot', '列克星敦',
                     '--named-bot', '--summary', '公开摘要 🌙 café'],
                    env=dict(os.environ, PYTHONIOENCODING=encoding), capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout.decode('ascii')),
                                 {'header': '##模型：列克星敦 | 公开摘要 🌙 café',
                                  'identity': '列克星敦', 'visibility': 'public'})

    def test_public_defaults_to_bot_nickname_or_complete_model_without_reasoning(self):
        """OpenAI: 公开默认 Bot 只留昵称，Agent 只留完整型号并保留型号本身的后缀。"""
        with tempfile.TemporaryDirectory() as tmp:
            for flags, expected in (
                (('--client', 'Hermes', '--bot', '列克星敦', '--named-bot'), '列克星敦'),
                (('--client', 'Codex', '--model', 'vendor/Exact-Model-v2-high',
                  '--reasoning-effort', 'xhigh'), 'vendor/Exact-Model-v2-high'),
                (('--model', 'GPT Sol6.1 xhigh', '--reasoning-effort', 'xhigh'), 'GPT Sol6.1'),
                (('--model', 'GPT Sol6.1 XHIGH', '--reasoning-effort', 'xhigh'), 'GPT Sol6.1'),
            ):
                with self.subTest(expected=expected):
                    result = self.invoke(tmp, '--visibility', 'public', *flags,
                                         '--pc', 'PRIVATE-HOST', '--mixed-human', '--summary', '公开摘要')
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(json.loads(result.stdout),
                                     {'header': f'##模型：{expected} | 公开摘要',
                                      'identity': expected, 'visibility': 'public'})
                    self.assertNotIn('PRIVATE-HOST', result.stdout + result.stderr)
            for model in ('GPT Sol6.1 xhigh', 'GPT Sol6.1 XHIGH', 'GPT', 'Sol', 'GPT Sol',
                          'DSH', 'DSH Bot', 'auto', '<model>'):
                with self.subTest(model=model):
                    result = self.invoke(tmp, '--visibility', 'public', '--model', model,
                                         '--summary', '不能猜测实际身份')
                    self.assertNotEqual(result.returncode, 0, result.stdout)
            for model, effort in (('GPT Sol6.1 high xhigh', 'xhigh'),
                                  ('GPT Sol6.1 high', 'xhigh')):
                result = self.invoke(tmp, '--visibility', 'public', '--model', model,
                                     '--reasoning-effort', effort, '--summary', '拒绝混合档位')
                self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_public_overrides_are_explicit_mutually_exclusive_and_private_cannot_use_them(self):
        """OpenAI: 用户可明确指定公开名称或省略，但同样参数不能削弱私有身份要求。"""
        with tempfile.TemporaryDirectory() as tmp:
            for flags, expected in ((('--public-name', 'PublicMaintainer'), 'PublicMaintainer'),
                                    (('--omit-public-identity',), '')):
                result = self.invoke(tmp, '--visibility', 'public', '--summary', '公开摘要', *flags)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout),
                                 {'header': f'##模型：{expected} | 公开摘要' if expected else '公开摘要',
                                  'identity': expected, 'visibility': 'public'})
                for source in ((), ('--client', 'Codex', '--model', 'gpt-6-astra',
                                   '--reasoning-effort', 'high')):
                    rejected = self.invoke(tmp, '--visibility', 'private', '--summary', '私有摘要',
                                           *source, *flags)
                    self.assertNotEqual(rejected.returncode, 0, rejected.stdout)
                    self.assertNotIn('"header"', rejected.stdout)
            result = self.invoke(tmp, '--visibility', 'public', '--summary', '公开摘要',
                                 '--public-name', 'PublicMaintainer', '--omit-public-identity')
            self.assertNotEqual(result.returncode, 0)
            for name in ('', 'name\nother', 'name+other', 'PC:PRIVATE-HOST', '<placeholder>'):
                result = self.invoke(tmp, '--visibility', 'public', '--summary', '公开摘要',
                                     '--public-name', name)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('PRIVATE-HOST', result.stdout + result.stderr)

    def test_visibility_must_be_explicit_and_unknown_must_not_fall_back_to_private(self):
        """OpenAI: 未提供、未知或企业 internal 可见性不能悄悄退回私有规则。"""
        for visibility in ((), ('--visibility', 'unknown'), ('--visibility', 'internal')):
            with self.subTest(visibility=visibility), tempfile.TemporaryDirectory() as tmp:
                result = self.invoke(tmp, '--client', 'Codex', '--model', 'gpt-6-astra',
                                     '--reasoning-effort', 'high', '--summary', '可见性待核', *visibility)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('"header"', result.stdout)
        for value in (None, '', 'unknown', 'internal'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                identity.commit_header(None, 'gpt-6-astra', '', '可见性待核', visibility=value)

    def test_public_has_no_config_host_or_private_metadata_dependency(self):
        """OpenAI: 用不能读取的配置与主机替身证明公开输出只依赖明确的公开字段。"""
        class UnreadableConfig(dict):
            def __getitem__(self, key):
                """OpenAI: 任何私有配置读取都使测试立即失败。"""
                raise AssertionError('must not read private configuration')

            def get(self, key, default=None):
                """OpenAI: 默认值读取也不能绕过公开配置隔离检查。"""
                raise AssertionError('must not read private configuration')

        with patch.object(socket, 'gethostname', side_effect=AssertionError('must not read host')):
            result = identity.commit_result(UnreadableConfig(), 'gpt-6-astra', '', '公开摘要',
                                            client='PRIVATE-FRAMEWORK', reasoning_effort='high',
                                            computer_name='PRIVATE-HOST', mixed_human=True,
                                            visibility='public')
            self.assertEqual(result, {'header': '##模型：gpt-6-astra | 公开摘要',
                                      'identity': 'gpt-6-astra', 'visibility': 'public'})
            # OpenAI: 显式省略不读取被舍弃的内部身份，即使其值尚不可验证。
            result = identity.commit_result(UnreadableConfig(), object(), object(), '公开摘要',
                                            visibility='public', omit_public_identity=True)
            self.assertEqual(result, {'header': '公开摘要', 'identity': '', 'visibility': 'public'})

    def test_public_rejects_reintroduced_identity_and_malformed_summary_without_echo(self):
        """OpenAI: 摘要不容许重复身份字段或控制字符，报错不回显敏感原文。"""
        for summary in ('', ' leading', 'trailing ', 'x\ny', 'x|y',
                        '##模型：vendor/model', '##主人 + 模型：vendor/model',
                        '模型:vendor/model', '计算机：PRIVATE-HOST'):
            with self.subTest(summary=summary), tempfile.TemporaryDirectory() as tmp:
                result = self.invoke(tmp, '--visibility', 'public', '--omit-public-identity',
                                     '--summary', summary)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn('"header"', result.stdout)
                if summary:
                    self.assertNotIn(summary, result.stdout)

    def test_public_cli_ignores_private_configuration_and_creates_no_data(self):
        """OpenAI: 公开默认与明确省略均不打开或建立本地配置目录，也不回显私有元数据。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / 'data'
            data.mkdir()
            before = data / 'config.json'
            before.write_text('{invalid private configuration PRIVATE-PERSON', encoding='utf-8')
            raw = before.read_bytes()
            result = self.invoke(data, '--visibility', 'public', '--model', 'gpt-6-astra',
                                 '--reasoning-effort', 'xhigh', '--client', 'PRIVATE-FRAMEWORK',
                                 '--mixed-human', '--computer-name', 'PRIVATE-HOST', '--summary', '公开摘要')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout),
                             {'header': '##模型：gpt-6-astra | 公开摘要',
                              'identity': 'gpt-6-astra', 'visibility': 'public'})
            self.assertNotIn('PRIVATE-', result.stdout + result.stderr)
            self.assertEqual(before.read_bytes(), raw)
            self.assertEqual(list(data.iterdir()), [before])
            skill, empty_data = root / 'missing-skill', root / 'missing-data'
            result = subprocess.run(
                [sys.executable, '-B', str(SCRIPT), '--skill-root', str(skill),
                 '--data-root', str(empty_data), 'commit-header', '--visibility', 'public',
                 '--omit-public-identity', '--summary', '按用户要求省略公开身份'],
                capture_output=True, text=True, encoding='utf-8', timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout),
                             {'header': '按用户要求省略公开身份', 'identity': '', 'visibility': 'public'})
            self.assertFalse(skill.exists())
            self.assertFalse(empty_data.exists())
            missing_identity = self.invoke(empty_data, '--visibility', 'public', '--summary', '未声明身份')
            self.assertNotEqual(missing_identity.returncode, 0)
            self.assertFalse(empty_data.exists())

    def test_rules_and_copyable_memory_templates_keep_privacy_and_review_boundaries(self):
        """OpenAI: 规则仍覆盖完整公开载荷和贡献边界，同时文档清除过时身份要求。"""
        skill = ROOT / 'skills/ld-codestyle-online'
        for path in (ROOT / 'README.md', ROOT / 'CONTRIBUTING.md', skill / 'SKILL.md',
                     skill / 'references/commit.md', skill / 'references/directory-context.md',
                     skill / 'references/agentic.md', *sorted((skill / 'templates').glob('module-*.md'))):
            text = path.read_text(encoding='utf-8')
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertIn('公开', text)
                self.assertIn('私有', text)
                self.assertIn('隐私', text)
        spec = (skill / 'references/commit.md').read_text(encoding='utf-8')
        for term in ('待推送提交', '中间版本', '证件号', '密钥', '撤销/轮换',
                     'private=false', 'internal', '不是通用脱敏器', '--visibility public',
                     '未知/查询失败不默认私有', '不重写旧提交', '--reasoning-effort',
                     '--public-name', '--omit-public-identity', '独立身份', 'none', '自有邮箱'):
            self.assertIn(term, spec)
        for obsolete in ('生成器默认调用当前 OS', '--client` 与 `--bot` 二选一',
                         '不在姓名中塞型号或PC', '公开仓库：省略整个模型身份段'):
            self.assertNotIn(obsolete, spec)


if __name__ == '__main__':
    unittest.main()
