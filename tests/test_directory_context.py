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
        index = (SKILL/'references/agentic.md').read_text(encoding='utf-8')
        for term in ('创建日期', '最近修改日期', '##模型：', '变更记录'):
            self.assertIn(term, index)

    def test_existing_memories_migrate_and_readme_header_is_self_contained(self):
        spec = (SKILL/'references/directory-context.md').read_text(encoding='utf-8')
        entry = (SKILL/'SKILL.md').read_text(encoding='utf-8')
        readme = (SKILL/'templates/module-readme.md').read_text(encoding='utf-8')
        header = readme.split('## 业务与边界', 1)[0]
        for text in (spec, entry):
            for required in ('既有共享记忆也必须迁移', '不是仅新建文件',
                             '未安装本技能', 'README原有职责与权威索引'):
                self.assertIn(required, text)
        for required in ('未安装本技能', 'README原有职责与权威索引',
                         'Agentic/MEMORY.md', 'Agentic/USER.md', 'Agentic/DEBUG.md',
                         '同级区域上下文', '不是临时文件', '不得擅自删除或改作他用'):
            self.assertIn(required, header)
        for required in ('不是可选布局', '迁移未完成', '责任人', '仅存放位置改变'):
            self.assertIn(required, spec)

    def test_each_file_header_stands_alone_for_an_unfamiliar_agent(self):
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
        index = (SKILL/'references/agentic.md').read_text(encoding='utf-8')
        header = index.split('```markdown\n', 1)[1].split('\n## ', 1)[0]
        for term in ('持久共享', '逻辑作用域', 'README入口', '未安装本技能',
                     '不得擅自删除或改作他用', '当前任务授权', '内容压缩'):
            self.assertIn(term, header)

    def test_markdown_relative_links_resolve(self):
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
        paths = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*')
                 if '.git' not in p.parts and '__pycache__' not in p.parts]
        self.assertEqual(len(paths), len({p.casefold() for p in paths}))

    def test_spec_keeps_user_intent_and_legacy_file_protection(self):
        text = (SKILL/'references/directory-context.md').read_text(encoding='utf-8')
        for required in ('MEMORY.md', 'USER.md', 'README.md', 'Readme.md', 'AgentDocs/',
                         '一次性', '未来设想', '不覆盖、不改名、不自动改写', '私有记忆',
                         '脚本与资产', '只读', '兄弟', '推断', '.meta'):
            self.assertIn(required, text)


    def test_cleanup_authority_is_explicit_in_entry_spec_and_templates(self):
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
