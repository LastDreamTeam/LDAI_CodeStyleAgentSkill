# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: Verify attribution, explicit Bot declarations, and reusable identity output."""
import importlib.util
import json
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/ld-codestyle-online/scripts/maintain.py'
IDENTITY = ROOT / 'skills/ld-codestyle-online/scripts/commit_identity.py'
SPEC = importlib.util.spec_from_file_location('commit_identity_fixture', IDENTITY)
identity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(identity)


class CommitIdentityTests(unittest.TestCase):
    def invoke(self, skill, data, *args):
        """OpenAI: 在隔离技能与数据目录运行 CLI，并为本组私有用例补显式可见性。"""
        if args and args[0] == 'commit-header':
            args = (args[0], '--visibility', 'private', *args[1:])
        return subprocess.run(
            [sys.executable, '-B', str(SCRIPT), '--skill-root', str(skill),
             '--data-root', str(data), *args], capture_output=True,
            text=True, encoding='utf-8', timeout=10)

    def test_display_name_is_separate_persistent_and_legacy_safe(self):
        """OpenAI: 核对独立显示名、旧偏好保全、安装隔离及非法值的拒绝写入。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill, other, data = root / 'skill', root / 'other', root / 'data'
            skill.mkdir()
            other.mkdir()
            shown = self.invoke(skill, data, 'show')
            self.assertEqual(shown.returncode, 0, shown.stderr)
            initial = json.loads(shown.stdout)
            self.assertEqual(initial['config']['human_commit_name'], '主人')
            config_file = Path(initial['data_dir']) / 'config.json'
            legacy = {'schema_version': 1, 'human_name': '旧标识',
                      'interval_days': 9, 'auto_update': False}
            config_file.write_text(json.dumps(legacy), encoding='utf-8')
            result = self.invoke(skill, data, 'show')
            self.assertEqual(json.loads(result.stdout)['config'],
                             dict(legacy, human_commit_name='主人'))
            result = self.invoke(skill, data, 'config', '--human-commit-name', '褪色的梦')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['config'],
                             dict(legacy, human_commit_name='褪色的梦'))
            result = self.invoke(skill, data, 'show')
            self.assertEqual(json.loads(result.stdout)['config']['human_commit_name'], '褪色的梦')
            result = self.invoke(other, data, 'show')
            self.assertEqual(json.loads(result.stdout)['config']['human_commit_name'], '主人')
            result = self.invoke(skill, data, 'config', '--human-name', '新标识')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['config']['human_commit_name'], '褪色的梦')
            # OpenAI: 错误输入不得顺带重写既有有效偏好。
            before = config_file.read_bytes()
            for bad in ('', '伪造\n##模型：other', '名字 | 假摘要'):
                result = self.invoke(skill, data, 'config', '--human-commit-name', bad)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(config_file.read_bytes(), before)

    def test_headers_reflect_mixed_contribution_and_configured_display_name(self):
        """OpenAI: 实跑 CLI，核对 Bot 无模型、混合人类前缀以及可复用身份字段。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill, data = Path(tmp) / 'skill', Path(tmp) / 'data'
            skill.mkdir()
            source = skill / 'example.cs'
            original = '// LD: keep the human contract\nclass Example {}'
            source.write_text(original, encoding='utf-8')
            args = ('commit-header', '--client', 'Hermes', '--bot', '列克星敦',
                    '--named-bot', '--summary', '按人类约定调整实现')
            result = self.invoke(skill, data, *args, '--mixed-human')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['header'],
                             '##主人 + 模型：Hermes-列克星敦 | 按人类约定调整实现')
            renamed = self.invoke(skill, data, 'config', '--human-commit-name', '褪色的梦')
            self.assertEqual(renamed.returncode, 0, renamed.stderr)
            result = self.invoke(skill, data, *args, '--mixed-human')
            self.assertEqual(json.loads(result.stdout)['header'],
                             '##褪色的梦 + 模型：Hermes-列克星敦 | 按人类约定调整实现')
            result = self.invoke(skill, data, *args)
            rendered = json.loads(result.stdout)
            self.assertEqual(rendered['header'], '##模型：Hermes-列克星敦 | 按人类约定调整实现')
            self.assertEqual(rendered['identity'], 'Hermes-列克星敦')
            self.assertEqual(source.read_text(encoding='utf-8'), original)

    def test_header_render_does_not_rewrite_preferences(self):
        """OpenAI: 生成带实际强度的私有 Agent 首行时，原始旧配置字节保持不变。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill, data = Path(tmp) / 'skill', Path(tmp) / 'data'
            skill.mkdir()
            initial = json.loads(self.invoke(skill, data, 'show').stdout)
            config_file = Path(initial['data_dir']) / 'config.json'
            legacy = {'schema_version': 1, 'human_name': 'LD',
                      'interval_days': 7, 'auto_update': False}
            raw = json.dumps(legacy, separators=(',', ':')).encode()
            config_file.write_bytes(raw)
            result = self.invoke(skill, data, 'commit-header', '--client', 'DeepSeekHarness',
                                 '--model', 'gpt-6-astra', '--reasoning-effort', 'high',
                                 '--summary', '只生成首行', '--mixed-human')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['header'],
                             '##主人 + 模型：DeepSeekHarness gpt-6-astra high | 只生成首行')
            self.assertEqual(config_file.read_bytes(), raw)

    def test_private_bot_requires_framework_nickname_and_explicit_declaration(self):
        """OpenAI: 独立 Bot 身份需三个明确字段，普通会话昵称不能走 Bot 分支。"""
        for fields in ({'bot': '列克星敦'}, {'bot': '列克星敦', 'client': 'Hermes'},
                       {'bot': '列克星敦', 'named_bot': True},
                       {'client': 'Codex', 'named_bot': True}):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                identity.commit_identity('gpt-6-astra', visibility='private',
                                         reasoning_effort='high', **fields)
        for default in ('Codex', 'OpenAI Codex', 'DSH', 'DSH Bot', 'GPT', 'GPT Dot',
                        'GPT Sol', 'Hermes Bot', 'Assistant'):
            with self.subTest(default=default), self.assertRaises(ValueError):
                identity.commit_identity(bot=default, client='Hermes', named_bot=True,
                                         visibility='private')
        self.assertEqual(identity.commit_identity(bot='列克星敦', client='Hermes',
                                                  named_bot=True, visibility='private'),
                         'Hermes-列克星敦')

    def test_private_agent_requires_framework_model_and_actual_reasoning(self):
        """OpenAI: 缺框架、完整型号或实际档位时拒绝；none 必须由调用方显式声明。"""
        valid = {'model': 'gpt-6-astra', 'client': 'DeepSeekHarness',
                 'reasoning_effort': 'xhigh', 'visibility': 'private'}
        self.assertEqual(identity.commit_identity(**valid), 'DeepSeekHarness gpt-6-astra xhigh')
        for field in ('model', 'client', 'reasoning_effort'):
            for missing in (None, ''):
                with self.subTest(field=field, missing=missing), self.assertRaises(ValueError):
                    identity.commit_identity(**{**valid, field: missing})
        for value in ('unknown', 'auto', 'default', '?', '无从得知'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                identity.commit_identity(**{**valid, 'reasoning_effort': value})
        self.assertEqual(identity.commit_identity(**{**valid, 'reasoning_effort': 'none'}),
                         'DeepSeekHarness gpt-6-astra none')

    def test_identity_fields_reject_extra_header_structure_without_echo(self):
        """OpenAI: 全部身份输入拒绝控制字符与结构注入，错误信息不回显输入。"""
        valid = {'model': 'gpt-6-astra', 'client': 'Codex',
                 'reasoning_effort': 'high', 'visibility': 'private'}
        for field in ('model', 'client', 'reasoning_effort'):
            for value in (' first', 'trailing ', 'first\nsecond', 'first|secret',
                          'first+second', 'PC:SECRET', '模型：SECRET', '##SECRET', '<占位>'):
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ValueError) as error:
                        identity.commit_identity(**{**valid, field: value})
                    self.assertNotIn(value, str(error.exception))
        for value in ('Name|other', 'Name+other', 'Name\nother', 'Name PC:SECRET', None, 0, False, []):
            with self.subTest(bot=value), self.assertRaises(ValueError):
                identity.commit_identity(bot=value, client='Hermes', named_bot=True,
                                         visibility='private')

    def test_pc_is_only_explicit_and_never_queries_operating_system(self):
        """OpenAI: 禁用主机查询后仍可生成身份，只有显式合法 PC 值才追加。"""
        valid = {'model': 'gpt-6-astra', 'client': 'Codex',
                 'reasoning_effort': 'high', 'visibility': 'private'}
        with patch.object(socket, 'gethostname', side_effect=AssertionError('must not query host')):
            self.assertEqual(identity.commit_identity(**valid), 'Codex gpt-6-astra high')
            self.assertEqual(identity.commit_identity(**valid, pc='TEST-PC'),
                             'Codex gpt-6-astra high PC:TEST-PC')
            self.assertEqual(identity.commit_identity(**valid, computer_name='TEST-PC'),
                             'Codex gpt-6-astra high PC:TEST-PC')
            self.assertEqual(identity.commit_identity(**valid, computer_name='TEST-PC', pc='TEST-PC'),
                             'Codex gpt-6-astra high PC:TEST-PC')
        for host in ('', ' fake ', 'host\nother', 'host | fake', 'host/path', '<unknown>'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                identity.commit_identity(**valid, pc=host)
        with self.assertRaises(ValueError):
            identity.commit_identity(**valid, pc='FIRST', computer_name='SECOND')
        self.assertEqual(identity.commit_identity(bot='列克星敦', client='Hermes', named_bot=True,
                                                  pc='BOT-HOST', visibility='private'),
                         'Hermes-列克星敦 PC:BOT-HOST')

    def test_result_reuses_exact_identity_and_never_mutates_configuration(self):
        """OpenAI: 同一结果同时供首行和 Git 显示名复用，纯函数不修改输入偏好。"""
        config = {'human_commit_name': '褪色的梦'}
        original = dict(config)
        result = identity.commit_result(config, 'gpt-6-astra', '', '修复输入',
                                        client='Codex', reasoning_effort='high',
                                        mixed_human=True, visibility='private')
        self.assertEqual(result, {'header': '##褪色的梦 + 模型：Codex gpt-6-astra high | 修复输入',
                                  'identity': 'Codex gpt-6-astra high', 'visibility': 'private'})
        self.assertEqual(config, original)
        self.assertEqual(identity.commit_header(config, 'gpt-6-astra', '', '修复输入',
                                                client='Codex', reasoning_effort='high',
                                                mixed_human=True, visibility='private'), result['header'])
        for config in (None, {}, {'human_commit_name': 'fake\nother'}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                identity.commit_result(config, None, '列克星敦', '修复输入', client='Hermes',
                                       named_bot=True, mixed_human=True, visibility='private')

    def test_document_templates_produce_exact_git_subject(self):
        """OpenAI: 用临时 Git 仓库验证文档三段模板的空行确实保留准确提交主题。"""
        docs = [ROOT / 'skills/ld-codestyle-online/SKILL.md',
                ROOT / 'skills/ld-codestyle-online/references/commit.md']
        templates = [block for doc in docs
                     for block in re.findall(r'```text\n(.*?)\n```', doc.read_text(encoding='utf-8'), re.S)
                     if '##问题：' in block and '##解决：' in block]
        self.assertTrue(templates)
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['git', 'init', '-q', tmp], check=True, capture_output=True)
            for template in templates:
                with self.subTest(header=template.splitlines()[0]):
                    # OpenAI: 这里只在临时仓库产生测试提交，绝不改工作仓库或全局作者配置。
                    subprocess.run(['git', '-C', tmp, '-c', 'user.name=SkillFixture',
                                    '-c', 'user.email=fixture@example.invalid',
                                    '-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-F', '-'],
                                   input=template, text=True, encoding='utf-8', check=True, capture_output=True)
                    subject = subprocess.check_output(['git', '-C', tmp, 'log', '-1', '--format=%s'],
                                                      text=True, encoding='utf-8').strip()
                    self.assertEqual(subject, template.splitlines()[0])

    def test_configuration_edit_commands_are_centralized_in_readme(self):
        """OpenAI: 配置编辑命令保持唯一入口，技能仍需声明独立人类显示名和混合贡献。"""
        pattern = r'config\s+--(?:human-name|human-commit-name|interval-days|auto-update|interaction|answer-wait-minutes|idle-after-minutes)\b'
        offenders = [str(path.relative_to(ROOT)) for path in ROOT.rglob('*.md')
                     if path.name != 'README.md' and '.git' not in path.relative_to(ROOT).parts
                     and re.search(pattern, path.read_text(encoding='utf-8'))]
        self.assertEqual(offenders, [], 'Configuration edit commands belong only in README')
        readme = (ROOT / 'README.md').read_text(encoding='utf-8')
        for flag in ('--human-name', '--human-commit-name', '--interval-days', '--auto-update'):
            self.assertIn(flag, readme)
        skill = (ROOT / 'skills/ld-codestyle-online/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('human_commit_name', skill)
        self.assertIn('##主人 + 模型：', skill)


if __name__ == '__main__':
    unittest.main()
