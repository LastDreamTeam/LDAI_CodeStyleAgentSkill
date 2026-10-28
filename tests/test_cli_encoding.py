# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Validate the machine-readable CLI protocol independently of host console encoding.
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/ld-codestyle-online/scripts/maintain.py'


class CliEncodingTests(unittest.TestCase):
    def invoke(self, skill, data, encoding, *args):
        env = dict(os.environ, PYTHONUTF8='0', PYTHONIOENCODING=encoding)
        return subprocess.run(
            [sys.executable, '-B', str(SCRIPT), '--skill-root', str(skill),
             '--data-root', str(data), *args],
            env=env, capture_output=True, timeout=10)

    def decode(self, result, expected_code):
        self.assertEqual(result.returncode, expected_code, repr(result.stderr))
        self.assertTrue(result.stdout.isascii(), repr(result.stdout))
        # OpenAI: Consumers can parse JSON bytes as UTF-8 without guessing a Windows code page.
        return json.loads(result.stdout)

    def test_unicode_preferences_and_header_survive_legacy_console_encodings(self):
        for encoding in ('cp936', 'cp1252'):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                skill, data = root / 'skill', root / 'data'
                skill.mkdir()
                initial = self.decode(self.invoke(skill, data, encoding, 'show'), 0)
                self.assertEqual(initial['config']['human_commit_name'], '主人')
                display = '褪色的梦🌙'
                configured = self.decode(self.invoke(
                    skill, data, encoding, 'config', '--human-commit-name', display), 0)
                self.assertEqual(configured['config']['human_commit_name'], display)
                config_file = Path(configured['data_dir']) / 'config.json'
                persisted = config_file.read_text(encoding='utf-8')
                self.assertIn(display, persisted)
                before = config_file.read_bytes()
                summary = '保留中文与 Unicode 🌙 café'
                result = self.decode(self.invoke(
                    skill, data, encoding, 'commit-header', '--visibility', 'private', '--client', 'Codex',
                    '--model', 'vendor/model', '--computer-name', 'TEST-PC',
                    '--summary', summary, '--mixed-human'), 0)
                self.assertEqual(result['header'],
                                 f'##{display} + 模型：Codex + vendor/model PC:TEST-PC | {summary}')
                self.assertEqual(config_file.read_bytes(), before)

    def test_unicode_filesystem_errors_remain_machine_readable(self):
        for encoding in ('cp936', 'cp1252'):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                skill, data = root / 'skill', root / '并发任务🌙'
                skill.mkdir()
                initial = self.invoke(skill, data, 'utf-8', 'show')
                self.assertEqual(initial.returncode, 0, repr(initial.stderr))
                lock = Path(json.loads(initial.stdout)['data_dir']) / 'maintenance.lock'
                lock.write_text('keep active lock', encoding='utf-8')
                result = self.decode(self.invoke(skill, data, encoding, 'show'), 1)
                self.assertEqual(result['status'], 'error')
                self.assertIn(data.name, result['error'])
                self.assertEqual(lock.read_text(encoding='utf-8'), 'keep active lock')


if __name__ == '__main__':
    unittest.main()
