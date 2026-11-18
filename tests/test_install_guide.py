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


def symlink_unavailable_reason():
    """OpenAI: 探测当前用户能否创建目录符号链接，返回不可用原因或 None。"""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            # OpenAI: Windows 缺少 SeCreateSymbolicLinkPrivilege 时抛 WinError 1314；只记录原因，不提权或改系统设置。
            (Path(tmp) / 'probe').symlink_to(Path(tmp), target_is_directory=True)
        except (OSError, NotImplementedError) as exc:
            return f'Directory symlink unavailable for this user: {type(exc).__name__} {getattr(exc, "winerror", "")}'
    return None


SYMLINK_SKIP = symlink_unavailable_reason()


@unittest.skipIf(SYMLINK_SKIP, SYMLINK_SKIP or '')
class InstallGuideTests(unittest.TestCase):
    """OpenAI: 执行安装文档中的链接示例；无链接权限的环境如实跳过，由 CI 的 Windows/POSIX runner 覆盖。"""

    def link_example(self):
        """OpenAI: 从安装文档提取可执行的链接脚本，缺失时说明文档入口损坏。"""
        self.assertTrue(GUIDE.is_file(), 'The Agent-readable installation entry must exist')
        match = re.search(r'<!-- ld-link-example:start -->\s*```python\n(.*?)\n```',
                          GUIDE.read_text(encoding='utf-8'), re.S)
        self.assertIsNotNone(match, 'The local-link example must be executable and testable')
        return match.group(1)

    def invoke(self, code, source, target):
        """OpenAI: 以独立解释器运行链接脚本，按 UTF-8 捕获输出避免本机代码页解码失败。"""
        return subprocess.run([sys.executable, '-B', '-c', code, str(source), str(target)],
                              capture_output=True, text=True, encoding='utf-8', timeout=10)

    def test_document_installs_complete_link_and_default_config(self):
        """OpenAI: 验证完整链接可用并加载每日自动更新的新安装默认值。"""
        # OpenAI: 真实CLI必须经宿主发现路径运行，避免只验证源目录能被读取。
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
            self.assertEqual(config['interval_days'], 1)
            self.assertTrue(config['auto_update'])

    def test_same_install_is_reused_without_overwrite(self):
        """OpenAI: 重复执行指向同一源的链接只报告 present，不覆盖已有安装。"""
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
        """OpenAI: 已有目录与悬空链接都保留原状并报错，保护人工内容。"""
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
            original_target = os.readlink(dangling)
            result = self.invoke(code, source, dangling)
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue(dangling.is_symlink())
            self.assertEqual(os.readlink(dangling), original_target)
            # OpenAI: A missing leaf cannot normalize Windows 8.3 aliases by itself.
            self.assertTrue(dangling.resolve().parent.samefile(root))
            self.assertEqual(dangling.resolve().name, 'absent')
            self.assertFalse(dangling.exists())


if __name__ == '__main__':
    unittest.main()
