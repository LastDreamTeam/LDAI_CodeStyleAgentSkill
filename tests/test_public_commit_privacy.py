# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: Public defaults omit identity, with explicit public-name overrides."""
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
    def test_local_account_selection_in_entry_and_remote_workflow(self):
        """OpenAI: 验证入口能找到本地作者、远端身份及连接器回退规则。"""
        skill = ROOT / 'skills/ld-codestyle-online'
        entry = (skill / 'SKILL.md').read_text(encoding='utf-8')
        workflow = (skill / 'references/branch-workflow.md').read_text(encoding='utf-8')
        spec = (skill / 'references/commit.md').read_text(encoding='utf-8')
        account = spec.split('### 本地账号优先\n', 1)[1].split('\n### ', 1)[0]
        for source in (entry, account):
            for term in ('Codex、Cursor、DSH', '只有本地确实缺少账号且用户未禁用连接器'):
                self.assertIn(term, source)
        for source in (entry, workflow):
            self.assertIn('commit.md#本地账号优先)', source)
        for term in ('Git 作者、提交者和邮箱', 'Git Credential Manager', 'SSH 账号',
                     '仅凭 `gh auth status` 未登录不能改用连接器', '同一本地账号的 API 登录',
                     '不能把权限不足当作缺少账号', '不能切换连接器绕过限制',
                     'LastDream 本人已确认使用此默认', '一次指定不改长期偏好',
                     '才在已有的项目偏好或用户设置中为该主人记住例外'):
            with self.subTest(term=term):
                self.assertIn(term, account)
        for term in ('本地是私人邮箱且没有公开授权', '已核实的 GitHub noreply 地址'):
            self.assertIn(term, spec)

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
                     'commit-header', '--visibility', 'public',
                     '--summary', '公开摘要 🌙 café'],
                    env=dict(os.environ, PYTHONIOENCODING=encoding), capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout.decode('ascii')),
                                 {'header': '公开摘要 🌙 café',
                                  'identity': '', 'visibility': 'public'})

    def test_public_defaults_to_summary_only_without_identity(self):
        """OpenAI: 公开默认只留摘要，忽略内部身份字段，也不因缺少 bot/model 失败。"""
        with tempfile.TemporaryDirectory() as tmp:
            cases = (
                (),
                ('--client', 'Hermes', '--bot', '列克星敦', '--named-bot'),
                ('--client', 'Codex', '--model', 'vendor/Exact-Model-v2-high',
                 '--reasoning-effort', 'xhigh'),
                ('--model', 'GPT Sol6.1 xhigh', '--reasoning-effort', 'xhigh'),
                ('--model', 'GPT'),
            )
            for flags in cases:
                with self.subTest(flags=flags):
                    result = self.invoke(tmp, '--visibility', 'public', *flags,
                                         '--pc', 'PRIVATE-HOST', '--mixed-human', '--summary', '公开摘要')
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertEqual(json.loads(result.stdout),
                                     {'header': '公开摘要',
                                      'identity': '', 'visibility': 'public'})
                    self.assertNotIn('PRIVATE-HOST', result.stdout + result.stderr)
                    self.assertNotIn('##模型', result.stdout)

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
            self.assertEqual(result, {'header': '公开摘要',
                                      'identity': '', 'visibility': 'public'})
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
                             {'header': '公开摘要',
                              'identity': '', 'visibility': 'public'})
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
            self.assertEqual(missing_identity.returncode, 0, missing_identity.stdout + missing_identity.stderr)
            self.assertEqual(json.loads(missing_identity.stdout),
                             {'header': '未声明身份', 'identity': '', 'visibility': 'public'})
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
                self.assertNotRegex(text, r'公开(?:目标| Bot)?默认(?:只留|只需|只记|用|是)(?:Bot|昵称)')
                if path.parent == skill / 'templates':
                    header, changes = text.split('## 变更记录', 1)
                    self.assertIn('公开默认不写模型身份段', header)
                    self.assertIn('公开目标默认不写模型身份段', changes)
                    self.assertIn('私有身份记录：`##模型：', changes)
        spec = (skill / 'references/commit.md').read_text(encoding='utf-8')
        for term in ('待推送提交', '中间版本', '证件号', '密钥', '撤销/轮换',
                     'private=false', 'internal', '不是通用脱敏器', '--visibility public',
                     '未知/查询失败不默认私有', '不重写旧提交', '--reasoning-effort',
                     '--public-name', '--omit-public-identity', '独立身份', 'none', '自有邮箱'):
            self.assertIn(term, spec)
        for required in ('公开仓库：首行只写摘要', '不写模型身份段', '公开默认返回空 `identity`',
                         '已获准公开的真实显示名和邮箱'):
            self.assertIn(required, spec)
        public_guide = spec.split('### 公开仓库：', 1)[1].split('用户可明确要求公开显示名', 1)[0]
        public_example = public_guide.split('```text\n', 1)[1].split('\n```', 1)[0]
        summary, problem, solution = public_example.split('\n\n')
        self.assertNotIn('##模型：', summary)
        self.assertRegex(problem, r'^##问题：.+')
        self.assertRegex(solution, r'^##解决：.+')
        for obsolete in ('生成器默认调用当前 OS', '--client` 与 `--bot` 二选一',
                         '不在姓名中塞型号或PC', '默认保留简短身份'):
            self.assertNotIn(obsolete, spec)


if __name__ == '__main__':
    unittest.main()
