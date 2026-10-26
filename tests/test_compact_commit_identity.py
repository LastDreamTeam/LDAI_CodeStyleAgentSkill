# SPDX-License-Identifier: AGPL-3.0-only
"""Exercise compact identity output through the real CLI with synthetic fixtures."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/ld-codestyle-online/scripts/maintain.py'


class CompactCommitIdentityTests(unittest.TestCase):
    def invoke(self, data, *args):
        return subprocess.run(
            [sys.executable, '-B', str(SCRIPT), '--data-root', str(data),
             'commit-header', *args], capture_output=True, text=True,
            encoding='utf-8', timeout=10)

    def test_private_codex_alias_uses_short_product_and_pc(self):
        with tempfile.TemporaryDirectory() as tmp:
            for flag in ('--client', '--bot'):
                for name in ('Codex', 'OpenAI Codex', 'OpenAICodex'):
                    with self.subTest(flag=flag, name=name):
                        result = self.invoke(tmp, '--visibility', 'private', flag, name,
                                             '--model', 'fixture-model-v2',
                                             '--computer-name', 'TEST-PC', '--summary', '修复输入')
                        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                        self.assertEqual(json.loads(result.stdout)['header'],
                                         '##模型：Codex + fixture-model-v2 PC:TEST-PC | 修复输入')

    def test_private_rejects_product_names_and_unknown_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            for model in ('', 'Codex', 'OpenAI Codex', 'OpenAICodex', 'OpenAI',
                          'xAI', 'DeepSeek', 'ChatGPT', 'DeepSeekHarness',
                          'VSCode Copilot', 'VisualStudio Copilot', 'Other Agent Plugin',
                          'unknown', 'auto', 'default', 'latest', '未知',
                          '<实际模型标识>', 'FixtureBot'):
                with self.subTest(model=model):
                    result = self.invoke(tmp, '--visibility', 'private', '--bot', 'FixtureBot',
                                         '--model', model, '--computer-name', 'TEST-PC',
                                         '--summary', '拒绝不明模型')
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertNotIn('"header"', result.stdout)

    def test_exact_model_identifier_is_never_shortened_with_product(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self.invoke(tmp, '--visibility', 'private', '--client', 'OpenAI Codex',
                                 '--model', 'vendor/exact-model-v2+adapter',
                                 '--computer-name', 'TEST-PC', '--summary', '保留准确型号')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['header'],
                             '##模型：Codex + vendor/exact-model-v2+adapter PC:TEST-PC | 保留准确型号')


    def test_public_rejects_compact_computer_field_without_echo(self):
        with tempfile.TemporaryDirectory() as tmp:
            for summary in ('PC:TEST-PC', '修复输入 PC:TEST-PC', 'pc：TEST-PC', 'PC : TEST-PC'):
                with self.subTest(summary=summary):
                    result = self.invoke(tmp, '--visibility', 'public', '--summary', summary)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertNotIn('"header"', result.stdout)
                    self.assertNotIn('TEST-PC', result.stdout + result.stderr)
            for summary in ('修复PC端输入', '修复RPC:超时'):
                result = self.invoke(tmp, '--visibility', 'public', '--summary', summary)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)['header'], summary)

    def test_private_rejects_compact_field_inside_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            for field in ('--model', '--client', '--bot'):
                for value in ('PC:EXTRA', 'name PC：EXTRA', 'name pc:EXTRA'):
                    args = ['--visibility', 'private', '--model', 'fixture-model-v2',
                            '--computer-name', 'TEST-PC', '--summary', '拒绝额外身份字段']
                    if field == '--model':
                        args[args.index(field) + 1] = value
                    else:
                        args += [field, value]
                    with self.subTest(field=field, value=value):
                        result = self.invoke(tmp, *args)
                        self.assertNotEqual(result.returncode, 0, result.stdout)
                        self.assertNotIn('"header"', result.stdout)

    def test_private_bot_and_unknown_product_names_remain_exact(self):
        with tempfile.TemporaryDirectory() as tmp:
            for args, identity in (
                (('--bot', 'FixtureBot', '--named-bot'), 'FixtureBot + fixture-model-v2'),
                (('--client', 'CustomProduct'), 'CustomProduct + fixture-model-v2 PC:TEST-PC'),
            ):
                host = () if '--named-bot' in args else ('--computer-name', 'TEST-PC')
                result = self.invoke(tmp, '--visibility', 'private', *args,
                                     '--model', 'fixture-model-v2', *host, '--summary', '真实执行者')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)['header'], f'##模型：{identity} | 真实执行者')
            for product in ('Codex', 'OpenAI Codex', 'OpenAICodex'):
                result = self.invoke(tmp, '--visibility', 'private', '--bot', product,
                                     '--named-bot', '--model', 'fixture-model-v2', '--summary', '不可冒用豁免')
                self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_git_subject_and_single_commit_author_do_not_change_repository_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo, data = Path(tmp) / 'repo', Path(tmp) / 'data'
            repo.mkdir()
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith('GIT_')}
            env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)

            def git(*args, input=None):
                return subprocess.run(['git', '-C', str(repo), *args], input=input,
                                      capture_output=True, text=True, encoding='utf-8',
                                      env=env, check=True, timeout=10).stdout.strip()

            git('init', '-q')
            git('config', 'user.name', 'SharedAccountFixture')
            git('config', 'user.email', 'fixture@example.invalid')
            config_before = (repo / '.git/config').read_bytes()
            inherited = dict(env, GIT_AUTHOR_NAME='InheritedAuthorFixture',
                             GIT_COMMITTER_NAME='InheritedCommitterFixture')
            for field, expected in (('GIT_AUTHOR_IDENT', 'InheritedAuthorFixture'),
                                    ('GIT_COMMITTER_IDENT', 'InheritedCommitterFixture')):
                effective = subprocess.run(
                    ['git', '-C', str(repo), '-c', 'user.name=Codex', 'var', field],
                    env=inherited, capture_output=True, text=True, encoding='utf-8',
                    check=True, timeout=10).stdout
                self.assertTrue(effective.startswith(expected + ' <fixture@example.invalid>'))
            private = self.invoke(data, '--visibility', 'private', '--client', 'OpenAICodex',
                                  '--model', 'fixture-model-v2', '--computer-name', 'TEST-PC',
                                  '--summary', '修复输入')
            self.assertEqual(private.returncode, 0, private.stdout + private.stderr)
            private_header = json.loads(private.stdout)['header']
            git('-c', 'user.name=Codex', '-c', 'commit.gpgsign=false', 'commit', '--allow-empty',
                '-F', '-', input=private_header + '\n\n##问题：输入异常。\n\n##解决：修复并验证。\n')
            self.assertEqual(git('log', '-1', '--format=%s%n%an%n%cn'),
                             private_header + '\nCodex\nCodex')
            first_commit = git('rev-parse', 'HEAD')
            first_object = git('cat-file', 'commit', first_commit)
            public = self.invoke(data, '--visibility', 'public', '--client', 'OpenAI Codex',
                                 '--model', 'fixture-model-v2', '--computer-name', 'TEST-PC',
                                 '--summary', '修复公开入口')
            self.assertEqual(public.returncode, 0, public.stdout + public.stderr)
            self.assertEqual(json.loads(public.stdout), {'header': '修复公开入口', 'visibility': 'public'})
            git('-c', 'user.name=PublicAuthorFixture', '-c', 'commit.gpgsign=false', 'commit',
                '--allow-empty', '-F', '-', input='修复公开入口\n\n##问题：入口异常。\n\n##解决：修复并验证。\n')
            self.assertEqual(git('log', '-1', '--format=%s%n%an%n%cn'),
                             '修复公开入口\nPublicAuthorFixture\nPublicAuthorFixture')
            self.assertEqual((repo / '.git/config').read_bytes(), config_before)
            self.assertEqual(git('cat-file', 'commit', first_commit), first_object)


if __name__ == '__main__':
    unittest.main()
