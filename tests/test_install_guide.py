# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Execute the published installation example, without a real Agent profile.
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / 'skills/install.md'
NAME = 'ld-codestyle-online'
SOURCE = ROOT / 'skills' / NAME


def run_python(args, **environment):
    """OpenAI: 以 UTF-8 交换子进程的标准流，保留安装失败时的原始诊断。"""
    # OpenAI: 管道两端要约定同一编码。单设父进程的 encoding 会误读 Windows 子进程的本地代码页。
    env = dict(os.environ, **environment, PYTHONIOENCODING='utf-8')
    return subprocess.run([sys.executable, '-B', *args], env=env, capture_output=True,
                          encoding='utf-8', timeout=10)


class InstallGuideTests(unittest.TestCase):
    """OpenAI: 在隔离目录中验证安装文档对新链接、同源入口及已有内容的处理。"""

    def symlink_or_skip(self, link, destination):
        """OpenAI: 创建测试用目录符号链接，只在 Windows 明确报告缺少该特权时跳过用例。"""
        try:
            link.symlink_to(destination, target_is_directory=True)
        except OSError as exc:
            # OpenAI: 1314 是本次创建操作的特权错误，访问被拒、路径错误等需要原样暴露。
            if os.name == 'nt' and exc.winerror == 1314:
                self.skipTest('Creating a directory symlink requires privilege (WinError 1314)')
            raise

    def create_junction(self, link, destination):
        """OpenAI: 用 Windows PowerShell 在测试的新路径创建真实目录联接。"""
        self.assertFalse(os.path.lexists(link))
        # OpenAI: 通过子进程环境传递路径，PowerShell 将含空格的路径作为一个参数处理。
        command = ('New-Item -ItemType Junction -Path $env:LD_TEST_LINK '
                   '-Target $env:LD_TEST_SOURCE -ErrorAction Stop | Out-Null')
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', command],
                       env=dict(os.environ, LD_TEST_LINK=str(link), LD_TEST_SOURCE=str(destination)),
                       check=True, timeout=15)
        self.assertEqual(link.lstat().st_reparse_tag, stat.IO_REPARSE_TAG_MOUNT_POINT)

    def link_example(self):
        """Anthropic: 从安装文档提取可执行的链接脚本，缺失时说明文档入口损坏。"""
        self.assertTrue(GUIDE.is_file(), 'The Agent-readable installation entry must exist')
        match = re.search(r'<!-- ld-link-example:start -->\s*```python\n(.*?)\n```',
                          GUIDE.read_text(encoding='utf-8'), re.S)
        self.assertIsNotNone(match, 'The local-link example must be executable and testable')
        return match.group(1)

    def invoke(self, target, source=SOURCE):
        """OpenAI: 让独立解释器对指定源和发现入口执行安装页原文。"""
        return run_python(['-c', self.link_example(), str(source), str(target)])

    def assert_conflict(self, target):
        """OpenAI: 确认安装脚本识别了已有入口的冲突。"""
        result = self.invoke(target)
        # OpenAI: 只有预期诊断能证明进入了保护分支，其他异常同样可能返回退出码 1。
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(result.stderr.strip(), 'Existing target preserved; inspect the conflict')

    def assert_default_config(self, target, root):
        """OpenAI: 从接入后的路径读取技能内容及隔离数据目录的新安装默认值。"""
        # OpenAI: 真实CLI必须经宿主发现路径运行，避免只验证源目录能被读取。
        self.assertTrue((target / 'references/contract.md').is_file())
        result = run_python([str(target / 'scripts/maintain.py'), 'show'],
                            LD_CODESTYLE_DATA_ROOT=str(root / 'data'))
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)['config']
        self.assertEqual(config['human_name'], 'LD')
        self.assertEqual(config['interval_days'], 1)
        self.assertTrue(config['auto_update'])

    def test_document_installs_complete_link_and_default_config(self):
        """OpenAI: 验证完整链接可用并加载每日自动更新的新安装默认值。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # OpenAI: 在同一测试卷单独探测创建特权，随后文档脚本的任何失败都要报告。
            self.symlink_or_skip(root / 'probe', SOURCE)
            target = root / 'agent-skills' / NAME
            result = self.invoke(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'linked')
            self.assertTrue(target.is_symlink() and target.samefile(SOURCE))
            self.assert_default_config(target, root)
            # OpenAI: 第二次调用必须复用第一次创建的同一链接条目。
            before = target.lstat()
            result = self.invoke(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'present')
            self.assertTrue(os.path.samestat(before, target.lstat()))
            self.assertTrue(target.samefile(SOURCE))

    def test_existing_directory_is_preserved(self):
        """OpenAI: 普通目录的冲突保护在没有符号链接特权的用户下也必须运行。"""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / NAME
            target.mkdir()
            sentinel = target / 'human.txt'
            sentinel.write_text('keep human work', encoding='utf-8')
            self.assert_conflict(target)
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'keep human work')

    def test_existing_file_is_preserved(self):
        """OpenAI: 同名文件占用发现入口时保留原始字节。"""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / NAME
            target.write_bytes(b'human work')
            self.assert_conflict(target)
            self.assertEqual(target.read_bytes(), b'human work')

    def test_dangling_symlink_is_preserved(self):
        """OpenAI: 悬空目录符号链接继续保留其原指向。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dangling = root / NAME
            self.symlink_or_skip(dangling, root / 'absent')
            original_target = os.readlink(dangling)
            self.assert_conflict(dangling)
            self.assertTrue(dangling.is_symlink())
            self.assertEqual(os.readlink(dangling), original_target)
            # OpenAI: A missing leaf cannot normalize Windows 8.3 aliases by itself.
            self.assertTrue(dangling.resolve().parent.samefile(root))
            self.assertEqual(dangling.resolve().name, 'absent')
            self.assertFalse(dangling.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows directory junction')
    def test_same_junction_is_reused_without_symlink_privilege(self):
        """OpenAI: 经已存在的同源 Windows 联接复用完整技能并读取默认配置。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / NAME
            self.create_junction(target, SOURCE)
            before = target.lstat()
            result = self.invoke(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'present')
            self.assertTrue(os.path.samestat(before, target.lstat()))
            self.assertTrue(target.samefile(SOURCE))
            self.assert_default_config(target, root)

    @unittest.skipUnless(os.name == 'nt', 'Windows directory junction')
    def test_wrong_and_dangling_junction_is_preserved(self):
        """OpenAI: 指向其他目录的联接在目标存在及消失后都保留原指向。"""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / NAME
            with tempfile.TemporaryDirectory(dir=tmp) as other:
                self.create_junction(target, Path(other))
                original_target = os.readlink(target)
                self.assert_conflict(target)
                self.assertTrue(target.samefile(other))
            # OpenAI: 仅释放临时源，发现入口仍占用；可在真实悬空联接上检查防覆盖逻辑。
            self.assertFalse(target.exists())
            self.assert_conflict(target)
            self.assertEqual(os.readlink(target), original_target)
            self.assertEqual(target.lstat().st_reparse_tag, stat.IO_REPARSE_TAG_MOUNT_POINT)

    def test_unicode_failure_is_readable(self):
        """OpenAI: 父环境指定其他编码时，子进程的真实中文路径错误也能严格按 UTF-8 读取。"""
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, PYTHONIOENCODING='ascii'):
            root = Path(tmp)
            result = self.invoke(root / NAME, root / '缺少源目录')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('缺少源目录', result.stderr)


if __name__ == '__main__':
    unittest.main()
