# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 检查日常与打扫的文档约定，不冒充自动源码审查。"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/ld-codestyle-online"


class HousekeepingTests(unittest.TestCase):
    """OpenAI: 防止旧物整理重新变成每次开发的前置工单。"""

    def test_plain_daily_rule_and_separate_cleanup(self):
        """OpenAI: 各入口必须区分日常记录和可分批的打扫。"""
        for path in (ROOT / "README.md", SKILL / "SKILL.md", SKILL / "references/directory-context.md"):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.name):
                for phrase in ("平时", "打扫", "出事那块目录自己的 README/Agentic", "凡是动这块东西的人都得先看", "死机级", "还差哪些"):
                    self.assertIn(phrase, text)
        spec = (SKILL / "references/directory-context.md").read_text(encoding="utf-8")
        for phrase in ("从哪搬到哪", "谁搬的", "旧代码缺注释", "旧脚本没按新规", "不是每次任务", "只读任务"):
            self.assertIn(phrase, spec)

    def test_replaced_routing_jargon_is_not_in_current_docs(self):
        """OpenAI: 防止入口删了复杂词、其他正文和模板仍保留判定链。"""
        for path in (ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "CHANGELOG.md", *SKILL.rglob("*.md")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                for stale in ("两个模块以上", "否则就地放着", "最低充分公共层", "最深公共父目录", "共同读取链"):
                    self.assertNotIn(stale, text)


if __name__ == "__main__":
    unittest.main()
