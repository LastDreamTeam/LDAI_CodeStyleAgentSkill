# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Validate the published, provider-neutral directory-context bundle and its links.
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/ld-codestyle-online'


class DirectoryContextTests(unittest.TestCase):
    def test_manifest_and_entry_are_consistent(self):
        """OpenAI: 核对清单中的仓库/版本与技能入口一致，并检查各区域模板存在。"""
        manifest = json.loads((SKILL/'assets/version.json').read_text(encoding='utf-8'))
        entry = (SKILL/'SKILL.md').read_text(encoding='utf-8')
        self.assertEqual(manifest['repository'], 'LastDreamTeam/LDAI_CodeStyleAgentSkill')
        self.assertIn('version: ' + manifest['version'], entry)
        self.assertIn('references/directory-context.md', entry)
        for kind in ('memory', 'user', 'readme', 'debug'):
            path = SKILL/f'templates/module-{kind}.md'
            self.assertTrue(path.is_file())
            self.assertIn('作用域', path.read_text(encoding='utf-8'))

    def test_agentic_memory_layout_keeps_logical_owner_at_readme_level(self):
        """OpenAI: 验证共享记忆物理归位至 Agentic 时仍由 README 区域确定逻辑归属。"""
        spec = (SKILL/'references/directory-context.md').read_text(encoding='utf-8')
        entry = (SKILL/'SKILL.md').read_text(encoding='utf-8')
        for text in (spec, entry):
            for required in ('Agentic/MEMORY.md', 'Agentic/USER.md', 'Agentic/DEBUG.md',
                             'README 所在区域', '不扩大权限'):
                self.assertIn(required, text)
        for required in ('逻辑作用域', '物理存放', '跨区域索引', '单一有效正文',
                         '不得把兄弟目录', 'AgentDocs/', '迁移'):
            self.assertIn(required, spec)
        for stale in ('三份文档与这些脚本同层', '在Base控制区同层建立三份'):
            self.assertNotIn(stale, spec)
        for kind in ('memory', 'user'):
            template = (SKILL/f'templates/module-{kind}.md').read_text(encoding='utf-8')
            self.assertIn('逻辑作用域', template)
            self.assertIn('README 所在区域', template)
            self.assertIn('Agentic/', template)
        readme = (SKILL/'templates/module-readme.md').read_text(encoding='utf-8')
        for required in ('共享记忆声明', 'Agentic/MEMORY.md', 'Agentic/USER.md',
                         'Agentic/DEBUG.md', '同级区域上下文'):
            self.assertIn(required, readme)

    def test_debug_captures_user_workflow_and_post_delivery_verification(self):
        """OpenAI: 检查 DEBUG 模板覆盖用户复现流程、恢复步骤及推送合并后的验证状态。"""
        template = SKILL/'templates/module-debug.md'
        self.assertTrue(template.is_file(), 'Missing user-facing DEBUG workflow template')
        text = template.read_text(encoding='utf-8')
        for required in ('逻辑作用域', '用户原意', '前提', '步骤', '预期', '实际',
                         '版本', '环境', '恢复', '未验', '推送后', '合并后'):
            self.assertIn(required, text)
        spec = (SKILL/'references/directory-context.md').read_text(encoding='utf-8')
        for required in ('用户纠正', '流程修订', '推送后', '合并后', '未部署',
                         '不自动授权', '不能为了测试通过', '测试数据'):
            self.assertIn(required, spec)
        for path in (SKILL/'SKILL.md', SKILL/'references/commit.md'):
            entry = path.read_text(encoding='utf-8')
            for required in ('DEBUG', '推送后', '合并后'):
                self.assertIn(required, entry)

    def test_all_memory_templates_record_dates_and_change_identity(self):
        """OpenAI: 确认共享记忆模板和规范记录日期、条目变更类型及实际修改身份。"""
        spec = (SKILL/'references/directory-context.md').read_text(encoding='utf-8')
        for term in ('新增、修改、删除', '##模型：', '文件更新时间不等于验证日期',
                     '历史日期未知', '条目标识', '删除摘要', '实际模型标识'):
            self.assertIn(term, spec)
        for kind in ('readme', 'memory', 'user', 'debug'):
            text = (SKILL/f'templates/module-{kind}.md').read_text(encoding='utf-8')
            with self.subTest(kind=kind):
                for term in ('创建日期', '最近修改日期', '##模型：', '变更记录',
                             '新增/修改/删除', '条目标识', '实际模型标识'):
                    self.assertIn(term, text)
        index = (SKILL/'templates/module-readme.md').read_text(encoding='utf-8')
        for term in ('创建日期', '最近修改日期', '##模型：', '变更记录'):
            self.assertIn(term, index)

    def test_existing_memories_migrate_and_readme_header_is_self_contained(self):
        """OpenAI: 旧布局归专门打扫，日常记忆仍有可独立理解的入口。"""
        spec = (SKILL/'references/directory-context.md').read_text(encoding='utf-8')
        entry = (SKILL/'SKILL.md').read_text(encoding='utf-8')
        readme = (SKILL/'templates/module-readme.md').read_text(encoding='utf-8')
        header = readme.split('## 业务与边界', 1)[0]
        for text in (spec, entry):
            for required in ('平时', '打扫', '未安装本技能', 'README原有职责与权威索引'):
                self.assertIn(required, text)
        for required in ('未安装本技能', 'README原有职责与权威索引',
                         'Agentic/MEMORY.md', 'Agentic/USER.md', 'Agentic/DEBUG.md',
                         '同级区域上下文', '不是临时文件', '不得擅自删除或改作他用'):
            self.assertIn(required, header)
        for required in ('从哪搬到哪', '谁搬的', '还差哪些', '不是每次任务', '保留有效正文'):
            self.assertIn(required, spec)

    def test_each_file_header_stands_alone_for_an_unfamiliar_agent(self):
        """OpenAI: 逐种模板核对新 Agent 单独打开文件时可见的权限、作用域和来源提示。"""
        roles = {'readme': '区域地图', 'memory': '事实与经验',
                 'user': '用户意图', 'debug': '操作与测试流程'}
        for kind, role in roles.items():
            text = (SKILL/f'templates/module-{kind}.md').read_text(encoding='utf-8')
            header = text.split('\n## ', 1)[0]
            with self.subTest(kind=kind):
                for term in (role, '持久共享', '未安装本技能', '不在舰队或指挥系统',
                             '不是临时文件', '私有记忆', '不得擅自删除或改作他用',
                             '逻辑作用域', 'README', '当前任务授权', '先读',
                             '九成以上把握', '内容压缩', '专门获授权',
                             '日期', '实际模型', '来源', '不高于'):
                    self.assertIn(term, header)
                if kind != 'readme':
                    self.assertIn('../README.md', header)
                    self.assertIn('不只管Agentic', header)
        spec = (SKILL/'references/directory-context.md').read_text(encoding='utf-8')
        for term in ('每份文件头部', '不能只在 README', '旧文件', '保留有效正文',
                     '独立打开', '只读任务', '陌生Agent'):
            self.assertIn(term, spec)
        entry = (SKILL/'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('每份文件头部', entry)
        index = (SKILL/'templates/module-readme.md').read_text(encoding='utf-8')
        header = index.split('\n## ', 1)[0]
        for term in ('持久共享', '逻辑作用域', 'README', '未安装本技能',
                     '不得擅自删除或改作他用', '当前任务授权', '内容压缩'):
            self.assertIn(term, header)

    def test_recurrent_bug_lessons_require_verified_repair_and_preserve_slices(self):
        """OpenAI: 核对复发缺陷记录区分过程与已验证修复，并保留阶段性经验。"""
        spec = (SKILL/'references/directory-context.md').read_text(encoding='utf-8')
        section = spec.split('### 复发缺陷的修复经验闭环', 1)[-1].split('### USER.md', 1)[0]
        self.assertIn('### 复发缺陷的修复经验闭环', spec)
        for required in ('工作会话', '用户反馈', 'Git', '提交标题', 'diff',
                         '已验证修复后', '同一条目', '修复中途', '废弃/放弃',
                         '阶段性/番茄切片', '不必等待整项任务', '不等于长期稳定',
                         '未知就标未知', '未完成', 'DEBUG', '不删除'):
            with self.subTest(required=required):
                self.assertIn(required, section)
        template = (SKILL/'templates/module-memory.md').read_text(encoding='utf-8')
        for required in ('复发缺陷', '已验证修复后', '阶段性/番茄切片',
                         '历史修复', '发现与复现', '修复过程', '验证证据',
                         '防复发', '未完成', '修复中途', '废弃/放弃'):
            self.assertIn(required, template)
        for path in (SKILL/'SKILL.md', SKILL/'references/contract.md'):
            text = path.read_text(encoding='utf-8')
            for required in ('复发缺陷', 'MEMORY', 'Git', '已验证修复后', '阶段性/番茄切片'):
                self.assertIn(required, text)
        example = spec.split('### 措辞与复核示例', 1)[-1].split('## 日期、修改身份', 1)[0]
        self.assertIn('修复并验证后', example)
        self.assertNotIn('本轮复现后，可能是保存快照捕获过晚', example)

    def test_readme_replaces_legacy_agentic_index_without_losing_protection(self):
        """OpenAI: 打扫保留旧索引的有效知识、链接和人工资料。"""
        guide = (SKILL/'references/agentic.md').read_text(encoding='utf-8')
        spec = (SKILL/'references/directory-context.md').read_text(encoding='utf-8')
        contract = (SKILL/'references/contract.md').read_text(encoding='utf-8')
        for term in ('README.md', '单一有效正文', 'Agentic/', 'AGENTS.md',
                     '相对链接', '.meta', '还差哪些'):
            self.assertIn(term, guide)
        for text in (guide, spec, contract):
            for stale in ('`Agentic.md` 保留Core模块索引职责',
                          '`Agentic.md`保留Core索引职责和位置',
                          '# <模块名> Agentic 索引', '索引保留既有位置与职责'):
                self.assertNotIn(stale, text)
        self.assertIn('不再新建或续写', guide)
        self.assertIn('README', contract)
        readme_template = (SKILL/'templates/module-readme.md').read_text(encoding='utf-8')
        for heading in ('## 依赖、禁止的反向依赖与插件边界',
                        '## 场景、预制件、资源与装配前提',
                        '## 生命周期、数据流、线程与清理'):
            self.assertIn(heading, readme_template)
        self.assertIn('不得只搬章节标题或链接', guide)
        self.assertIn('旧 Agentic.md 有价值的相关正文原意迁入', readme_template)

    def test_scope_examples_preserve_exact_targets_and_explain_discovery(self):
        """OpenAI: 两组路径例子不变，存放规则只保留日常直观判断。"""
        spec = (SKILL/'references/directory-context.md').read_text(encoding='utf-8')
        section = spec.split('### 记在哪里', 1)[-1].split('## 每份文件头部', 1)[0]
        # OpenAI: Check each relationship-to-owner mapping, not just token presence.
        rows = [[cell.strip() for cell in line.strip('|').split('|')]
                for line in section.splitlines() if line.startswith('| `./Core/')]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0][:2], [
            '`./Core/FunA/ViewModel.cs` 与 `./Core/Mgr.cs` 联动产生 bug',
            '`./Agentic/DEBUG.md`'])
        self.assertEqual(rows[1][:2], [
            '`./Core/FunA/ViewModel.cs` 与 `./Core/FunA/Prefab.asset` 联动产生 bug',
            '`./Core/FunA/Agentic/DEBUG.md`'])
        for term in ('./Core/FunA/ViewModel.cs', './Core/Mgr.cs', './Agentic/DEBUG.md',
                     './Core/FunA/Prefab.asset', './Core/FunA/Agentic/DEBUG.md',
                     './Core/README.md', '只修改 Mgr.cs', '所有 Markdown 记忆',
                     '出事那块目录自己的 README/Agentic', '凡是动这块东西的人都得先看', '死机级',
                     '单一有效正文', '按需读取', '不扩大权限'):
            with self.subTest(term=term):
                self.assertIn(term, section)

    def test_each_template_explains_scope_routing_before_its_body(self):
        """OpenAI: 复制模板同样采用简短存放规则，不带旧判定链。"""
        for kind in ('readme', 'memory', 'user', 'debug'):
            text = (SKILL/f'templates/module-{kind}.md').read_text(encoding='utf-8')
            header = text.split('\n## ', 1)[0]
            with self.subTest(kind=kind):
                for term in ('出事那块目录自己的 README/Agentic', '凡是动这块东西的人都得先看', '死机级', '按需读取', '入口'):
                    self.assertIn(term, header)
        debug = (SKILL/'templates/module-debug.md').read_text(encoding='utf-8')
        for term in ('缺陷与防复发', '关联文件/数据', '单独修改任一关联方', '唯一正文'):
            self.assertIn(term, debug)

    def test_markdown_relative_links_resolve(self):
        """OpenAI: 逐个检查仓库 Markdown 相对链接实际存在，跳过外链与片段锚点。"""
        for path in ROOT.rglob('*.md'):
            if '.git' in path.parts:
                continue
            for link in re.findall(r'\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
                link = link.split('#', 1)[0]
                if not link or '://' in link or link.startswith('mailto:'):
                    continue
                with self.subTest(file=path.relative_to(ROOT).as_posix(), link=link):
                    self.assertTrue((path.parent/link).exists())

    def test_bundle_has_no_case_only_path_collisions(self):
        """OpenAI: 以大小写折叠后的相对路径检测跨大小写文件系统的路径冲突。"""
        paths = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
                 if '.git' not in p.parts and '__pycache__' not in p.parts]
        self.assertEqual(len(paths), len({p.casefold() for p in paths}))

    def test_spec_keeps_user_intent_and_legacy_file_protection(self):
        """OpenAI: 检查目录上下文规范仍禁止借新布局擅改旧文件或扩大读写授权。"""
        text = (SKILL/'references/directory-context.md').read_text(encoding='utf-8')
        for required in ('MEMORY.md', 'USER.md', 'README.md', 'Readme.md', 'AgentDocs/',
                         '一次性', '未来设想', '不覆盖、不改名、不自动改写', '私有记忆',
                         '脚本与资产', '只读', '兄弟', '推断', '.meta'):
            self.assertIn(required, text)


    def test_cleanup_authority_is_explicit_in_entry_spec_and_templates(self):
        """OpenAI: 确认入口、规范及各模板均限制清理权限与无损整合条件。"""
        paths = [SKILL/'SKILL.md', SKILL/'references/directory-context.md',
                 *(SKILL/f'templates/module-{kind}.md' for kind in ('memory', 'user', 'readme', 'debug'))]
        for path in paths:
            text = path.read_text(encoding='utf-8')
            with self.subTest(path=path.name):
                for term in ('九成以上把握', '无损整合', '内容压缩', '专门获授权', '审计/辅助模型'):
                    self.assertIn(term, text)
        self.assertIn('否则直接忽略', (SKILL/'SKILL.md').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
