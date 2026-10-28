# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 检查注释规范的入口和验收契约，不冒充业务代码注释分析器。"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/ld-codestyle-online"


class CommentContractTests(unittest.TestCase):
    """OpenAI: 防止后续规则改写再次把必填注释弱化为公共成员建议。"""

    def test_required_comments_are_reachable_and_block_delivery(self):
        """OpenAI: 每个执行入口都应链接同一强制规则，并覆盖旧代码和失败边界。"""
        spec_path = SKILL / "references/comments.md"
        self.assertTrue(spec_path.is_file(), "缺少强制注释与旧代码补齐规范")
        spec = spec_path.read_text(encoding="utf-8")
        # OpenAI: 锁定容易被旧措辞削弱的契约，不把关键字存在解释成Agent已遵守。
        for term in (
            "所有具名函数", "private", "构造函数", "Unity 生命周期", "局部函数",
            "<summary>", "<param name=", "<returns>", "<inheritdoc/>", "docstring",
            "核心原理实现位置", "//", "不是二选一", "旧脚本和旧项目",
            "整个第一方脚本", "不只检查 diff", "禁止提交", "不能报完成",
            "第三方", "生成代码", "[debug]", "不安装 hook/CI", "语义审查",
        ):
            with self.subTest(term=term):
                self.assertIn(term, spec)
        for relative in (
            "SKILL.md", "references/contract.md", "references/commit.md",
        ):
            with self.subTest(entry=relative):
                entry = (SKILL / relative).read_text(encoding="utf-8")
                self.assertIn("comments.md", entry)
                self.assertIn("强制", entry)
        for relative in ("README.md", "CONTRIBUTING.md"):
            with self.subTest(public_entry=relative):
                self.assertIn("references/comments.md", (ROOT / relative).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
