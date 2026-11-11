# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: Verify delivery examples with real temporary Git and existing question APIs.

These tests exercise isolated Git artifacts and the documented decision protocol; they do
not prove that every Agent follows the rules or that Unity compilation/business validation ran.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/ld-codestyle-online'
TEMPLATE = SKILL / 'templates/push-question.example.json'
PUSH_HEADING = '默认提交与推送边界：完整复现更新'
ASK_HEADING = '推送前无法安全决策时的求助'
PUSH_ANCHOR = '#默认提交与推送边界完整复现更新'
ASK_ANCHOR = '#推送前无法安全决策时的求助'
RESOURCE_GUID = '1234567890abcdef1234567890abcdef'

# OpenAI: This synthetic formal test consumes delivered source, metadata and resources together.
# It verifies a dependency closure in a clean checkout, not Unity compilation or scene behavior.
DELIVERY_TEST = '''"""OpenAI: Synthetic delivery contract; no Unity runtime verification is claimed."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]

class DeliveryTests(unittest.TestCase):
    def test_source_reference_and_metadata_preserve_asset_identity(self):
        """OpenAI: Require the source GUID reference and its imported resource metadata to agree."""
        area = ROOT / 'Assets/Feature'
        source = (area / 'FeaturePolicy.cs').read_text(encoding='utf-8')
        reference = re.search(r'SettingsGuid = "([0-9a-f]{32})"', source)
        self.assertIsNotNone(reference)
        # OpenAI: Missing metadata must fail even when the resource bytes themselves are present.
        metadata = (area / 'feature-settings.json.meta').read_text(encoding='utf-8')
        self.assertIn('guid: ' + reference.group(1), metadata)
        for name in ('Assets/Feature.meta', 'Assets/Feature/FeaturePolicy.cs.meta'):
            self.assertRegex((ROOT / name).read_text(encoding='utf-8'), r'guid: [0-9a-f]{32}')

    def test_default_resource_is_available_without_local_diagnostics(self):
        """OpenAI: Read the shipped settings from the checkout without any scratch-script fallback."""
        value = json.loads((ROOT / 'Assets/Feature/feature-settings.json').read_text(encoding='utf-8'))
        self.assertEqual(value, {'default_flow': 'legacy', 'enabled_by_explicit_flag': True})
'''

DELIVERY_FILES = {
    'Assets/Feature.meta': 'fileFormatVersion: 2\nguid: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\nfolderAsset: yes\n',
    'Assets/Feature/FeaturePolicy.cs': (
        '// OpenAI: Synthetic source fixture links settings by their stable asset GUID.\n'
        'namespace DeliveryFixture\n{\n'
        '    /// <summary>OpenAI: Declares the settings dependency used by this fixture.</summary>\n'
        '    public static class FeaturePolicy\n    {\n'
        f'        public const string SettingsGuid = "{RESOURCE_GUID}";\n'
        '    }\n}\n'),
    'Assets/Feature/FeaturePolicy.cs.meta': 'fileFormatVersion: 2\nguid: bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\n',
    'Assets/Feature/feature-settings.json': '{"default_flow":"legacy","enabled_by_explicit_flag":true}\n',
    'Assets/Feature/feature-settings.json.meta': f'fileFormatVersion: 2\nguid: {RESOURCE_GUID}\n',
    'tests/test_delivery.py': DELIVERY_TEST,
}


def section(path, heading):
    """OpenAI: Read one named Markdown section including its subsections, avoiding whole-file word matches."""
    text = path.read_text(encoding='utf-8')
    marker = '## ' + heading + '\n'
    start = text.index(marker) + len(marker)
    end = text.find('\n## ', start)
    return text[start:] if end == -1 else text[start:end]


def load_interaction():
    """OpenAI: Import the existing interaction protocol without starting its CLI or local web server."""
    spec = importlib.util.spec_from_file_location('push_scope_interaction', SKILL / 'scripts/interact.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PushScopeGitTests(unittest.TestCase):
    """OpenAI: Prove precise staging and pending-history boundaries in disposable repositories only."""

    def setUp(self):
        """OpenAI: Isolate Git identity/configuration and discard inherited repository-routing variables."""
        # OpenAI: GIT_DIR/GIT_INDEX_FILE must never redirect a temporary fixture into the real worktree.
        self.environment = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
        self.environment.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull,
                                GIT_TERMINAL_PROMPT='0', GIT_AUTHOR_NAME='Fixture',
                                GIT_AUTHOR_EMAIL='fixture@example.invalid', GIT_COMMITTER_NAME='Fixture',
                                GIT_COMMITTER_EMAIL='fixture@example.invalid', PYTHONDONTWRITEBYTECODE='1')

    def command(self, directory, arguments, expected=0, diagnostics=False):
        """OpenAI: Run an isolated command, optionally retaining stderr to verify the intended failure cause."""
        result = subprocess.run(arguments, cwd=directory, env=self.environment, capture_output=True,
                                text=True, encoding='utf-8', errors='replace', timeout=20)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout + result.stderr if diagnostics else result.stdout

    def git(self, directory, *arguments):
        """OpenAI: Run Git with fixture-local behavior, disabled signing and deterministic file conversion."""
        return self.command(directory, ['git', '-c', 'commit.gpgsign=false', '-c', 'core.autocrlf=false',
                                        *arguments])

    def write_fixture(self, directory, files):
        """OpenAI: Create only explicitly listed files beneath an already chosen temporary repository."""
        for name, content in files.items():
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content.encode('utf-8'))

    def create_repository(self, directory):
        """OpenAI: Clone a local fixture upstream so the worktree has a real, known origin/main baseline."""
        upstream, work = directory / 'upstream', directory / 'work'
        upstream.mkdir()
        self.git(upstream, 'init', '-b', 'main')
        self.write_fixture(upstream, {'notes/human.md': 'Previously committed human notes.\n',
                                      'ProjectSettings/ProjectVersion.txt': 'fixture-only; no Unity version claimed\n'})
        self.git(upstream, 'add', '--', 'notes/human.md', 'ProjectSettings/ProjectVersion.txt')
        self.git(upstream, 'commit', '-m', 'Fixture baseline')
        baseline = self.git(upstream, 'rev-parse', 'HEAD').strip()
        self.git(directory, 'clone', '--no-hardlinks', str(upstream), str(work))
        self.assertEqual(self.git(work, 'rev-parse', 'origin/main').strip(), baseline)
        return work, baseline

    def clean_checkout(self, source, destination):
        """OpenAI: Clone committed Git content without copying ignored/untracked files from the worktree."""
        self.git(destination.parent, 'clone', '--no-hardlinks', str(source), str(destination))
        self.assertEqual(self.git(destination, 'status', '--porcelain'), '')
        return destination

    def run_delivered_tests(self, checkout, expected=0):
        """OpenAI: Execute the formal test script from the clean checkout, never from the original fixture."""
        return self.command(checkout, [sys.executable, '-B', '-m', 'unittest', 'discover',
                                       '-s', 'tests', '-p', 'test_delivery.py'], expected=expected, diagnostics=True)

    def test_precise_candidates_preserve_dependencies_and_leave_local_materials(self):
        """OpenAI: Ship source/tests/resources/meta together while leaving one-off artifacts and human edits intact."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work, _ = self.create_repository(root)
            self.write_fixture(work, DELIVERY_FILES)
            local_only = {
                'scratch/probe-once.py': '# Synthetic one-off probe; not a formal test dependency.\n',
                'scratch/probe.log': 'Synthetic temporary output, not a secret.\n',
                'notes/user-draft.md': 'Uncommitted human draft must remain local.\n',
                'notes/human.md': 'Human changes in progress; do not revert or stage.\n',
            }
            self.write_fixture(work, local_only)
            before = {name: (work / name).read_bytes() for name in local_only}
            # OpenAI: The fixture uses a reviewed file list; neither broad staging nor cleanup is needed.
            self.git(work, 'add', '--', *sorted(DELIVERY_FILES))
            staged = set(filter(None, self.git(work, 'diff', '--cached', '--name-only', '-z').split('\0')))
            self.assertEqual(staged, set(DELIVERY_FILES))
            self.git(work, 'commit', '-m', 'Deliver source resources and formal validation')
            checkout = self.clean_checkout(work, root / 'delivery')
            self.run_delivered_tests(checkout)
            for name, content in DELIVERY_FILES.items():
                with self.subTest(delivered=name):
                    self.assertEqual((checkout / name).read_bytes(), content.encode('utf-8'))
            for name, content in before.items():
                with self.subTest(local=name):
                    self.assertEqual((work / name).read_bytes(), content)
                    if name != 'notes/human.md':
                        self.assertFalse((checkout / name).exists())
            self.assertEqual((checkout / 'notes/human.md').read_text(encoding='utf-8'),
                             'Previously committed human notes.\n')
            self.assertIn(' M notes/human.md', self.git(work, 'status', '--porcelain', '--untracked-files=all'))
            self.assertEqual(self.git(checkout, 'status', '--porcelain'), '')

    def test_omitting_required_meta_breaks_clean_validation_without_deleting_local_file(self):
        """OpenAI: A negative clean-checkout case proves resource metadata is a real fixture dependency."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work, _ = self.create_repository(root)
            self.write_fixture(work, DELIVERY_FILES)
            omitted = 'Assets/Feature/feature-settings.json.meta'
            original = (work / omitted).read_bytes()
            self.git(work, 'add', '--', *sorted(name for name in DELIVERY_FILES if name != omitted))
            self.git(work, 'commit', '-m', 'Fixture intentionally omits a required metadata dependency')
            checkout = self.clean_checkout(work, root / 'incomplete-delivery')
            self.assertFalse((checkout / omitted).exists())
            failure = self.run_delivered_tests(checkout, expected=1)
            self.assertIn('FileNotFoundError', failure)
            self.assertIn('feature-settings.json.meta', failure)
            # OpenAI: Excluding a candidate from Git is not permission to delete its local evidence.
            self.assertEqual((work / omitted).read_bytes(), original)
            self.assertIn(omitted, self.git(work, 'ls-files', '--others', '--exclude-standard'))

    def test_all_pending_commits_reveal_artifact_absent_from_final_tree(self):
        """OpenAI: A later index-only removal does not erase an earlier artifact from the pending Git history."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            work, baseline = self.create_repository(root)
            path = 'scratch/one-off-output.txt'
            content = 'Synthetic disposable artifact; never a real credential.\n'
            self.write_fixture(work, {path: content})
            self.git(work, 'add', '--', path)
            self.git(work, 'commit', '-m', 'Fixture accidental artifact inclusion')
            first = self.git(work, 'rev-parse', 'HEAD').strip()
            artifact = (work / path).resolve()
            self.assertTrue(artifact.is_relative_to(work.resolve()))
            # OpenAI: Only remove this verified temporary path from the index; preserve local bytes.
            self.git(work, 'rm', '--cached', '--', path)
            self.git(work, 'commit', '-m', 'Fixture final tree stops tracking artifact')
            pending = self.git(work, 'rev-list', '--reverse', 'origin/main..HEAD').splitlines()
            self.assertEqual(len(pending), 2)
            self.assertEqual(pending[0], first)
            self.assertEqual(self.git(work, 'rev-parse', 'origin/main').strip(), baseline)
            self.assertNotIn(path, self.git(work, 'diff', '--name-only', 'origin/main..HEAD').splitlines())
            containing = [revision for revision in pending
                          if path in self.git(work, 'ls-tree', '-r', '--name-only', revision).splitlines()]
            self.assertEqual(containing, [first])
            checkout = self.clean_checkout(work, root / 'history-delivery')
            self.assertFalse((checkout / path).exists())
            self.assertEqual(self.git(checkout, 'show', first + ':' + path), content)
            self.assertEqual(artifact.read_bytes(), content.encode('utf-8'))


class PushQuestionTests(unittest.TestCase):
    """OpenAI: Verify the new example works with the existing two-choice and free-text answer contract."""

    def setUp(self):
        """OpenAI: Load the committed-format example and current interaction code without altering either."""
        self.interaction = load_interaction()
        self.question = json.loads(TEMPLATE.read_text(encoding='utf-8'))

    def test_example_contains_two_substantive_conditional_plans_and_no_fake_validation(self):
        """OpenAI: Keep the sample actionable without presenting synthetic verification as completed work."""
        validated = self.interaction.validate_question(self.question)
        self.assertEqual(set(validated), {'request_id', 'session_id', 'revision', 'title', 'question',
                                          'options', 'recommended_id'})
        self.assertEqual([item['id'] for item in validated['options']], ['preserve-default', 'migrate-default'])
        self.assertEqual(validated['recommended_id'], 'preserve-default')
        for option in validated['options']:
            with self.subTest(option=option['id']):
                self.assertNotIn(option['label'], ('继续', '取消', '稍后', '推送', '不推送'))
                for meaning in ('实施', '业务差别', '推荐理由'):
                    self.assertIn(meaning, option['detail'])
        self.assertIn('显式启用', validated['options'][0]['label'])
        self.assertIn('迁移验证', validated['options'][1]['label'])
        self.assertIn('不代表任何核查、迁移或测试已经发生', validated['question'])
        self.assertIn('实际提问前', validated['question'])
        self.assertIn('自由说明', validated['question'])

    def test_both_options_and_custom_text_round_trip_without_auto_approval(self):
        """OpenAI: Submit each real option and a third free-text plan through unmodified QuestionSession."""
        answers = [('preserve-default', '先维持兼容，补开关说明。'),
                   ('migrate-default', '确认业务范围后再执行迁移验证。'),
                   (None, '第三种方案：本次只交付独立修复，默认切换另排版本。')]
        for choice, text in answers:
            with self.subTest(choice=choice):
                session = self.interaction.QuestionSession(self.question, 60, 5)
                session.ready(session.identity())
                result = session.answer({**session.identity(), 'action': 'submitted',
                                         'choice_id': choice, 'text': text})
                self.assertEqual(result['outcome'], 'submitted')
                self.assertEqual(result['choice_id'], choice)
                self.assertEqual(result['text'], text)
                self.assertFalse(result['user_approved'])
                self.assertEqual(self.interaction.assess_nonresponse(result['outcome'])['decision'],
                                 'review_explicit_answer')

    def test_timeout_does_not_select_recommendation_or_release_pending_business_work(self):
        """OpenAI: Silence on an unresolved business-default decision keeps its dependent work deferred."""
        clock = [100.0]
        # OpenAI: A deterministic clock checks the timeout boundary without sleeping or running a UI.
        session = self.interaction.QuestionSession(self.question, 60, 5, clock=lambda: clock[0])
        session.ready(session.identity())
        self.assertIsNone(session.check())
        clock[0] = 160.0
        result = session.check()
        self.assertEqual(result['outcome'], 'timed_out')
        self.assertNotIn('choice_id', result)
        self.assertFalse(result['user_approved'])
        assessment = self.interaction.assess_nonresponse(
            result['outcome'], authorized=True, reversible=True, direction_clear=False,
            low_risk=False, needs_new_approval=True, depends_on_pending=True)
        self.assertEqual(assessment['decision'], 'defer_item_continue_independent')
        self.assertFalse(assessment['user_approved'])
        for outcome in ('native_required', 'local_ui_not_allowed', 'channel_required'):
            self.assertEqual(self.interaction.assess_nonresponse(outcome)['decision'], 'routed_not_assessed')


class PushScopeDocumentTests(unittest.TestCase):
    """OpenAI: Guard essential normative boundaries; text checks do not certify Agent compliance."""

    def test_delivery_contract_preserves_dependencies_local_files_and_full_history(self):
        """OpenAI: Locate delivery boundaries in their authoritative section rather than incidental mentions."""
        spec = section(SKILL / 'references/commit.md', PUSH_HEADING)
        # OpenAI: Small semantic groups supplement the executable Git cases; they are not an automatic gate.
        for meaning in ('干净检出', '保全必要依赖', '正式构建/测试脚本', '排除非必要副产物',
                        '.meta', 'GUID', '排除上传不等于删除本地文件', '不擅自删除',
                        '未经审查不得整体暂存', '全部待推送提交', '中间提交', '.gitignore'):
            with self.subTest(meaning=meaning):
                self.assertIn(meaning, spec)
        self.assertIn('不授权重写已发布历史', spec)
        privacy = section(SKILL / 'references/commit.md', '公开前隐私检查与脱敏')
        self.assertIn('全部待推送提交', privacy)
        self.assertIn('元数据', privacy)
        self.assertIn('后一提交删除秘密也不清除前一提交', privacy)

    def test_help_contract_requires_prior_work_real_alternatives_and_honest_waiting(self):
        """OpenAI: Preserve the investigation threshold, substantial alternatives and host-specific pause rules."""
        spec = section(SKILL / 'references/interaction.md', ASK_HEADING)
        self.assertRegex(spec, r'(?s)尽合理能力.*仍.*无法.*安全可靠决策')
        for meaning in ('业务', '默认行为', '已查/已试', '两种经过评估', '适用条件',
                        '用户自由解释', '取消/稍后', '支持询问且能异步/后台收答',
                        '不依赖该选择', '框架/容器不支持可用询问功能', '同一会话以文字',
                        '超时或没有可并行继续的任务', '暂停待决任务及受影响推送',
                        '不自动选择推荐项', '不虚构异步API'):
            with self.subTest(meaning=meaning):
                self.assertIn(meaning, spec)
        self.assertIn('../templates/push-question.example.json', spec)
        self.assertIn('不会为宿主安装异步询问能力', spec)

    def test_existing_entries_link_authoritative_sections_without_duplicated_rules(self):
        """OpenAI: Keep old execution entries connected to the new authoritative sections and cross-links."""
        commit = SKILL / 'references/commit.md'
        interaction = SKILL / 'references/interaction.md'
        self.assertIn(PUSH_ANCHOR, section(commit, '提交与推送前'))
        self.assertIn('interaction.md' + ASK_ANCHOR, section(commit, PUSH_HEADING))
        self.assertIn('commit.md' + PUSH_ANCHOR, section(interaction, ASK_HEADING))
        for heading in ('何时问，在哪里问', '没有回答：先评估，任务继续'):
            self.assertIn(ASK_ANCHOR, section(interaction, heading))
        for path in (ROOT / 'README.md', ROOT / 'CONTRIBUTING.md', SKILL / 'SKILL.md'):
            with self.subTest(entry=path.name):
                text = path.read_text(encoding='utf-8')
                self.assertIn('commit.md' + PUSH_ANCHOR, text)
                self.assertIn('interaction.md' + ASK_ANCHOR, text)


if __name__ == '__main__':
    unittest.main()
