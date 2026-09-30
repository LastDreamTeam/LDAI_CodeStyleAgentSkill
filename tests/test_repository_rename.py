# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Pin new fetches to the canonical repository, retaining explicit rename compatibility.
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/ld-codestyle-online/scripts/maintain.py'
spec = importlib.util.spec_from_file_location('rename_maintenance', SCRIPT)
assert spec is not None and spec.loader is not None
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

CANONICAL = 'LastDreamTeam/LDAI_CodeStyleAgentSkill'
LEGACY = 'LastDreamTeam/LDCodeStyleAgentSkill'


class RepositoryRenameTests(unittest.TestCase):
    def test_version_fetch_uses_canonical_repository(self):
        payload = {'name': m.NAME, 'version': '0.2.0', 'repository': CANONICAL}
        with patch('urllib.request.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())) as request:
            self.assertEqual(m.fetch_version(), payload)
        url = request.call_args.args[0].full_url
        self.assertEqual(url, f'https://raw.githubusercontent.com/{CANONICAL}/main/skills/{m.NAME}/assets/version.json')


    def test_native_registry_accepts_old_and_new_exact_names_across_redirects(self):
        for source, prefix in [('github', ''), ('skills.sh', 'skills-sh/'), ('skills-sh', 'skills-sh/')]:
            for identity in (CANONICAL, LEGACY):
                for url_repo in (CANONICAL, LEGACY):
                    with self.subTest(source=source, identity=identity, url_repo=url_repo):
                        m.validate_native_source({
                            'source': source, 'identifier': f'{prefix}{identity}/skills/{m.NAME}',
                            'metadata': {'source_url': f'https://github.com/{url_repo}/tree/' + 'a'*40 + f'/skills/{m.NAME}'},
                        })

    def test_native_alias_does_not_accept_forks_unpinned_urls_or_lookalikes(self):
        official_url = f'https://github.com/{CANONICAL}/tree/' + 'a'*40 + f'/skills/{m.NAME}'
        valid = {'source': 'github', 'identifier': f'{CANONICAL}/skills/{m.NAME}',
                 'metadata': {'source_url': official_url}}
        invalid: list[dict] = [dict(valid, identifier=f'other/LDAI_CodeStyleAgentSkill/skills/{m.NAME}'),
                   dict(valid, identifier=f'{LEGACY}/skills/{m.NAME}-extra'),
                   dict(valid, source='unknown')]
        for url in (official_url.replace('/tree/' + 'a'*40, '/tree/main'),
                    official_url.replace('github.com/', 'github.com.evil.invalid/'),
                    official_url.replace(CANONICAL, 'other/LDAI_CodeStyleAgentSkill')):
            invalid.append(dict(valid, metadata={'source_url': url}))
        for entry in invalid:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                m.validate_native_source(entry)


    def test_backup_carries_new_templates_without_private_state(self):
        import tempfile
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill, data = root/'skill', root/'data'
            (skill/'templates').mkdir(parents=True)
            data.mkdir()
            (skill/'templates/module-memory.md').write_text('Shared template', encoding='utf-8')
            (skill/'templates/auth.json').write_text('do not include', encoding='utf-8')
            archive = m.backup_skill(skill, data)
            with zipfile.ZipFile(archive) as saved:
                self.assertIn('templates/module-memory.md', saved.namelist())
                self.assertNotIn('templates/auth.json', saved.namelist())


if __name__ == '__main__':
    unittest.main()
