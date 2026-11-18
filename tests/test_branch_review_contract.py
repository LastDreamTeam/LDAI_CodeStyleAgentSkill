# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 核对分支时序与技术审查的文档契约及入口。"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ld-codestyle-online"
WORKFLOW = SKILL / "references" / "branch-workflow.md"
REVIEW = "合并请求的技术审查"


class BranchReviewContractTests(unittest.TestCase):
    """OpenAI: 在对应阶段内核对约束，避免无关段落恰好提到相同用词。"""

    def section(self, path, heading):
        """OpenAI: 提取一个二级标题的完整正文，缺文件或标题时指出对应入口。"""
        self.assertTrue(path.is_file(), path)
        content = path.read_text(encoding="utf-8")
        # OpenAI: 标题单独占行，下一节中的结论不能补偿本节缺少的门槛。
        match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", content, re.M | re.S)
        self.assertIsNotNone(match, f"{path.name} 缺少 {heading}")
        return match.group(1)

    def assert_mentions(self, section, *terms):
        """OpenAI: 分别报告缺少的措施，便于维护者核对被删改的规则。"""
        for term in terms:
            with self.subTest(term=term):
                self.assertTrue(term in section, f"缺少文档约定或入口：{term}")

    def test_release_branch_decision_protects_pending_work(self):
        """OpenAI: 主分支上的小修与已有改动都要交代用户答复及可做的调查。"""
        decision = self.section(WORKFLOW, "在发布分支动手前")
        self.assert_mentions(
            decision, "`main`", "`master`", "`release`", "小修", "询问", "答复",
            "实验性", "回滚成本", "只读调查", "未提交改动", "未推送提交",
            "带到新分支", "先推送到当前分支", "先验收", "本次", "`stash`", "`reset`",
            "保留本地改动", "强推", "重写已发布历史",
        )

    def test_branch_types_and_names_are_traceable(self):
        """OpenAI: 保护五类分支含义、双种命名结尾和历史分支边界。"""
        naming = self.section(WORKFLOW, "分支类型与命名")
        for kind, meaning in (("fix", "优化"), ("feature", "实验"), ("archive", "放弃"),
                              ("legacy", "存根"), ("bak", "备份")):
            with self.subTest(kind=kind):
                self.assertRegex(naming, rf"`{kind}`[^\n]*{meaning}")
        self.assert_mentions(
            naming, "全小写", "短横线", "YYMMDD", "ld-blueprint-add", "ld-fishnet-261111",
            "实际建立", "前缀", "用户", "Issue", "PR", "历史分支",
        )

    def test_first_request_submits_history_second_checks_the_same_version(self):
        """OpenAI: 将材料、合并条件和收尾分别约束在对应请求，避免一次请求直通。"""
        first = self.section(WORKFLOW, "第一次请求合并")
        second = self.section(WORKFLOW, "第二次请求合并")
        after = self.section(WORKFLOW, "合并之后")
        self.assert_mentions(
            first, "不合并", "签出点", "最新推送", "全部提交", "中间", "最终 diff",
            "Issue", "问题和边界", "PR", "验证结果", "未覆盖", "兼容性",
            "../SKILL.md#合并请求的技术审查",
        )
        self.assert_mentions(second, "用户", "Issue", "PR", "审查记录", "补齐", "冲突", "合并")
        self.assert_mentions(after, "合并版本", "影响范围", "未验", "关闭", "遗留", "Issue", "PR")

    def test_review_points_to_the_original_criteria(self):
        """OpenAI: 各项技术判断可直接回到原章节，审查入口独立于开发步骤。"""
        skill = SKILL / "SKILL.md"
        review = self.section(skill, REVIEW)
        content = skill.read_text(encoding="utf-8")
        self.assertLess(content.index(f"\n## {REVIEW}\n"), content.index("\n## 流程与验收\n"))
        for target in (
            "comments.md#执行委派与提交验收", "contract.md#模块结构与控制边界",
            "contract.md#插件纯净与必要改写", "contract.md#cinspector-与文档",
            "contract.md#代码格式整理", "directory-context.md#读取更新和权限",
            "commit.md#格式与工具",
        ):
            with self.subTest(target=target):
                self.assertIn(f"](references/{target})", review)

    def test_review_scope_authority_and_actual_verification(self):
        """OpenAI: 防止自审放行、安装状态免责、扩成全仓审计或误把结论当授权。"""
        review = self.section(SKILL / "SKILL.md", REVIEW)
        self.assert_mentions(
            review, "人类当前明确指令", "AGENTS.md", "区域 `README.md`", "本技能默认",
            "未安装", "直接依赖", "受影响调用者", "无关问题", "配对接口", "架构负责人",
            "结论和缺口清单", "自己的提交身份", "自审", "独立复审", "由人决定",
            "亲自运行", "语法检查", "项目编译", "测试", "文档契约测试", "作者自述", "未验",
            "执行侧", "合并前后", "读回", "暂定", "issues/27", "追加",
        )

    def test_published_entry_points_are_connected(self):
        """OpenAI: 仓内贡献者与技能使用者都能找到时序和技术审查正文。"""
        for path in (ROOT / "CONTRIBUTING.md", ROOT / "README.md"):
            content = path.read_text(encoding="utf-8")
            with self.subTest(entry=path.name):
                self.assert_mentions(content, "references/branch-workflow.md", "SKILL.md#合并请求的技术审查")
        self.assertIn("](references/branch-workflow.md)", (SKILL / "SKILL.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
