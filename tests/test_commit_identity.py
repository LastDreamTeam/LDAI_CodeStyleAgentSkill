# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Exercise contribution labels through the actual CLI, in isolated install slots.
import json
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
            args = ('commit-header', '--model', 'gpt-6-astra', '--bot', '列克星敦',
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
                             '##褪色的梦 + 模型：gpt-6-astra | 无Bot身份的实现')
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
                             '##模型：vendor/model+adapter | 保留合法原标识')

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
