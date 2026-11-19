# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: Test project memory scope without reading or writing the user's environment."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/ld-codestyle-online/scripts/project_memory.py'
SPEC = importlib.util.spec_from_file_location('project_memory_fixture', SCRIPT)
memory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(memory)


class FakeKey:
    def __enter__(self):
        """OpenAI: 模拟注册表句柄的上下文入口，不打开任何真实系统资源。"""
        return self

    def __exit__(self, *args):
        """OpenAI: 模拟句柄释放，保留异常以便验证调用方的失败处理。"""
        return False


class FakeRegistry:
    HKEY_CURRENT_USER = 'fake-current-user'
    KEY_QUERY_VALUE = 1
    KEY_SET_VALUE = 2
    REG_SZ = 1
    REG_EXPAND_SZ = 2
    REG_DWORD = 4

    def __init__(self, value=None, value_type=REG_SZ):
        """OpenAI: 建立完全隔离的注册表替身，并放入不应受影响的另一变量。"""
        self.values = {'UNRELATED_VARIABLE': ('untouched', self.REG_SZ)}
        if value is not None:
            self.values[memory.VARIABLE] = (value, value_type)
        self.accesses = []
        self.writes = 0
        self.deny_read = False
        self.deny_write = False
        self.fail_verification = False

    def OpenKey(self, hive, key, reserved=0, access=KEY_QUERY_VALUE):
        """OpenAI: 只允许访问当前用户 Environment，记录操作而不触及真实注册表。"""
        if hive != self.HKEY_CURRENT_USER or key != 'Environment':
            raise AssertionError('Unexpected registry key')
        if self.deny_read:
            raise PermissionError('read denied')
        self.accesses.append(('open', key, access))
        return FakeKey()

    def CreateKeyEx(self, hive, key, reserved=0, access=KEY_SET_VALUE):
        """OpenAI: 模拟当前用户环境键的可写句柄，并能注入写入权限失败。"""
        if hive != self.HKEY_CURRENT_USER or key != 'Environment':
            raise AssertionError('Unexpected registry key')
        if self.deny_write:
            raise PermissionError('write denied')
        self.accesses.append(('create', key, access))
        return FakeKey()

    def QueryValueEx(self, key, name):
        """OpenAI: 只能查询单一黑名单变量，防止实现顺手读取其他用户环境。"""
        if name != memory.VARIABLE:
            raise AssertionError('Unexpected registry variable')
        self.accesses.append(('query', name))
        if self.fail_verification and self.writes:
            raise OSError('verification unavailable')
        if name not in self.values:
            raise FileNotFoundError('variable absent')
        return self.values[name]

    def SetValueEx(self, key, name, reserved, value_type, value):
        """OpenAI: 只允许写入黑名单 REG_SZ，其余变量始终保留在替身中。"""
        if name != memory.VARIABLE or value_type != self.REG_SZ:
            raise AssertionError('Unexpected registry mutation')
        if self.deny_write:
            raise PermissionError('write denied')
        self.accesses.append(('set', name))
        self.writes += 1
        self.values[name] = (value, value_type)


class ProjectMemoryTests(unittest.TestCase):
    def invoke(self, project, *args, environ=None, registry=None, windows=True, lock_directory=None):
        """OpenAI: 调用真实 CLI 入口并注入环境、注册表和临时锁，完全隔离用户配置。"""
        stream = io.StringIO()
        with tempfile.TemporaryDirectory() as isolated_locks, redirect_stdout(stream):
            code = memory.main([*args, '--project-root', str(project)],
                               environ={} if environ is None else environ,
                               registry=FakeRegistry() if registry is None else registry,
                               windows=windows,
                               lock_directory=isolated_locks if lock_directory is None else lock_directory)
        return code, json.loads(stream.getvalue())

    def mark_heavy(self, path):
        """OpenAI: 写入明确的 Unity 工程标记，供启用态测试使用，不代表真实业务项目。"""
        root = Path(path)
        (root / 'Assets').mkdir(parents=True, exist_ok=True)
        settings = root / 'ProjectSettings'
        settings.mkdir(parents=True, exist_ok=True)
        version = settings / 'ProjectVersion.txt'
        if not version.exists():
            version.write_text('m_EditorVersion: 2022.3.0f1\n', encoding='utf-8')
        return root

    def test_default_show_enables_light_projects_without_writing(self):
        """OpenAI: 缺变量时轻量项目也默认启用；show 不创建项目资料或写注册表、进程环境。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env, registry = {}, FakeRegistry()
            code, result = self.invoke(root, 'show', environ=env, registry=registry)
            self.assertEqual(code, 0)
            self.assertEqual(result['status'], 'ok')
            self.assertTrue(result['enabled'])
            self.assertEqual(result['project_kind'], 'unknown')
            self.assertFalse(result['existing_memory'])
            self.assertFalse(result['persisted'])
            self.assertEqual(result['source'], 'default')
            self.assertEqual(result['excluded_roots'], [])
            self.assertEqual(result['value'], '[]')
            self.assertEqual(result['project_root'], memory.normalize_project_root(root))
            self.assertEqual(list(root.iterdir()), [])
            self.assertEqual(env, {})
            self.assertEqual(registry.writes, 0)

    def test_heavy_engine_and_existing_memory_enable_unless_excluded(self):
        """OpenAI: Unity 标记或已有记忆文件仍默认启用；黑名单仍可关闭重型项目。"""
        with tempfile.TemporaryDirectory() as tmp:
            unity = self.mark_heavy(Path(tmp) / 'unity')
            env, registry = {}, FakeRegistry()
            code, result = self.invoke(unity, 'show', environ=env, registry=registry)
            self.assertEqual(code, 0)
            self.assertTrue(result['enabled'])
            self.assertEqual(result['project_kind'], 'unity')
            self.assertFalse(result['existing_memory'])
            self.assertEqual(env, {})
            self.assertEqual(registry.writes, 0)
            light = Path(tmp) / 'web'
            light.mkdir()
            (light / 'Agentic').mkdir()
            (light / 'Agentic' / 'MEMORY.md').write_text('fixture memory', encoding='utf-8')
            code, result = self.invoke(light, 'show', environ=env, registry=registry)
            self.assertEqual(code, 0)
            self.assertTrue(result['enabled'])
            self.assertEqual(result['project_kind'], 'unknown')
            self.assertTrue(result['existing_memory'])
            excluded = {memory.VARIABLE: json.dumps([str(unity)])}
            code, result = self.invoke(unity, 'show', environ=excluded, registry=registry)
            self.assertEqual(code, 0)
            self.assertFalse(result['enabled'])
            self.assertEqual(result['project_kind'], 'unity')

    def make_symlink(self, link, target, directory=True):
        """OpenAI: 以真实链接构造路径，只在 Windows 未授予创建符号链接权限时跳过。"""
        try:
            link.symlink_to(target, target_is_directory=directory)
        except OSError as exc:
            if getattr(exc, 'winerror', None) == 1314:
                self.skipTest('Windows symlink privilege unavailable')
            raise

    def check_directory_links(self, create_link):
        """OpenAI: 用同一套项目内外、重复入口与环路现场检验符号链接和 Windows 联接。"""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'project'
            module = project / 'module'
            records = project / 'records'
            other = Path(tmp) / 'project-other'
            module.mkdir(parents=True)
            records.mkdir()
            (other / 'Agentic').mkdir(parents=True)
            (other / 'Agentic' / 'MEMORY.md').write_text('other project', encoding='utf-8')
            (records / 'USER.md').write_text('local intent', encoding='utf-8')
            create_link(project / 'Agentic', other / 'Agentic')
            create_link(project / 'external', other)
            create_link(project / 'alias', module)
            create_link(module / 'loop', project)
            metadata = project / '.git' / 'records'
            metadata.mkdir(parents=True)
            (metadata / 'MEMORY.md').write_text('git fixture', encoding='utf-8')
            create_link(module / 'metadata', metadata)
            create_link(records / 'Agentic', metadata)

            with patch.object(memory.os, 'scandir', wraps=os.scandir) as scan:
                self.assertFalse(memory.has_existing_memory(project))
            # OpenAI: 无命中时实际遍历完整个测试项目，但外部目录与已访问目录都不再进入。
            visited = [Path(call.args[0]).resolve() for call in scan.call_args_list]
            self.assertCountEqual(visited, [project.resolve(), module.resolve(), records.resolve()])

            create_link(module / 'Agentic', records)
            code, result = self.invoke(project, 'show')
            self.assertEqual(code, 0)
            self.assertTrue(result['existing_memory'])
            self.assertTrue(result['enabled'])

    def test_project_modules_and_root_fast_path(self):
        """OpenAI: 真实模块可名为 Build 或 Library；根目录已有记忆可直接命中。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            area = root / 'src' / 'Build' / 'Library' / 'Agentic'
            area.mkdir(parents=True)
            (area / 'README.md').write_text('module index', encoding='utf-8')
            self.assertFalse(memory.has_existing_memory(root))
            (area / 'DEBUG.md').write_text('module history', encoding='utf-8')
            self.assertTrue(memory.has_existing_memory(root))
            (root / 'Agentic').mkdir()
            (root / 'Agentic' / 'MEMORY.md').write_text('root history', encoding='utf-8')
            with patch.object(memory.os, 'scandir', side_effect=AssertionError('unexpected scan')):
                self.assertTrue(memory.has_existing_memory(root))

    def test_disappearing_directory_entry_does_not_hide_module_memory(self):
        """OpenAI: 枚举与查询之间消失一个目录项时继续查找同项目的真实记忆。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'moving').mkdir()
            area = root / 'module' / 'Agentic'
            area.mkdir(parents=True)
            (area / 'MEMORY.md').write_text('module history', encoding='utf-8')
            classify = memory._project_directory

            def classify_during_move(entry, project):
                """OpenAI: 只注入单个条目的删除竞态，其余路径用实际文件系统验证。"""
                if entry.name == 'moving':
                    raise FileNotFoundError(entry.path)
                return classify(entry, project)

            with patch.object(memory, '_project_directory', side_effect=classify_during_move):
                self.assertTrue(memory.has_existing_memory(root))

    def test_only_in_project_directory_symlinks_contribute_memory(self):
        """OpenAI: 根和模块的目录符号链接不跨项目，根内别名仍可暴露实际记忆。"""
        self.check_directory_links(self.make_symlink)

    @unittest.skipUnless(os.name == 'nt', 'NTFS junctions require Windows')
    def test_only_in_project_junctions_contribute_memory(self):
        """OpenAI: 用不依赖符号链接权限的真实 NTFS 联接复核根内外和循环。"""
        import _winapi
        self.check_directory_links(lambda link, target: _winapi.CreateJunction(str(target), str(link)))

    def test_memory_files_resolve_within_the_project(self):
        """OpenAI: 根级和模块级的三个记忆文件允许根内链接，不把外链、断链和普通说明当记忆。"""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'project'
            module = project / 'module' / 'Agentic'
            module.mkdir(parents=True)
            records = project / 'Agentic'
            records.mkdir()
            external = Path(tmp) / 'external.md'
            external.write_text('other project', encoding='utf-8')
            local = project / 'notes.md'
            local.write_text('local intent', encoding='utf-8')
            (module / 'README.md').write_text('module index', encoding='utf-8')
            (records / 'DEBUG.md').mkdir()
            self.make_symlink(records / 'USER.md', external, directory=False)
            self.make_symlink(module / 'MEMORY.md', external, directory=False)
            self.make_symlink(module / 'DEBUG.md', project / 'missing.md', directory=False)
            self.assertFalse(memory.has_existing_memory(project))
            self.make_symlink(module / 'USER.md', local, directory=False)
            self.assertTrue(memory.has_existing_memory(project))

    def test_exclude_and_include_require_explicit_owner_request(self):
        """OpenAI: 缺少主人明确要求声明时，两种变更都不得生成已生效结果或写环境。"""
        with tempfile.TemporaryDirectory() as tmp:
            registry = FakeRegistry()
            for command in ('exclude', 'include'):
                for flags in ((), ('--persist-user',)):
                    with self.subTest(command=command, flags=flags):
                        code, result = self.invoke(tmp, command, *flags, registry=registry)
                        self.assertNotEqual(code, 0)
                        self.assertEqual(result['status'], 'error')
                        self.assertFalse(result['persisted'])
                        self.assertNotIn('enabled', result)
            self.assertEqual(registry.writes, 0)

    def test_default_changes_are_suggestions_until_host_applies_value(self):
        """OpenAI: 候选状态与当前状态分开，调用方落地建议值后再查询才看到生效。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = self.mark_heavy(tmp)
            registry, env = FakeRegistry(), {}
            code, result = self.invoke(root, 'exclude', '--owner-requested', environ=env, registry=registry)
            self.assertEqual(code, 0)
            self.assertEqual(result['status'], 'environment_update_required')
            self.assertTrue(result['enabled'])
            self.assertFalse(result['desired_enabled'])
            self.assertFalse(result['persisted'])
            self.assertEqual(result['excluded_roots'], [])
            self.assertEqual(result['desired_excluded_roots'], [memory.normalize_project_root(root)])
            self.assertEqual(registry.writes, 0)
            self.assertEqual(env, {})
            self.assertTrue(self.invoke(root, 'show', registry=registry)[1]['enabled'])
            applied = {memory.VARIABLE: result['value']}
            self.assertFalse(self.invoke(root, 'show', environ=applied, registry=registry)[1]['enabled'])
            code, include = self.invoke(root, 'include', '--owner-requested', environ=applied, registry=registry)
            self.assertEqual(code, 0)
            self.assertFalse(include['enabled'])
            self.assertTrue(include['desired_enabled'])
            self.assertEqual(include['value'], '[]')
            self.assertFalse(include['persisted'])

    def test_exact_root_matching_does_not_exclude_siblings_or_nested_projects(self):
        """OpenAI: 排除按规范化完整根相等判断，不能按字符串前缀或祖先扩大范围。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'Project'
            sibling = Path(tmp) / 'ProjectElse'
            nested = root / 'IndependentProject'
            root.mkdir()
            sibling.mkdir()
            nested.mkdir()
            self.mark_heavy(root)
            self.mark_heavy(sibling)
            self.mark_heavy(nested)
            env = {memory.VARIABLE: json.dumps([str(root / '..' / root.name)])}
            for project, expected in ((root, False), (sibling, True), (nested, True)):
                with self.subTest(project=project):
                    code, result = self.invoke(project, 'show', environ=env)
                    self.assertEqual(code, 0)
                    self.assertEqual(result['enabled'], expected)
            # OpenAI: 完整根的尾分隔符与点路径是同一目录，不能制造第二个排除身份。
            code, result = self.invoke(str(root) + os.sep, 'exclude', '--owner-requested', environ=env)
            self.assertEqual(code, 0)
            self.assertEqual(result['desired_excluded_roots'], [memory.normalize_project_root(root)])

    def test_real_directory_aliases_share_one_normalized_root(self):
        """OpenAI: 实际符号链接根和目标根共享排除记录；平台不许建链接时如实跳过。"""
        with tempfile.TemporaryDirectory() as tmp:
            target, alias = Path(tmp) / 'target', Path(tmp) / 'alias'
            target.mkdir()
            self.mark_heavy(target)
            try:
                alias.symlink_to(target, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f'Temporary directory symlink unavailable: {type(exc).__name__}')
            env = {memory.VARIABLE: json.dumps([str(alias)])}
            code, result = self.invoke(target, 'show', environ=env)
            self.assertEqual(code, 0)
            self.assertFalse(result['enabled'])
            self.assertEqual(result['excluded_roots'], [memory.normalize_project_root(target)])

    def test_windows_case_aliases_match_without_prefix_expansion(self):
        """OpenAI: Windows 大小写别名用原生规范化比较，其他系统保留其路径语义。"""
        if os.name != 'nt':
            self.skipTest('Windows path normalization requires Windows')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'MixedCaseProject'
            root.mkdir()
            self.mark_heavy(root)
            env = {memory.VARIABLE: json.dumps([str(root).swapcase()])}
            code, result = self.invoke(root, 'show', environ=env)
            self.assertEqual(code, 0)
            self.assertFalse(result['enabled'])

    def test_invalid_values_fail_without_fallback_or_sensitive_raw_echo(self):
        """OpenAI: 坏 JSON、类型与相对路径拒绝，不能被当作空列表重新启用。"""
        with tempfile.TemporaryDirectory() as tmp:
            for raw in ('', 'PRIVATE-RAW-SECRET', '{}', 'null', 'true', '1', '[null]',
                        '[true]', '[1]', '["relative-root"]', '[""]', '["PRIVATE\\nROOT"]'):
                with self.subTest(raw=raw):
                    code, result = self.invoke(tmp, 'show', environ={memory.VARIABLE: raw})
                    self.assertNotEqual(code, 0)
                    self.assertEqual(result['status'], 'error')
                    self.assertNotIn('enabled', result)
                    self.assertNotIn('PRIVATE-', json.dumps(result))
            for root in ('relative-root', Path(tmp) / 'missing'):
                code, result = self.invoke(root, 'show')
                self.assertNotEqual(code, 0)
                self.assertNotIn('enabled', result)
            file = Path(tmp) / 'not-a-directory'
            file.write_text('fixture', encoding='utf-8')
            self.assertNotEqual(self.invoke(file, 'show')[0], 0)

    def test_unavailable_old_roots_are_retained_when_updating_other_projects(self):
        """OpenAI: 已移走项目的合法绝对根仍保留，不擅自清空其他排除记录。"""
        with tempfile.TemporaryDirectory() as tmp:
            root, previous = Path(tmp), Path(tmp) / 'previous-project-now-absent'
            env = {memory.VARIABLE: json.dumps([str(previous)])}
            code, result = self.invoke(root, 'exclude', '--owner-requested', environ=env)
            self.assertEqual(code, 0)
            self.assertEqual(result['desired_excluded_roots'],
                             [memory.normalize_project_root(previous, must_exist=False),
                              memory.normalize_project_root(root)])

    def test_persistent_registry_value_overrides_stale_process_environment(self):
        """OpenAI: 持久空列表也有优先级，不能被继承的旧排除值重新覆盖。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = self.mark_heavy(tmp)
            env = {memory.VARIABLE: json.dumps([tmp])}
            registry = FakeRegistry('[]')
            code, result = self.invoke(root, 'show', environ=env, registry=registry)
            self.assertEqual(code, 0)
            self.assertTrue(result['enabled'])
            self.assertEqual(result['source'], 'user_environment')
            self.assertEqual(registry.writes, 0)
            registry.values[memory.VARIABLE] = ('PRIVATE-INVALID-RAW', registry.REG_SZ)
            code, result = self.invoke(root, 'show', environ={memory.VARIABLE: '[]'}, registry=registry)
            self.assertNotEqual(code, 0)
            self.assertNotIn('enabled', result)
            self.assertNotIn('PRIVATE-INVALID-RAW', json.dumps(result))
            registry.values[memory.VARIABLE] = (7, registry.REG_DWORD)
            self.assertNotEqual(self.invoke(root, 'show', registry=registry)[0], 0)

    def test_windows_persistence_preserves_other_roots_and_unrelated_environment(self):
        """OpenAI: 显式持久化仅改一个注册表值，回读后才将候选状态标为已生效。"""
        with tempfile.TemporaryDirectory() as tmp:
            root, other = Path(tmp) / 'project', Path(tmp) / 'other'
            root.mkdir()
            other.mkdir()
            self.mark_heavy(root)
            self.mark_heavy(other)
            registry = FakeRegistry(json.dumps([str(other)]))
            env = {memory.VARIABLE: '[]', 'UNRELATED_PROCESS': 'unchanged'}
            code, result = self.invoke(root, 'exclude', '--owner-requested', '--persist-user',
                                       environ=env, registry=registry)
            self.assertEqual(code, 0)
            self.assertEqual(result['status'], 'updated')
            self.assertTrue(result['persisted'])
            self.assertFalse(result['enabled'])
            self.assertEqual(result['source'], 'user_environment')
            self.assertEqual(result['excluded_roots'],
                             [memory.normalize_project_root(other), memory.normalize_project_root(root)])
            self.assertEqual(registry.values['UNRELATED_VARIABLE'], ('untouched', registry.REG_SZ))
            self.assertEqual(env, {memory.VARIABLE: '[]', 'UNRELATED_PROCESS': 'unchanged'})
            self.assertFalse(self.invoke(root, 'show', environ=env, registry=registry)[1]['enabled'])
            code, restored = self.invoke(root, 'include', '--owner-requested', '--persist-user',
                                         environ=env, registry=registry)
            self.assertEqual(code, 0)
            self.assertTrue(restored['enabled'])
            self.assertEqual(restored['excluded_roots'], [memory.normalize_project_root(other)])
            self.assertEqual(registry.writes, 2)

    def test_including_final_root_persists_empty_list_to_defeat_stale_inheritance(self):
        """OpenAI: 最后一项移除后保存 [] 而非删除变量，防止进程旧值重新成为默认。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = self.mark_heavy(tmp)
            raw = json.dumps([tmp])
            registry = FakeRegistry(raw)
            code, result = self.invoke(root, 'include', '--owner-requested', '--persist-user',
                                       environ={memory.VARIABLE: raw}, registry=registry)
            self.assertEqual(code, 0)
            self.assertTrue(result['persisted'])
            self.assertTrue(result['enabled'])
            self.assertEqual(registry.values[memory.VARIABLE], ('[]', registry.REG_SZ))
            self.assertTrue(self.invoke(root, 'show', environ={memory.VARIABLE: raw},
                                        registry=registry)[1]['enabled'])

    def test_non_windows_persistence_is_an_explicit_host_action_not_fake_success(self):
        """OpenAI: 非 Windows 返回宿主配置建议，不调用注册表或假称持久化完成。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = self.mark_heavy(tmp)
            registry = FakeRegistry('PRIVATE-REGISTRY-MUST-NOT-BE-READ')
            code, result = self.invoke(root, 'exclude', '--owner-requested', '--persist-user',
                                       registry=registry, windows=False)
            self.assertEqual(code, 0)
            self.assertTrue(result['enabled'])
            self.assertFalse(result['desired_enabled'])
            self.assertFalse(result['persisted'])
            self.assertEqual(result['status'], 'environment_update_required')
            self.assertTrue(result['next_step'])
            self.assertEqual(registry.accesses, [])

    def test_permission_or_verification_failures_never_report_updated(self):
        """OpenAI: 读写失败拒绝；写后读验失败明确结果未知，不能伪报成功或未写入。"""
        with tempfile.TemporaryDirectory() as tmp:
            for mode in ('deny_read', 'deny_write', 'fail_verification'):
                with self.subTest(mode=mode):
                    registry = FakeRegistry()
                    setattr(registry, mode, True)
                    code, result = self.invoke(tmp, 'exclude', '--owner-requested', '--persist-user',
                                               registry=registry)
                    self.assertNotEqual(code, 0)
                    self.assertEqual(result['status'], 'error')
                    self.assertNotIn('enabled', result)
                    if mode == 'fail_verification':
                        self.assertIsNone(result['persisted'])
                        self.assertEqual(registry.writes, 1)
                    else:
                        self.assertFalse(result['persisted'])
                        self.assertEqual(registry.writes, 0)

    def test_user_lock_covers_read_modify_write_across_different_projects(self):
        """OpenAI: 在写句柄入口插入另一项目更新，验证同用户锁阻止两个成功结果互相覆盖。"""
        with tempfile.TemporaryDirectory() as tmp:
            first, second, locks = Path(tmp) / 'first', Path(tmp) / 'second', Path(tmp) / 'locks'
            first.mkdir()
            second.mkdir()
            registry = FakeRegistry('[]')
            original_create = registry.CreateKeyEx
            nested = []

            def interleave(hive, key, reserved=0, access=registry.KEY_SET_VALUE):
                """OpenAI: 精确模拟另一安装在第一次写入前提交不同项目的排除请求。"""
                nested.append(self.invoke(second, 'exclude', '--owner-requested', '--persist-user',
                                          registry=registry, lock_directory=locks))
                return original_create(hive, key, reserved, access)

            with patch.object(registry, 'CreateKeyEx', side_effect=interleave):
                code, result = self.invoke(first, 'exclude', '--owner-requested', '--persist-user',
                                           registry=registry, lock_directory=locks)
            self.assertEqual(code, 0)
            self.assertTrue(result['persisted'])
            self.assertEqual(len(nested), 1)
            self.assertNotEqual(nested[0][0], 0)
            self.assertFalse(nested[0][1]['persisted'])
            self.assertEqual(registry.writes, 1)
            self.assertFalse((locks / memory.LOCK_NAME).exists())
            # OpenAI: 冲突者之后重新读列表再申请，须保留前一次已成功写入的项目根。
            code, result = self.invoke(second, 'exclude', '--owner-requested', '--persist-user',
                                       registry=registry, lock_directory=locks)
            self.assertEqual(code, 0)
            self.assertEqual(result['excluded_roots'],
                             [memory.normalize_project_root(first), memory.normalize_project_root(second)])

    def test_existing_or_stale_lock_is_never_deleted_or_taken_over(self):
        """OpenAI: 已有锁不能靠猜 PID 失效而自动抢占，失败也不得删除它。"""
        with tempfile.TemporaryDirectory() as tmp:
            project, locks = Path(tmp) / 'project', Path(tmp) / 'locks'
            project.mkdir()
            locks.mkdir()
            lock = locks / memory.LOCK_NAME
            lock.write_text('existing owner evidence', encoding='utf-8')
            registry = FakeRegistry()
            code, result = self.invoke(project, 'exclude', '--owner-requested', '--persist-user',
                                       registry=registry, lock_directory=locks)
            self.assertNotEqual(code, 0)
            self.assertFalse(result['persisted'])
            self.assertEqual(registry.accesses, [])
            self.assertEqual(lock.read_text(encoding='utf-8'), 'existing owner evidence')

    def test_written_value_followed_by_key_close_failure_reports_unknown(self):
        """OpenAI: 注册表值已写入但关闭写句柄失败时，不能错误宣称本次没有持久化。"""
        class CloseFailure(FakeKey):
            def __exit__(self, *args):
                """OpenAI: 仅在写入完成后注入句柄释放错误，复现结果不确定分支。"""
                raise OSError('close unavailable')

        with tempfile.TemporaryDirectory() as tmp:
            registry = FakeRegistry()
            with patch.object(registry, 'CreateKeyEx', return_value=CloseFailure()):
                code, result = self.invoke(tmp, 'exclude', '--owner-requested', '--persist-user',
                                           registry=registry)
            self.assertNotEqual(code, 0)
            self.assertIsNone(result['persisted'])
            self.assertEqual(registry.writes, 1)

    def test_observed_concurrent_registry_change_is_not_overwritten(self):
        """OpenAI: 持久值在读取与写入前检查之间变化时拒绝覆盖，保护其他项目根。"""
        with tempfile.TemporaryDirectory() as tmp:
            registry = FakeRegistry()
            with patch.object(memory, 'read_persistent_value', side_effect=[None, ('[]', registry.REG_SZ)]):
                code, result = self.invoke(tmp, 'exclude', '--owner-requested', '--persist-user',
                                           registry=registry)
            self.assertNotEqual(code, 0)
            self.assertFalse(result['persisted'])
            self.assertEqual(registry.writes, 0)


if __name__ == '__main__':
    unittest.main()
