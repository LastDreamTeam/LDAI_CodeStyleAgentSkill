# SPDX-License-Identifier: AGPL-3.0-only
"""Anthropic: 核对 0.6.1 的采用判定、流程让位与触发描述，不冒称外部 Agent 已遵守。"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ld-codestyle-online"


def read(path):
    """Anthropic: 以 UTF-8 读取文档，缺文件时直接暴露路径。"""
    return path.read_text(encoding="utf-8")


def frontmatter_description(text):
    """Anthropic: 取 SKILL.md frontmatter 的 description，宿主据此隐式选用技能。"""
    match = re.search(r'^description:\s*"(.*)"\s*$', text.split("\n---", 1)[0], re.M)
    return match.group(1) if match else ""


class ScopeAdoptionContractTests(unittest.TestCase):
    """Anthropic: 防止源码风格因“非 Unity”被跳过，也防止流程规则越过项目约定和当前指令。"""

    def test_adoption_signals_cover_first_party_non_unity_projects(self):
        """Anthropic: 采用信号必须可判定，且与 Unity 结构规则分开。"""
        entry = read(SKILL / "SKILL.md")
        rule = entry.split("4. **其余源码风格", 1)[1].split("\n5. ", 1)[0]
        for term in ("LD/LastDreamTeam", "AGENTS.md", "`LD:`", "`I<类型>Base`", "`.Agentic`",
                     "用户当次明确要求", "不论是否Unity", "第三方或他人项目须明确采用", "不能仅凭"):
            with self.subTest(term=term):
                self.assertIn(term, rule)
        comments = read(SKILL / "references/comments.md")
        self.assertIn("LD/LastDreamTeam 一方仓库", comments.split("\n## ", 1)[0])
        self.assertIn("在已采用LD源码风格的一方代码", entry)

    def test_workflow_rules_yield_to_project_and_current_instruction(self):
        """OpenAI: 保护先交审查、再由人决定的两个阶段，已有当前授权可追溯。"""
        entry = read(SKILL / "SKILL.md")
        self.assertIn("5. **协作流程与写作约定**", entry)
        workflow = read(SKILL / "references/branch-workflow.md")
        intro = workflow.split("\n## ", 1)[0]
        for term in ("没有声明自己分支", "用户当前明确决定优先", "不新增提交、推送、合并或发布授权"):
            self.assertIn(term, intro)
        self.assertNotIn("技能源码仓库的 `main`", intro)
        # OpenAI: 新任务已有改动的归属和实际合并的决定，分别由对应阶段的授权覆盖。
        for term in ("开始新任务", "只要有未提交改动或未推送提交", "同一任务在自己分支上续做", "仍须符合项目的合并审查规则",
                     "第一次", "再次明确", "没有 Issue/PR 机制", "作者段", "隐私检查"):
            with self.subTest(term=term):
                self.assertIn(term, workflow)
        self.assertIn("在线发布通道", read(ROOT / "CONTRIBUTING.md"))

    def test_review_disagreements_stay_inside_the_project(self):
        """Anthropic: 私有项目的审查记录不得追加到上游公开议题。"""
        entry = read(SKILL / "SKILL.md")
        review = entry.split("## 合并请求的技术审查", 1)[1].split("\n## ", 1)[0]
        # OpenAI: 对外追加保留 #27 的历史入口，分享条件须与原项目记录同时可见。
        for term in ("本项目的 PR/Issue", "脱敏", "获授权", "issues/27", "追加可公开", "原可见范围"):
            self.assertIn(term, review)

    def test_description_names_core_triggers_within_host_budget(self):
        """Anthropic: 描述前置写代码、审查与交付触发词，长度保持在常见宿主上限内。"""
        description = frontmatter_description(read(SKILL / "SKILL.md"))
        self.assertTrue(description)
        self.assertLessEqual(len(description), 1024)
        # OpenAI: 宿主可能截短描述，所以把适用项目放在前面，并避免 XML 形状的元数据。
        self.assertNotRegex(description, r"[<>]")
        for term in ("writing", "reviewing", "committing", "PRs", "Issues", "README",
                     "Markdown memory", "Base interfaces", "LD/LastDreamTeam"):
            with self.subTest(term=term):
                self.assertIn(term, description)

    def test_installed_skill_docs_do_not_link_outside_the_skill(self):
        """Anthropic: Hermes 只装技能子目录，技能内相对链接不能跳出安装单元。"""
        for path in SKILL.rglob("*.md"):
            text = read(path)
            for target in re.findall(r"\]\(([^)\s]+)\)", text):
                if target.startswith(("http", "#", "mailto:")):
                    continue
                # OpenAI: 按路径组成部分判定归属，同名前缀的兄弟目录不随技能安装。
                resolved = (path.parent / target.split("#", 1)[0]).resolve()
                with self.subTest(path=path.name, target=target):
                    self.assertTrue(resolved.is_relative_to(SKILL.resolve()))
                    self.assertTrue(resolved.exists())


if __name__ == "__main__":
    unittest.main()
