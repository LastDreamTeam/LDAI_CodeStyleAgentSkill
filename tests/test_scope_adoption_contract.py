# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 核对 0.6.1 的采用判定、流程让位与触发描述，不冒称外部 Agent 已遵守。"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ld-codestyle-online"


def read(path):
    """OpenAI: 以 UTF-8 读取文档，缺文件时直接暴露路径。"""
    return path.read_text(encoding="utf-8")


def frontmatter_description(text):
    """OpenAI: 取 SKILL.md frontmatter 的 description，宿主据此隐式选用技能。"""
    match = re.search(r'^description:\s*"(.*)"\s*$', text.split("\n---", 1)[0], re.M)
    return match.group(1) if match else ""


class ScopeAdoptionContractTests(unittest.TestCase):
    """OpenAI: 防止源码风格因“非 Unity”被跳过，也防止流程规则越过项目约定和当前指令。"""

    def test_adoption_signals_cover_first_party_non_unity_projects(self):
        """OpenAI: 采用信号必须可判定，且与 Unity 结构规则分开。"""
        entry = read(SKILL / "SKILL.md")
        rule = entry.split("4. **其余源码风格", 1)[1].split("\n5. ", 1)[0]
        for term in ("LD/LastDreamTeam", "AGENTS.md", "`LD:`", "`I<类型>Base`", "`.Agentic`",
                     "用户当次明确要求", "不论是否Unity", "第三方、他人或未采用项目只适用前两层"):
            with self.subTest(term=term):
                self.assertIn(term, rule)
        comments = read(SKILL / "references/comments.md")
        self.assertIn("LD/LastDreamTeam 一方仓库", comments.split("\n## ", 1)[0])
        self.assertIn("在已采用LD源码风格的一方代码", entry)

    def test_workflow_rules_yield_to_project_and_current_instruction(self):
        """OpenAI: 分支和两次合并请求是默认做法，按材料状态判断，不为凑次数拒绝。"""
        entry = read(SKILL / "SKILL.md")
        self.assertIn("5. **协作流程与写作约定**", entry)
        workflow = read(SKILL / "references/branch-workflow.md")
        intro = workflow.split("\n## ", 1)[0]
        for term in ("没有声明自己分支", "用户当前明确决定优先", "不新增提交、推送、合并或发布授权"):
            self.assertIn(term, intro)
        self.assertNotIn("技能源码仓库的 `main`", intro)
        for term in ("开始新任务", "同一任务在自己分支上续做", "仍须符合项目的合并审查规则",
                     "按材料状态算", "不为凑次数再拒绝一次", "没有 Issue/PR 机制", "作者段", "隐私检查"):
            with self.subTest(term=term):
                self.assertIn(term, workflow)
        self.assertIn("在线发布通道", read(ROOT / "CONTRIBUTING.md"))

    def test_review_disagreements_stay_inside_the_project(self):
        """OpenAI: 私有项目的审查记录不得追加到上游公开议题。"""
        entry = read(SKILL / "SKILL.md")
        review = entry.split("## 合并请求的技术审查", 1)[1].split("\n## ", 1)[0]
        for term in ("本项目的 PR/Issue", "脱敏", "获授权", "不把私有项目记录追加进上游公开议题"):
            self.assertIn(term, review)

    def test_description_names_core_triggers_within_host_budget(self):
        """OpenAI: 描述前置写代码、审查与交付触发词，长度保持在常见宿主上限内。"""
        description = frontmatter_description(read(SKILL / "SKILL.md"))
        self.assertTrue(description)
        self.assertLessEqual(len(description), 1024)
        for term in ("writing", "reviewing", "committing", "PRs", "Issues", "README", "##模型",
                     "Agentic/USER|MEMORY|DEBUG", "I<Type>Base", "LD/LastDreamTeam"):
            with self.subTest(term=term):
                self.assertIn(term, description)

    def test_installed_skill_docs_do_not_link_outside_the_skill(self):
        """OpenAI: Hermes 只装技能子目录，技能内相对链接不能跳出安装单元。"""
        for path in SKILL.rglob("*.md"):
            text = read(path)
            for target in re.findall(r"\]\(([^)\s]+)\)", text):
                if target.startswith(("http", "#", "mailto:")):
                    continue
                resolved = (path.parent / target.split("#", 1)[0]).resolve()
                with self.subTest(path=path.name, target=target):
                    self.assertTrue(str(resolved).startswith(str(SKILL.resolve())))


if __name__ == "__main__":
    unittest.main()
