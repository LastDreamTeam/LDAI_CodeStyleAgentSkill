# SPDX-License-Identifier: AGPL-3.0-only
"""Anthropic: 检查代码格式整理与插件必要改写规则的入口和验收契约，不冒充源码格式检查器。"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/ld-codestyle-online"


def read(path):
    """Anthropic: 按UTF-8读取文档，避免Windows默认代码页改变比较结果。"""
    return path.read_text(encoding="utf-8")


def section(text, heading):
    """Anthropic: 截取指定二级标题到下一个二级标题之间的正文，确保关键词落在正确小节。"""
    start = text.index("## " + heading + "\n")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


class FormatPluginContractTests(unittest.TestCase):
    """Anthropic: 防止后续改写把格式整理或插件改写登记弱化为可选建议。"""

    def test_format_rules_limit_scope_and_preserve_encoding(self):
        """Anthropic: 格式整理只覆盖本次改动，并保护编码、换行与受保护内容。"""
        spec = section(read(SKILL / "references/contract.md"), "代码格式整理")
        # Anthropic: 锁定容易被删掉的边界词，不把关键字存在解释成Agent已遵守。
        for term in (
            "交付要求", ".editorconfig", "dotnet format", "BOM", "CRLF/LF",
            "调试输出", "注释掉的废弃代码块", "[debug]", "只整理本次改动范围",
            "第三方或生成代码", "纯格式变更", "不夹带行为改动", "需授权",
        ):
            with self.subTest(term=term):
                self.assertIn(term, spec)

    def test_plugin_rewrite_requires_marker_external_ledger_and_reapply(self):
        """Anthropic: 必要侵入改写须最小化、就地标记、插件外登记并在升级后补回。"""
        spec = section(read(SKILL / "references/contract.md"), "插件纯净与必要改写")
        for term in (
            "默认保持原样", "wrapper/adapter", "确无项目侧方案", "最小改动",
            "项目侧改写点", "插件目录外登记", "AGENTS.md", "升级后补回",
            "上游已修复", "死机级", "登记不代替授权",
        ):
            with self.subTest(term=term):
                self.assertIn(term, spec)

    def test_entries_link_both_rules(self):
        """Anthropic: 执行入口、提交验收与公开说明都能找到两条规则。"""
        entries = {
            SKILL / "SKILL.md": ("references/contract.md#代码格式整理", "references/contract.md#插件纯净与必要改写"),
            SKILL / "references/commit.md": ("contract.md#代码格式整理", "contract.md#插件纯净与必要改写"),
            ROOT / "README.md": ("references/contract.md#代码格式整理", "references/contract.md#插件纯净与必要改写"),
            ROOT / "CONTRIBUTING.md": ("references/contract.md#代码格式整理", "references/contract.md#插件纯净与必要改写"),
        }
        for path, links in entries.items():
            text = read(path)
            for link in links:
                with self.subTest(entry=path.name, link=link):
                    self.assertIn(link, text)


if __name__ == "__main__":
    unittest.main()
