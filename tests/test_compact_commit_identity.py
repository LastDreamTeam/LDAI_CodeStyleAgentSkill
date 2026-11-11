# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: Exercise concise identity output through the real CLI with synthetic fixtures."""
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
        """OpenAI: 使用临时数据根运行提交头 CLI，并以 UTF-8 收集结果。"""
        return subprocess.run(
            [sys.executable, '-B', str(SCRIPT), '--data-root', str(data),
             'commit-header', *args], capture_output=True, text=True,
            encoding='utf-8', timeout=10)

    def test_private_codex_alias_uses_short_framework_and_explicit_pc(self):
        """OpenAI: 仅缩短明确 Codex 框架旧称，实际档位和显式 PC 保留。"""
        with tempfile.TemporaryDirectory() as tmp:
            for name in ('Codex', 'OpenAI Codex', 'OpenAICodex'):
                with self.subTest(name=name):
                    result = self.invoke(tmp, '--visibility', 'private', '--client', name,
                                         '--model', 'fixture-model-v2', '--reasoning-effort', 'high',
                                         '--pc', 'TEST-PC', '--summary', '修复输入')
                    self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                    rendered = json.loads(result.stdout)
                    self.assertEqual(rendered['header'],
                                     '##模型：Codex fixture-model-v2 high PC:TEST-PC | 修复输入')
                    self.assertNotIn('+', rendered['identity'])

    def test_private_rejects_generic_names_unknown_models_and_placeholders(self):
        """OpenAI: 笼统 GPT/Sol、产品、路由别名和占位文本不能充作完整型号。"""
        with tempfile.TemporaryDirectory() as tmp:
            for model in ('', 'GPT', 'Sol', 'GPT Sol', 'DSH', 'DSH Bot', 'Codex',
                          'OpenAI Codex', 'OpenAICodex', 'OpenAI',
                          'xAI', 'DeepSeek', 'ChatGPT', 'DeepSeekHarness', 'Claude',
                          'VSCode Copilot', 'VisualStudio Copilot', 'Other Agent Plugin',
                          'unknown', 'auto', 'default', 'latest', '未知', 'model',
                          'vendor/auto', '<实际模型标识>', '[待确认]'):
                with self.subTest(model=model):
                    result = self.invoke(tmp, '--visibility', 'private', '--client', 'Codex',
                                         '--model', model, '--reasoning-effort', 'high',
                                         '--summary', '拒绝不明模型')
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertNotIn('"header"', result.stdout)

    def test_exact_model_identifier_is_preserved_and_embedded_effort_is_not_duplicated(self):
        """OpenAI: 完整型号原样保留，明确一致的尾部档位只在公开输出剥离。"""
        with tempfile.TemporaryDirectory() as tmp:
            for model in ('vendor/Exact-Model-v2.1-high', 'GPT Sol6.1', 'GPT Sol6.1 xhigh',
                          'vendor/model:20b', 'vendor/model-v2@release-3'):
                with self.subTest(model=model):
                    result = self.invoke(tmp, '--visibility', 'private', '--client', 'OpenAI Codex',
                                         '--model', model, '--reasoning-effort', 'xhigh',
                                         '--summary', '保留准确型号')
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    expected = model if model.endswith(' xhigh') else model + ' xhigh'
                    self.assertEqual(json.loads(result.stdout)['identity'], 'Codex ' + expected)
                    public = self.invoke(tmp, '--visibility', 'public', '--model', model,
                                         '--reasoning-effort', 'xhigh', '--summary', '公开准确型号')
                    self.assertEqual(public.returncode, 0, public.stdout + public.stderr)
                    expected = model[:-6] if model.endswith(' xhigh') else model
                    self.assertEqual(json.loads(public.stdout)['identity'], expected)
            # OpenAI: 不把任意连字符后缀猜成档位，也不靠删除非法字符伪造另一个型号。
            for model, effort in (('GPT Sol6.1 xhigh', 'high'), ('vendor/model+adapter', 'high')):
                result = self.invoke(tmp, '--visibility', 'private', '--client', 'Codex',
                                     '--model', model, '--reasoning-effort', effort,
                                     '--summary', '拒绝冲突标识')
                self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_public_rejects_computer_fields_without_echo_and_allows_ordinary_pc_text(self):
        """OpenAI: 防止公开摘要回填主机结构，同时允许正常 PC/RPC 业务文字。"""
        with tempfile.TemporaryDirectory() as tmp:
            for summary in ('PC:TEST-PC', '修复输入 PC:TEST-PC', 'pc：TEST-PC', 'PC : TEST-PC'):
                with self.subTest(summary=summary):
                    result = self.invoke(tmp, '--visibility', 'public', '--omit-public-identity',
                                         '--summary', summary)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertNotIn('TEST-PC', result.stdout + result.stderr)
            for summary in ('修复PC端输入', '修复RPC:超时'):
                result = self.invoke(tmp, '--visibility', 'public', '--omit-public-identity',
                                     '--summary', summary)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)['header'], summary)

    def test_private_bot_combines_framework_and_nickname_without_model_or_default_pc(self):
        """OpenAI: 实跑 CLI 的框架与昵称组合，并拒绝普通会话昵称冒充 Bot。"""
        with tempfile.TemporaryDirectory() as tmp:
            result = self.invoke(tmp, '--visibility', 'private', '--client', 'Hermes',
                                 '--bot', 'FixtureBot', '--named-bot', '--summary', '真实执行者')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['identity'], 'Hermes-FixtureBot')
            result = self.invoke(tmp, '--visibility', 'private', '--client', 'Codex',
                                 '--model', 'fixture-model-v2', '--reasoning-effort', 'none',
                                 '--summary', '没有推理控制')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)['identity'], 'Codex fixture-model-v2 none')
            for args in (('--bot', 'FixtureBot'), ('--named-bot',),
                         ('--bot', 'Codex', '--named-bot')):
                result = self.invoke(tmp, '--visibility', 'private', '--client', 'Hermes',
                                     '--model', 'fixture-model-v2', '--reasoning-effort', 'high',
                                     '--summary', '不能冒充Bot', *args)
                self.assertNotEqual(result.returncode, 0, result.stdout)

    def test_git_subject_and_reused_identity_preserve_repository_configuration(self):
        """OpenAI: 临时 Git 仓库验证复用身份、邮箱保全及单次覆盖不会更改全局或历史。"""
        with tempfile.TemporaryDirectory() as tmp:
            repo, data = Path(tmp) / 'repo', Path(tmp) / 'data'
            repo.mkdir()
            env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
            env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)

            def git(*args, input=None):
                """OpenAI: 在隔离临时仓库执行 Git，返回去掉末尾换行的标准输出。"""
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
                                  '--model', 'fixture-model-v2', '--reasoning-effort', 'high',
                                  '--summary', '修复输入')
            self.assertEqual(private.returncode, 0, private.stdout + private.stderr)
            private_result = json.loads(private.stdout)
            # OpenAI: 使用生成器返回的同一 identity，避免作者名与首行采用两套格式。
            git('-c', 'user.name=' + private_result['identity'], '-c', 'commit.gpgsign=false',
                'commit', '--allow-empty', '-F', '-',
                input=private_result['header'] + '\n\n##问题：输入异常。\n\n##解决：修复并验证。\n')
            self.assertEqual(git('log', '-1', '--format=%s%n%an%n%cn'),
                             private_result['header'] + '\n' + private_result['identity']
                             + '\n' + private_result['identity'])
            self.assertEqual(git('log', '-1', '--format=%ae%n%ce'),
                             'fixture@example.invalid\nfixture@example.invalid')
            first_commit = git('rev-parse', 'HEAD')
            first_object = git('cat-file', 'commit', first_commit)
            public = self.invoke(data, '--visibility', 'public', '--model', 'fixture-model-v2',
                                 '--reasoning-effort', 'high', '--pc', 'TEST-PC',
                                 '--summary', '修复公开入口')
            self.assertEqual(public.returncode, 0, public.stdout + public.stderr)
            public_result = json.loads(public.stdout)
            self.assertEqual(public_result, {'header': '##模型：fixture-model-v2 | 修复公开入口',
                                             'identity': 'fixture-model-v2', 'visibility': 'public'})
            git('-c', 'user.name=' + public_result['identity'], '-c', 'commit.gpgsign=false',
                'commit', '--allow-empty', '-F', '-',
                input=public_result['header'] + '\n\n##问题：入口异常。\n\n##解决：修复并验证。\n')
            self.assertEqual(git('log', '-1', '--format=%an%n%cn'), 'fixture-model-v2\nfixture-model-v2')
            self.assertEqual((repo / '.git/config').read_bytes(), config_before)
            self.assertEqual(git('cat-file', 'commit', first_commit), first_object)


if __name__ == '__main__':
    unittest.main()
