# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Exercise contribution labels through the actual CLI, in isolated install slots.
import json
import socket
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'skills/ld-codestyle-online/scripts/maintain.py'


class CommitIdentityTests(unittest.TestCase):
    def invoke(self, skill, data, *args):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--skill-root', str(skill),
                               '--data-root', str(data), *args], capture_output=True,
                              text=True, encoding='utf-8', timeout=10)

    def test_display_name_is_separate_persistent_and_legacy_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill, other, data = root/'skill', root/'other', root/'data'
            skill.mkdir()
            other.mkdir()
            shown = self.invoke(skill, data, 'show')
            self.assertEqual(shown.returncode, 0, shown.stderr)
            initial = json.loads(shown.stdout)
            self.assertEqual(initial['config'].get('human_commit_name'), '主人')
            config_file = Path(initial['data_dir'])/'config.json'
            legacy = {'schema_version':1, 'human_name':'旧标识', 'interval_days':9, 'auto_update':False}
            config_file.write_text(json.dumps(legacy), encoding='utf-8')
            result = self.invoke(skill, data, 'show')
            migrated = json.loads(result.stdout)['config']
            self.assertEqual(migrated, dict(legacy, human_commit_name='主人'))
            result = self.invoke(skill, data, 'config', '--human-commit-name', '褪色的梦')
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            changed = json.loads(result.stdout)['config']
            self.assertEqual(changed, dict(legacy, human_commit_name='褪色的梦'))
            result = self.invoke(skill, data, 'show')
            self.assertEqual(json.loads(result.stdout)['config']['human_commit_name'], '褪色的梦')
            result = self.invoke(other, data, 'show')
            self.assertEqual(json.loads(result.stdout)['config']['human_commit_name'], '主人')
            result = self.invoke(skill, data, 'config', '--human-name', '新标识')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['config']['human_commit_name'], '褪色的梦')
            before = config_file.read_bytes()
            for bad in ('', '伪造\n##模型：other', '名字 | 假摘要'):
                result = self.invoke(skill, data, 'config', '--human-commit-name', bad)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(config_file.read_bytes(), before)

    def test_headers_reflect_mixed_contribution_and_configured_display_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill, data = Path(tmp)/'skill', Path(tmp)/'data'
            skill.mkdir()
            source = skill/'example.cs'
            source.write_text('// LD: keep the human contract\nclass Example {}', encoding='utf-8')
            args = ('commit-header', '--model', 'gpt-6-astra', '--bot', '列克星敦', '--named-bot',
                    '--summary', '按人类约定调整实现')
            result = self.invoke(skill, data, *args, '--mixed-human')
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertEqual(json.loads(result.stdout)['header'],
                             '##主人 + 模型：列克星敦 + gpt-6-astra | 按人类约定调整实现')
            renamed = self.invoke(skill, data, 'config', '--human-commit-name', '褪色的梦')
            self.assertEqual(renamed.returncode, 0, renamed.stderr)
            result = self.invoke(skill, data, *args, '--mixed-human')
            self.assertEqual(json.loads(result.stdout)['header'],
                             '##褪色的梦 + 模型：列克星敦 + gpt-6-astra | 按人类约定调整实现')
            result = self.invoke(skill, data, *args)
            self.assertEqual(json.loads(result.stdout)['header'],
                             '##模型：列克星敦 + gpt-6-astra | 按人类约定调整实现')
            result = self.invoke(skill, data, 'commit-header', '--model', 'gpt-6-astra',
                                 '--summary', '无Bot身份的实现', '--mixed-human')
            self.assertEqual(json.loads(result.stdout)['header'],
                             f'##褪色的梦 + 模型：gpt-6-astra（计算机：{socket.gethostname()}） | 无Bot身份的实现')
            for field in ('--model', '--bot', '--summary'):
                bad_args = list(args)
                bad_args[bad_args.index(field)+1] = '伪造\n##主人 + 模型：other'
                result = self.invoke(skill, data, *bad_args)
                self.assertNotEqual(result.returncode, 0)
            self.assertEqual(source.read_text(encoding='utf-8'),
                             '// LD: keep the human contract\nclass Example {}')

    def test_header_render_does_not_rewrite_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill, data = Path(tmp)/'skill', Path(tmp)/'data'
            skill.mkdir()
            initial = json.loads(self.invoke(skill, data, 'show').stdout)
            config_file = Path(initial['data_dir'])/'config.json'
            legacy = {'schema_version':1, 'human_name':'LD', 'interval_days':7, 'auto_update':False}
            raw = json.dumps(legacy, separators=(',', ':')).encode()
            config_file.write_bytes(raw)
            result = self.invoke(skill, data, 'commit-header', '--model', 'gpt-6-astra',
                                 '--summary', '只生成首行', '--mixed-human')
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            self.assertTrue(json.loads(result.stdout)['header'].startswith('##主人 + 模型：'))
            self.assertEqual(config_file.read_bytes(), raw)

    def test_identity_fields_reject_extra_header_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill, data = Path(tmp)/'skill', Path(tmp)/'data'
            skill.mkdir()
            for field in ('--model', '--bot'):
                for value in ('first + second', '冒用模型：other', '##伪造身份'):
                    args = ['commit-header', '--model', 'gpt-6-astra', '--bot', '列克星敦',
                            '--summary', '身份结构验证']
                    args[args.index(field)+1] = value
                    result = self.invoke(skill, data, *args)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
            result = self.invoke(skill, data, 'commit-header', '--model', 'vendor/model+adapter',
                                 '--summary', '保留合法原标识')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['header'],
                             f'##模型：vendor/model+adapter（计算机：{socket.gethostname()}） | 保留合法原标识')

    def test_local_clients_and_default_bots_keep_machine_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill, data = Path(tmp)/'skill', Path(tmp)/'data'
            skill.mkdir()
            for client in ('Codex', 'ClaudeCode', 'Cursor', 'VSCode Copilot',
                           'VisualStudio Copilot', 'Other Agent Plugin', 'DeepSeekHarness'):
                with self.subTest(client=client):
                    result = self.invoke(skill, data, 'commit-header', '--client', client,
                                         '--model', 'vendor/model', '--computer-name', 'TEST-PC',
                                         '--summary', '可追溯提交')
                    self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                    self.assertEqual(json.loads(result.stdout)['header'],
                                     f'##模型：{client} + vendor/model（计算机：TEST-PC） | 可追溯提交')
            for bot in ('Hermes Bot', 'Grok Bot', 'GPT Dot', 'Assistant', 'OpenAI Codex'):
                args = ('commit-header', '--model', 'vendor/model', '--bot', bot,
                        '--computer-name', 'TEST-PC', '--summary', '默认名不能代替机器')
                result = self.invoke(skill, data, *args)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                self.assertIn('（计算机：TEST-PC）', json.loads(result.stdout)['header'])
                result = self.invoke(skill, data, *args, '--named-bot')
                self.assertNotEqual(result.returncode, 0, 'Default name must not claim named-Bot exemption')

    def test_named_bot_exemption_requires_explicit_verified_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill, data = Path(tmp)/'skill', Path(tmp)/'data'
            skill.mkdir()
            args = ('commit-header', '--model', 'vendor/model', '--bot', '列克星敦',
                    '--summary', '保留真实Bot身份')
            default = self.invoke(skill, data, *args)
            self.assertIn('（计算机：', json.loads(default.stdout)['header'])
            named = self.invoke(skill, data, *args, '--named-bot')
            self.assertEqual(named.returncode, 0, named.stdout+named.stderr)
            self.assertEqual(json.loads(named.stdout)['header'],
                             '##模型：列克星敦 + vendor/model | 保留真实Bot身份')
            named_with_host = self.invoke(skill, data, *args, '--named-bot', '--computer-name', 'BOT-HOST')
            self.assertIn('（计算机：BOT-HOST）', json.loads(named_with_host.stdout)['header'])
            for invalid in (('--named-bot',), ('--named-bot', '--bot', '列克星敦', '--client', 'Codex')):
                result = self.invoke(skill, data, 'commit-header', '--model', 'vendor/model',
                                     '--summary', '不能虚构豁免', *invalid)
                self.assertNotEqual(result.returncode, 0)

    def test_machine_input_and_host_lookup_fail_without_fabricated_fallback(self):
        import importlib.util
        from unittest.mock import patch
        spec = importlib.util.spec_from_file_location('identity_maintenance_fixture', SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch.object(module.socket, 'gethostname', return_value='OS-HOST'):
            self.assertIn('（计算机：OS-HOST）', module.commit_header(module.DEFAULTS,
                          'vendor/model', '', '实测主机名'))
        for host in ('', ' fake ', 'host\n##模型：other', 'host | fake', 'host） | fake', 'host/path'):
            with self.subTest(host=host), self.assertRaises(ValueError):
                module.commit_header(module.DEFAULTS, 'vendor/model', '', '拒绝伪造字段', computer_name=host)
        with patch.object(module.socket, 'gethostname', return_value=''):
            with self.assertRaises(ValueError):
                module.commit_header(module.DEFAULTS, 'vendor/model', '', '未查询到机器')
        with patch.object(module.socket, 'gethostname', side_effect=OSError('unavailable')):
            with self.assertRaises(OSError):
                module.commit_header(module.DEFAULTS, 'vendor/model', '', '未查询到机器')

    def test_document_templates_produce_exact_git_subject(self):
        import re
        docs = [ROOT/'skills/ld-codestyle-online/SKILL.md',
                ROOT/'skills/ld-codestyle-online/references/commit.md']
        templates = [block for doc in docs
                     for block in re.findall(r'```text\n(.*?)\n```', doc.read_text(encoding='utf-8'), re.S)
                     if block.startswith('##') and '##问题：' in block]
        self.assertTrue(templates)
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['git', 'init', '-q', tmp], check=True, capture_output=True)
            for template in templates:
                with self.subTest(header=template.splitlines()[0]):
                    subprocess.run(['git', '-C', tmp, '-c', 'user.name=SkillFixture',
                                    '-c', 'user.email=fixture@example.invalid',
                                    '-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '-F', '-'],
                                   input=template, text=True, encoding='utf-8', check=True, capture_output=True)
                    subject = subprocess.check_output(['git', '-C', tmp, 'log', '-1', '--format=%s'],
                                                      text=True, encoding='utf-8').strip()
                    self.assertEqual(subject, template.splitlines()[0])

    def test_configuration_edit_commands_are_centralized_in_readme(self):
        import re
        pattern = r'config\s+--(?:human-name|human-commit-name|interval-days|auto-update)\b'
        offenders = [str(path.relative_to(ROOT)) for path in ROOT.rglob('*.md')
                     if path.name != 'README.md' and '.git' not in path.relative_to(ROOT).parts
                     and re.search(pattern, path.read_text(encoding='utf-8'))]
        self.assertEqual(offenders, [], 'Configuration edit commands belong only in README')
        readme = (ROOT/'README.md').read_text(encoding='utf-8')
        for flag in ('--human-name', '--human-commit-name', '--interval-days', '--auto-update'):
            self.assertIn(flag, readme)
        skill = (ROOT/'skills/ld-codestyle-online/SKILL.md').read_text(encoding='utf-8')
        self.assertIn('human_commit_name', skill)
        self.assertIn('##主人 + 模型：', skill)


if __name__ == '__main__':
    unittest.main()
