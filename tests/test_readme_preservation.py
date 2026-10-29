# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 验证旧模块索引正文的明确承接位置，不将业务迁移假定为已发生。"""
from pathlib import Path
import unittest

SKILL = Path(__file__).resolve().parents[1] / 'skills/ld-codestyle-online'


class ReadmePreservationTests(unittest.TestCase):
    """OpenAI: 文档契约只证明模板和规则保全入口，不能代替真实项目迁移验收。"""

    def test_old_architecture_content_has_explicit_readme_destinations(self):
        """OpenAI: 三类旧正文必须有承接槽位，不能仅把章节名或链接搬来。"""
        text = (SKILL / 'templates/module-readme.md').read_text(encoding='utf-8')
        for title in ('## 依赖、禁止的反向依赖与插件边界', '## 场景、预制件、资源与装配前提',
                      '## 生命周期、数据流、线程与清理'):
            with self.subTest(title=title):
                self.assertIn(title, text)
        spec = (SKILL / 'references/agentic.md').read_text(encoding='utf-8')
        self.assertIn('不得只搬章节标题或链接', spec)
        self.assertIn('拿不准则保留', spec)


if __name__ == '__main__':
    unittest.main()
