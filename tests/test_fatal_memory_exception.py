# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 核对严重故障的文档优先级，不冒称自动判断或真实项目已修复。"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/ld-codestyle-online'


class FatalMemoryExceptionTests(unittest.TestCase):
    """OpenAI: 致命级例外必须在入口、详细规则及每份可复制模板中可见。"""

    def test_fatal_exception_overrides_scope_in_every_entry(self):
        """OpenAI: 平时就地记，致命级移到相关范围必读入口，不机械提升到项目根。"""
        paths = [ROOT / 'README.md', ROOT / 'CONTRIBUTING.md', SKILL / 'SKILL.md',
                 *(SKILL / 'references' / name for name in
                   ('directory-context.md', 'agentic.md', 'contract.md')),
                 *(SKILL / 'templates' / f'module-{kind}.md'
                   for kind in ('readme', 'memory', 'user', 'debug'))]
        for path in paths:
            text = path.read_text(encoding='utf-8')
            # OpenAI: 模板必须单独说明优先级，不能只在链接目标补例外。
            visible = text.split('\n## ', 1)[0] if path.parent.name == 'templates' else text
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                for term in ('出事那块目录自己的 README/Agentic', '致命级', '优先',
                             '凡是动这块东西的人都得先看', 'XR 那套文件里最外面的那一份',
                             '不是项目根', '死机级', '触发条件', '一手证据', '版本/提交'):
                    self.assertIn(term, visible)
                for stale in ('两个模块以上', '不是按 bug 严重性归类',
                              '不能按严重性', '不因 bug 严重', '而非按严重性',
                              '一律写到最高层', '项目根/全局入口'):
                    self.assertNotIn(stale, text)

    def test_fatal_categories_and_local_example_do_not_hide_the_exception(self):
        """OpenAI: 明列损坏风险，并限定普通路径示例不能把局部死机经验降回低层。"""
        spec = (SKILL / 'references/directory-context.md').read_text(encoding='utf-8')
        routing = spec.split('### 记在哪里', 1)[-1].split('## 每份文件头部', 1)[0]
        for term in ('死机', '崩溃', '掉数据', '工程/存档损坏', 'XR',
                     '即使只涉及 FunA', '必读入口', '不是固定移到项目根',
                     '触发条件', '一手证据', '死机级', '单一有效正文'):
            with self.subTest(term=term):
                self.assertIn(term, routing)


if __name__ == '__main__':
    unittest.main()
