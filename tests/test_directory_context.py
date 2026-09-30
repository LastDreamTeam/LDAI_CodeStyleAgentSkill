# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Validate the published, provider-neutral directory-context bundle and its links.
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/ld-codestyle-online'


class DirectoryContextTests(unittest.TestCase):
    def test_manifest_and_entry_are_consistent(self):
        manifest = json.loads((SKILL/'assets/version.json').read_text(encoding='utf-8'))
        entry = (SKILL/'SKILL.md').read_text(encoding='utf-8')
        self.assertEqual(manifest['repository'], 'LastDreamTeam/LDAI_CodeStyleAgentSkill')
        self.assertIn('version: ' + manifest['version'], entry)
        self.assertIn('references/directory-context.md', entry)
        for kind in ('memory', 'user', 'readme'):
            path = SKILL/f'templates/module-{kind}.md'
            self.assertTrue(path.is_file())
            self.assertIn('作用域', path.read_text(encoding='utf-8'))

    def test_markdown_relative_links_resolve(self):
        for path in ROOT.rglob('*.md'):
            if '.git' in path.parts:
                continue
            for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                link = link.split('#', 1)[0]
                if not link or '://' in link or link.startswith('mailto:'):
                    continue
                with self.subTest(file=path.relative_to(ROOT).as_posix(), link=link):
                    self.assertTrue((path.parent/link).exists())

    def test_bundle_has_no_case_only_path_collisions(self):
        paths = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
                 if '.git' not in p.parts and '__pycache__' not in p.parts]
        self.assertEqual(len(paths), len({p.casefold() for p in paths}))

    def test_spec_keeps_user_intent_and_legacy_file_protection(self):
        text = (SKILL/'references/directory-context.md').read_text(encoding='utf-8')
        for required in ('MEMORY.md', 'USER.md', 'README.md', 'Readme.md', 'AgentDocs/',
                         '一次性', '未来设想', '不覆盖、不改名、不自动改写', '私有记忆',
                         '脚本与资产', '只读', '兄弟', '推断', '.meta'):
            self.assertIn(required, text)


    def test_cleanup_authority_is_explicit_in_entry_spec_and_templates(self):
        paths = [SKILL/'SKILL.md', SKILL/'references/directory-context.md',
                 *(SKILL/f'templates/module-{kind}.md' for kind in ('memory', 'user', 'readme'))]
        for path in paths:
            text = path.read_text(encoding='utf-8')
            with self.subTest(path=path.name):
                for term in ('九成以上把握', '无损整合', '内容压缩', '专门获授权', '审计/辅助模型'):
                    self.assertIn(term, text)
        self.assertIn('否则直接忽略', (SKILL/'SKILL.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
