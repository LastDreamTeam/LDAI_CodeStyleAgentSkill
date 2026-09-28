# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Execute the published installation example, without a real Agent profile.
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / 'skills/install.md'
NAME = 'ld-codestyle-online'


class InstallGuideTests(unittest.TestCase):
    def link_example(self):
        self.assertTrue(GUIDE.is_file(), 'The Agent-readable installation entry must exist')
        match = re.search(r'<!-- ld-link-example:start -->\s*```python\n(.*?)\n```',
                          GUIDE.read_text(encoding='utf-8'), re.S)
        self.assertIsNotNone(match, 'The local-link example must be executable and testable')
        return match.group(1)

    def invoke(self, code, source, target):
        return subprocess.run([sys.executable, '-B', '-c', code, str(source), str(target)],
                              capture_output=True, text=True, encoding='utf-8', timeout=10)

    def test_document_installs_complete_link_and_default_config(self):
        code = self.link_example()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'agent-skills' / NAME
            source = ROOT / 'skills' / NAME
            result = self.invoke(code, source, target)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(target.resolve(), source.resolve())
            self.assertTrue((target/'references/contract.md').is_file())
            env = dict(os.environ, LD_CODESTYLE_DATA_ROOT=str(Path(tmp)/'data'))
            result = subprocess.run([sys.executable, '-B', str(target/'scripts/maintain.py'), 'show'],
                                    env=env, capture_output=True, text=True, encoding='utf-8', timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            config = json.loads(result.stdout)['config']
            self.assertEqual(config['human_name'], 'LD')
            self.assertEqual(config['interval_days'], 7)

    def test_same_install_is_reused_without_overwrite(self):
        code = self.link_example()
        with tempfile.TemporaryDirectory() as tmp:
            source = ROOT / 'skills' / NAME
            target = Path(tmp) / NAME
            for _ in range(2):
                result = self.invoke(code, source, target)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'present')
            self.assertEqual(target.resolve(), source.resolve())

    def test_existing_directory_and_dangling_link_are_preserved(self):
        code = self.link_example()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = ROOT / 'skills' / NAME
            target = root / 'existing' / NAME
            target.mkdir(parents=True)
            sentinel = target / 'human.txt'
            sentinel.write_text('keep human work', encoding='utf-8')
            result = self.invoke(code, source, target)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'keep human work')
            dangling = root / 'dangling' / NAME
            dangling.parent.mkdir()
            dangling.symlink_to(root / 'absent', target_is_directory=True)
            result = self.invoke(code, source, dangling)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(dangling.is_symlink())
            self.assertEqual(os.readlink(dangling), str(root/'absent'))


if __name__ == '__main__':
    unittest.main()
