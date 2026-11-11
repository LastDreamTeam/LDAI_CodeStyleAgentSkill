# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: Query exact project memory scope and propose explicitly requested local exclusions."""
import argparse
from contextlib import contextmanager, nullcontext
import json
import os
from pathlib import Path

VARIABLE = 'LD_CODESTYLE_MEMORY_BLACKLIST'
LOCK_NAME = 'project-memory-blacklist.lock'
_MISSING = object()


class PersistenceUncertainError(ValueError):
    def __init__(self):
        """OpenAI: 写入已尝试但未可靠读验时，保留未知状态，禁止伪报成功或安全重试。"""
        super().__init__('User environment write could not be verified; run show and inspect before retrying')
        self.persisted = None


@contextmanager
def user_environment_lock(directory=None):
    """OpenAI: 用跨安装共享的当前用户短锁串行化整次持久变更；已有锁不等待或抢占。"""
    directory = Path(directory) if directory is not None else Path.home() / '.ld-codestyle'
    if not directory.is_absolute() or directory.is_symlink():
        raise ValueError('The user environment lock requires an absolute non-symlink directory')
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / LOCK_NAME
    try:
        # OpenAI: 同一环境变量跨项目共享，故锁位置不能依赖安装路径或目标项目根。
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise ValueError('A memory scope writer or stale user lock exists; inspect it before retrying') from exc
    body_failed = False
    try:
        os.write(descriptor, json.dumps({'pid': os.getpid()}).encode('ascii'))
        yield
    except BaseException:
        body_failed = True
        raise
    finally:
        try:
            os.close(descriptor)
            path.unlink()
        except OSError:
            # OpenAI: 清理失败不能掩盖原写入异常；无原异常时交由调用方保留持久化不确定性。
            if not body_failed:
                raise


def normalize_project_root(value, *, must_exist=True):
    """OpenAI: 返回本机真实规范化绝对目录；查询目标必须存在，旧黑名单根可暂时离线。"""
    if not isinstance(value, (str, os.PathLike)):
        raise ValueError('Project roots must be absolute directory paths')
    raw = os.fspath(value)
    if (not isinstance(raw, str) or not raw or not raw.isprintable()
            or raw != raw.strip() or not Path(raw).is_absolute()):
        raise ValueError('Project roots must be explicit absolute paths without control characters')
    try:
        # OpenAI: 先解析真实链接和点路径，再应用本机大小写规范；比较时绝不使用前缀。
        path = Path(raw).resolve(strict=must_exist)
        if (must_exist or path.exists()) and not path.is_dir():
            raise ValueError('Project roots must identify directories')
    except (OSError, RuntimeError) as exc:
        raise ValueError('Project root cannot be resolved; verify the absolute directory') from exc
    return os.path.normcase(str(path))


def parse_blacklist(raw):
    """OpenAI: 校验 JSON 绝对根列表，规范化并去重；坏值拒绝，绝不假装为空配置。"""
    if not isinstance(raw, str):
        raise ValueError('Memory blacklist must be a JSON array of absolute project root strings')
    try:
        values = json.loads(raw)
    except ValueError as exc:
        raise ValueError('Memory blacklist contains invalid JSON; existing configuration was not changed') from exc
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ValueError('Memory blacklist must be a JSON array of absolute project root strings')
    roots = []
    for value in values:
        # OpenAI: 已移动或离线的合法绝对根仍保留，不能借本次更新清理其他项目的排除。
        root = normalize_project_root(value, must_exist=False)
        if root not in roots:
            roots.append(root)
    return roots


def serialize_blacklist(roots):
    """OpenAI: 将已验证的根列表序列化为一个环境变量值，保留 Unicode 路径。"""
    return json.dumps(roots, ensure_ascii=False, separators=(',', ':'))


def read_persistent_value(registry):
    """OpenAI: 只读取 HKCU Environment 的黑名单值，区分缺失与坏类型，不扫描其他变量。"""
    try:
        with registry.OpenKey(registry.HKEY_CURRENT_USER, 'Environment', 0,
                              registry.KEY_QUERY_VALUE) as key:
            value, value_type = registry.QueryValueEx(key, VARIABLE)
    except FileNotFoundError:
        return None
    # OpenAI: 即使是 REG_EXPAND_SZ 也按字面 JSON 解析，不展开用户路径中的环境表达式。
    if value_type not in (registry.REG_SZ, registry.REG_EXPAND_SZ) or not isinstance(value, str):
        raise ValueError('Persistent memory blacklist must be a string containing a JSON array')
    return value, value_type


def _load_state(environ, registry):
    """OpenAI: 持久值优先于继承环境，只有变量确实不存在时才允许默认空列表。"""
    snapshot = read_persistent_value(registry) if registry is not None else None
    if snapshot is not None:
        # OpenAI: 空字符串属于损坏值，[] 属于有效清空；两者都不能回退到进程旧值。
        raw, source = snapshot[0], 'user_environment'
    else:
        raw = environ.get(VARIABLE, _MISSING)
        source = 'default' if raw is _MISSING else 'process_environment'
        if raw is _MISSING:
            raw = '[]'
    return {'roots': parse_blacklist(raw), 'source': source, 'snapshot': snapshot}


def _persist_value(registry, value, snapshot):
    """OpenAI: 写前复查原值，单值写入后精确读验；并发变化或不确定结果不得报成功。"""
    if read_persistent_value(registry) != snapshot:
        raise ValueError('Persistent memory blacklist changed; inspect current state before retrying')
    attempted = False
    try:
        with registry.CreateKeyEx(registry.HKEY_CURRENT_USER, 'Environment', 0,
                                  registry.KEY_QUERY_VALUE | registry.KEY_SET_VALUE) as key:
            # OpenAI: 只设置这一 REG_SZ 值；清空时写 []，不删除变量而重新启用继承旧值。
            attempted = True
            registry.SetValueEx(key, VARIABLE, 0, registry.REG_SZ, value)
    except OSError as exc:
        # OpenAI: Set 已尝试后连关闭句柄失败也可能已落地，不能回报 persisted=false。
        if attempted:
            raise PersistenceUncertainError() from exc
        raise
    try:
        actual = read_persistent_value(registry)
    except (OSError, ValueError) as exc:
        raise PersistenceUncertainError() from exc
    if actual != (value, registry.REG_SZ):
        raise PersistenceUncertainError()


def project_memory(command, project_root, *, owner_requested=False, persist_user=False,
                   environ=None, registry=None, windows=None, lock_directory=None):
    """OpenAI: 返回当前项目记忆状态及可选环境建议，只有显式 Windows 持久化才写系统。

    enabled/excluded_roots 始终是已观察到的实际状态；desired_* 是主人要求的候选。
    默认变更不改进程环境或项目文件，Windows 写后读验成功才返回 persisted=true。
    environ/registry/windows/lock_directory 可注入隔离测试；持久变更在当前用户共享锁
    内重读、计算与写验，正常查询只读取本机单个环境变量，不写锁或项目资料。
    """
    if command not in ('show', 'exclude', 'include'):
        raise ValueError('Choose show, exclude or include')
    if type(owner_requested) is not bool or type(persist_user) is not bool:
        raise ValueError('Owner request and persistence flags must be boolean')
    if command != 'show' and not owner_requested:
        raise ValueError('Changing memory scope requires the owner-requested declaration')
    if command == 'show' and (owner_requested or persist_user):
        raise ValueError('show is read-only; use include or exclude for an owner-requested change')
    if windows is None:
        windows = os.name == 'nt'
    elif type(windows) is not bool:
        raise ValueError('Platform selection must be boolean')
    root = normalize_project_root(project_root)
    if windows and registry is None:
        import winreg
        registry = winreg
    if not windows:
        registry = None
    write_verified = False
    try:
        # OpenAI: 必须在锁内读取最新列表再修改，单独锁住 Set 仍会丢失其他项目的并发更新。
        with user_environment_lock(lock_directory) if persist_user and windows else nullcontext():
            state = _load_state(os.environ if environ is None else environ, registry)
            roots = state['roots']
            result = {'status': 'ok', 'project_root': root, 'enabled': root not in roots,
                      'excluded_roots': list(roots), 'variable': VARIABLE,
                      'value': serialize_blacklist(roots), 'source': state['source'], 'persisted': False}
            if command == 'show':
                return result

            desired = list(roots)
            if command == 'exclude' and root not in desired:
                desired.append(root)
            elif command == 'include':
                desired = [candidate for candidate in desired if candidate != root]
            result.update(status='environment_update_required', desired_enabled=root not in desired,
                          desired_excluded_roots=desired, value=serialize_blacklist(desired))
            if persist_user and windows:
                _persist_value(registry, result['value'], state['snapshot'])
                write_verified = True
                result.update(status='updated', enabled=root not in desired, excluded_roots=list(desired),
                              source='user_environment', persisted=True)
            else:
                # OpenAI: 给出候选不代表生效；非 Windows 由已有宿主入口落地，不改 shell profile。
                result['next_step'] = ('Apply value through the authorized host or OS environment settings, '
                                       'then run show in that environment to verify; Windows readers prefer '
                                       'the user-persisted value when present')
    except OSError as exc:
        if write_verified:
            raise PersistenceUncertainError() from exc
        raise
    return result


def main(argv=None, *, environ=None, registry=None, windows=None, lock_directory=None):
    """OpenAI: 解析最小 CLI 并输出 ASCII JSON；错误不回显坏环境值或未核路径。"""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('show', 'exclude', 'include'):
        sub = commands.add_parser(command)
        sub.add_argument('--project-root', required=True, help='Existing absolute project root')
        if command != 'show':
            sub.add_argument('--owner-requested', action='store_true',
                             help='Caller declares an explicit request from the project owner')
            sub.add_argument('--persist-user', action='store_true',
                             help='On Windows, persist only this variable in HKCU Environment')
    args = parser.parse_args(argv)
    try:
        result = project_memory(args.command, args.project_root,
                                owner_requested=getattr(args, 'owner_requested', False),
                                persist_user=getattr(args, 'persist_user', False),
                                environ=environ, registry=registry, windows=windows,
                                lock_directory=lock_directory)
    except PersistenceUncertainError as exc:
        result = {'status': 'error', 'error': str(exc), 'persisted': None}
    except ValueError as exc:
        result = {'status': 'error', 'error': str(exc), 'persisted': False}
    except OSError:
        result = {'status': 'error', 'error': 'Unable to access the memory scope environment; no verified change',
                  'persisted': False}
    # OpenAI: 外层 ASCII JSON 可在旧 Windows 控制台解码，内部 value 仍保持准确 Unicode 路径。
    print(json.dumps(result, ensure_ascii=True))
    return 1 if result['status'] == 'error' else 0


if __name__ == '__main__':
    raise SystemExit(main())
