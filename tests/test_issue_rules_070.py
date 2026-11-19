# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 锁定 0.7.0 对 #33、#34、#36、#38 的入口与验收约定。"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ld-codestyle-online"


def section(path, heading):
    content = path.read_text(encoding="utf-8")
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", content, re.M | re.S)
    if match is None:
        raise AssertionError(f"{path.name} 缺少 {heading}")
    return match.group(1)


class IssueRules070Tests(unittest.TestCase):
    """OpenAI: 规则要写进参考页，技能入口也必须能发现，避免只改一处。"""

    def assert_mentions(self, text, *terms):
        for term in terms:
            with self.subTest(term=term):
                self.assertIn(term, text)

    def test_receipt_reports_results_and_real_tables(self):
        """OpenAI: #38 回执只报结果；要表格时用可渲染表，按 Issue 则逐条列出。"""
        receipt = section(SKILL / "references" / "interaction.md", "给人类的最终回执")
        self.assert_mentions(
            receipt,
            "默认只交结果",
            "怎么修",
            "部分验通",
            "可渲染",
            "字符手画",
            "逐条表",
            "| 序号 | 场景 |",
            "多行事项表的首列写序号",
            "首列使用可点到原单的 Issue 编号",
            "成功/失败",
            "开放/关闭",
            "不作为所有任务的固定模板",
        )
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("interaction.md#给人类的最终回执", skill)
        self.assertIn("默认只报结果", skill)

    def test_issue_closeout_is_discoverable_and_covers_three_cases(self):
        """OpenAI: #34 先核验再勾选后关闭，并覆盖漏关、待合并、仍有缺口。"""
        closeout = section(SKILL / "references" / "branch-workflow.md", "任务范围内的 Issue 必须收尾")
        self.assert_mentions(
            closeout,
            "漏关",
            "不扫无关 Issue",
            "先核验",
            "勾选",
            "已关闭",
            "待合并",
            "未完成",
            "旧修复漏关",
            "仅在分支",
            "仍有缺口",
        )
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("branch-workflow.md#任务范围内的-issue-必须收尾", skill)
        after = section(SKILL / "references" / "branch-workflow.md", "合并之后")
        self.assertNotIn("酌情关闭", after)

    def test_foreground_desktop_releases_pointer_immediately(self):
        """OpenAI: #36 前台占用用完立即归还；入口指向交互页，不把细则只写在别处。"""
        desktop = section(SKILL / "references" / "interaction.md", "前台桌面操作用完立即释放")
        self.assert_mentions(
            desktop,
            "Computer Use",
            "立即",
            "鼠标",
            "发回执",
            "失败",
            "取消",
            "不关闭用户的应用",
            "不能报已释放",
            "后台",
        )
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("interaction.md#前台桌面操作用完立即释放", skill)

    def test_acceptance_files_stay_in_the_project(self):
        """OpenAI: #33 开发和验收文件只放项目目录，这是默认约束。"""
        files = section(SKILL / "references" / "contract.md", "工作准备与验收文件")
        self.assert_mentions(
            files,
            "默认约束",
            "项目目录",
            "桌面",
            "系统目录",
            "跨仓",
            "一个验收入口",
            "不授权清理历史遗留",
        )
        skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("contract.md#工作准备与验收文件", skill)


if __name__ == "__main__":
    unittest.main()
