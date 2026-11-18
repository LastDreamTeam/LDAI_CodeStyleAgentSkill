# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 发布的写作入口必须随技能安装，并保护本仓已有的可用示例。"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "ld-codestyle-online"


class PublicWritingTests(unittest.TestCase):
    """OpenAI: 区分文档契约与人类实际读懂或产品实测的证据。"""

    def test_new_issue_defaults_are_scoped_to_the_target_project(self):
        """OpenAI: 同时保护仓库例外、可筛选的标题和追加标签的语义。"""
        guide = (SKILL / "references/public-writing.md").read_text(encoding="utf-8")
        issue = guide.split("## 新建 Issue", 1)[1].split("\n## ", 1)[0]
        for expected in ("项目已有", "P0", "P1", "P2", "P3", "一件事", "查重",
                         "原有标签", "颜色", "历史 Issue", "[P1][保存]"):
            with self.subTest(expected=expected):
                self.assertIn(expected, issue)

    def test_receipt_and_public_images_have_distinct_evidence_rules(self):
        """OpenAI: 回执可灵活表达，图片须维持实际受众和原画面约束。"""
        guide = (SKILL / "references/interaction.md").read_text(encoding="utf-8")
        receipt = guide.split("## 给人类的最终回执", 1)[1].split("\n## ", 1)[0]
        for expected in ("高权重建议", "两张", "未验证", "没有修前图", "commit.md#"):
            self.assertIn(expected, receipt)
        privacy = (SKILL / "references/commit.md").read_text(encoding="utf-8")
        for expected in ("原尺寸", "不裁剪", "Bot 名", "未登录", "亲眼"):
            self.assertIn(expected, privacy)

    def test_root_readme_and_english_entry_preserve_the_user_path(self):
        """OpenAI: 从两种语言验证安装路径，并避免丢失现有源码对照、流程图与历史索引。"""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        english = (ROOT / "README.en.md").read_text(encoding="utf-8")
        self.assertIn("(README.en.md)", readme.split("## 使用前后", 1)[0])
        self.assertIn("(README.md)", english)
        for target in ("skills/install.md", "Agentic/DEBUG.md"):
            self.assertIn("(" + target + ")", english)
            self.assertIn("(" + target + ")", readme)
        # OpenAI: 保护可复制的两种源码示例，允许项目日后自行调整配色、排版和渲染服务。
        for expected in ("```mermaid", "```csharp", "ToChartMilliseconds", "OnDisable", "7 个断言"):
            self.assertIn(expected, readme)
        guide = (SKILL / "references/public-writing.md").read_text(encoding="utf-8")
        homepage = guide.split("## 根 README", 1)[1]
        for expected in ("快速开始", "已有多语言", "English", "徽章", "示意", "配色"):
            self.assertIn(expected, homepage)

    def test_pilot_records_a_real_handoff_and_its_limits(self):
        """OpenAI: 防止后续把 Python 夹具或仅看客户端画面改写成跨仓实测。"""
        record = (ROOT / "Agentic/DEBUG.md").read_text(encoding="utf-8")
        section = record.split("## Go 服务端与 Windows 桌面客户端接手试点", 1)[1].split("\n## ", 1)[0]
        # OpenAI: 固定可追溯版本的形状，允许后续维护者按新的真实复跑更新版本。
        self.assertGreaterEqual(len(set(re.findall(r"`([0-9a-f]{40})`", section))), 2)
        for expected in ("根 README", "Agentic/USER.md", "Agentic/MEMORY.md", "已退役", "Agentic/DEBUG.md",
                         "go version -m", "一键连接", "登录后使用聊天", "同节点后续心跳", "未测", "独立 AI"):
            self.assertIn(expected, section)

    def test_workflow_entry_points_ship_inside_the_skill(self):
        """OpenAI: 跟随发布入口在安装目录内找得到规则，贡献者能找到同一份正文。"""
        entry = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        for target in ("public-writing.md", "interaction.md#给人类的最终回执", "branch-workflow.md"):
            with self.subTest(target=target):
                self.assertIn("references/" + target, entry)
                self.assertIn("references/" + target, contributing)
                # OpenAI: 附带章节名的链接也必须落到随安装分发的实际标题。
                filename, _, anchor = target.partition("#")
                page = (SKILL / "references" / filename).read_text(encoding="utf-8")
                if anchor:
                    self.assertRegex(page, re.compile("^## " + re.escape(anchor) + "$", re.M))
