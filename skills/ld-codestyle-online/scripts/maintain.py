# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: Per-install preferences and bounded, native-backend maintenance."""
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

NAME = 'ld-codestyle-online'
REPO = 'LastDreamTeam/LDAI_CodeStyleAgentSkill'
# OpenAI: The sole previous repository name is an explicit alias, not a wildcard trust rule.
OFFICIAL_REPOS = (REPO, 'LastDreamTeam/LDCodeStyleAgentSkill')
DEFAULTS = {'schema_version': 1, 'human_name': 'LD', 'human_commit_name': '主人',
            'interval_days': 1, 'auto_update': True}
CHECK_INTERVAL_SECONDS = 24 * 60 * 60
HEALTH_SCHEMA_VERSION = 1
INTERACTION_DEFAULTS = {'enabled': True, 'answer_wait_minutes': 15, 'idle_after_minutes': 0}


def load_json(path, default):
    """OpenAI: 读取对象型 JSON；文件尚不存在时返回默认配置的独立副本。"""
    if not path.exists():
        return dict(default)
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'Expected JSON object: {path.name}')
    return value


def save_json(path, value):
    """OpenAI: 拒绝非标准数字，先写入同目录临时文件并同步，再原子替换JSON。"""
    # OpenAI: Failed serialization leaves the previous document intact, never a partially written snapshot.
    fd, name = tempfile.mkstemp(prefix='.writing-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(value, out, ensure_ascii=False, indent=2, allow_nan=False)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def hermes_home(skill):
    """OpenAI: 沿技能父目录寻找带原生管理器锁文件的 Hermes 安装根目录。"""
    for parent in skill.parents:
        if parent.name == 'skills' and (parent / '.hub/lock.json').is_file():
            return parent.parent
    return None


def data_dir(skill, explicit=None):
    """OpenAI: 以技能物理路径摘要隔离安装实例，按显式根、环境根、Hermes 根依次选数据目录。"""
    identity = hashlib.sha256(os.path.normcase(str(skill.resolve())).encode()).hexdigest()[:24]
    base = explicit or os.environ.get('LD_CODESTYLE_DATA_ROOT')
    if base:
        return Path(base).expanduser().resolve() / NAME / identity
    home = hermes_home(skill)
    if home:
        return home / 'skill-data' / NAME / identity
    return skill / '.ld-codestyle-data' / 'schema-1'


@contextmanager
def locked(directory):
    """OpenAI: 独占创建维护锁并在退出时释放；已有锁直接拒绝并发维护。"""
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / 'maintenance.lock'
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump({'pid': os.getpid(), 'created_at': time.time()}, out)
        yield
    finally:
        lock.unlink()


def validate_commit_name(value):
    """OpenAI: 限制人类署名为单行可见文本，拒绝能伪造提交头字段的分隔符。"""
    if (not isinstance(value, str) or not 1 <= len(value) <= 40
            or not value.isprintable() or value != value.strip()
            or any(char in value for char in '#|+:：【】[]')):
        raise ValueError('human_commit_name must be 1-40 visible characters without header delimiters')


def interaction_config(config):
    """OpenAI: 合并交互默认值与配置覆盖，并严格校验布尔开关及分钟区间。"""
    # OpenAI: Resolve additive preferences without rewriting legacy files or sharing defaults.
    overrides = config.get('interaction', {})
    if not isinstance(overrides, dict) or set(overrides) - set(INTERACTION_DEFAULTS):
        raise ValueError('Invalid interaction settings')
    result = {**INTERACTION_DEFAULTS, **overrides}
    if type(result['enabled']) is not bool:
        raise ValueError('interaction.enabled must be boolean')
    for name, lower in (('answer_wait_minutes', 1), ('idle_after_minutes', 0)):
        if type(result[name]) is not int or not lower <= result[name] <= 1440:
            raise ValueError(f'interaction.{name} must be {lower}..1440 minutes')
    return result


def config_at(directory):
    """OpenAI: 读取 schema-1 偏好并补齐兼容默认项；不在读取阶段迁移写盘。"""
    config = load_json(directory / 'config.json', DEFAULTS)
    if type(config.get('schema_version')) is not int or config['schema_version'] != 1:
        raise ValueError('Unsupported configuration schema; no automatic migration')
    name = config.get('human_name')
    if not isinstance(name, str) or not re.fullmatch(r'[\w\-\u4e00-\u9fff]{1,40}', name):
        raise ValueError('human_name must contain 1-40 letters, digits, underscores or hyphens')
    days = config.get('interval_days')
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError('interval_days must be an integer between 1 and 365')
    # OpenAI: Missing preferences adopt the new default; an existing false may be deliberate.
    # Preserve false and legacy intervals verbatim; health explains how to explicitly opt in.
    config.setdefault('auto_update', True)
    if type(config['auto_update']) is not bool:
        raise ValueError('auto_update must be a boolean')
    config.setdefault('human_commit_name', '主人')
    validate_commit_name(config['human_commit_name'])
    interaction_config(config)
    return config


def version_tuple(value):
    """OpenAI: 只接受三段稳定版本号，转为整数元组供新旧版本比较。"""
    if not isinstance(value, str) or not re.fullmatch(r'\d+\.\d+\.\d+', value):
        raise ValueError('Expected a stable major.minor.patch version')
    return tuple(int(part) for part in value.split('.'))


def fetch_version():
    """OpenAI: 在十秒超时与 64 KiB 大小限制内读取官方版本清单。"""
    from urllib.request import Request, urlopen
    url = f'https://raw.githubusercontent.com/{REPO}/main/skills/{NAME}/assets/version.json'
    with urlopen(Request(url, headers={'User-Agent': NAME}), timeout=10) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError('Version response too large')
    return json.loads(raw)


def state_at(directory):
    """OpenAI: 校验兼容状态与时间戳；损坏数据不得被当成首次检查绕过节流。"""
    state = load_json(directory / 'state.json', {'schema_version': 1})
    if type(state.get('schema_version')) is not int or state['schema_version'] != 1:
        raise ValueError('Unsupported state schema')
    for key in ('last_error', 'last_update_error'):
        if state.get(key) is not None and not isinstance(state[key], str):
            raise ValueError(f'Invalid state error field: {key}')
    # OpenAI: Reject booleans/NaN as timestamps before subtraction; unknown state stays fail-closed.
    for key in ('last_attempt_at', 'last_success_at', 'last_update_attempt_at', 'last_updated_at'):
        value = state.get(key)
        if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
            raise ValueError(f'Invalid state timestamp: {key}')
    if state.get('latest_version') is not None:
        version_tuple(state['latest_version'])
    return state


def within_daily_window(timestamp, now):
    """OpenAI: 最近尝试未满24小时或时钟倒退时禁止重试，不接受force豁免。"""
    # OpenAI: A future timestamp may indicate a reversed clock, never permission to retry early.
    return timestamp is not None and now - timestamp < CHECK_INTERVAL_SECONDS


def health_snapshot(directory, config, current, state, *, now=None, issues=()):
    """OpenAI: 仅凭本地事实计算健康快照；缺证据、过期和失败均不能报健康。"""
    now = time.time() if now is None else now
    reasons = list(issues)
    notes = []
    auto_update = config.get('auto_update') if config is not None else None
    if auto_update is False:
        reasons.append('auto_update_disabled')
        notes.append('Existing auto_update=false is preserved; explicitly enable automatic updates if desired.')
    elif auto_update is not True:
        reasons.append('auto_update_unknown')
    if config is not None and config['interval_days'] != 1:
        notes.append('Stored interval_days is preserved; the effective check interval is always one day.')
    try:
        installed = version_tuple(current)
    except (ValueError, TypeError):
        installed, current = None, None
        reasons.append('installed_version_unknown')
    state = state or {}
    latest = state.get('latest_version')
    try:
        upstream = version_tuple(latest)
    except (ValueError, TypeError):
        upstream, latest = None, None
        reasons.append('latest_version_unknown')
    if installed is not None and upstream is not None and installed < upstream:
        reasons.append('version_behind')
    checked_at = state.get('last_success_at')
    age = None if checked_at is None else now - checked_at
    freshness = 'unknown'
    if age is not None:
        if age < 0:
            reasons.append('clock_rollback')
        elif age >= CHECK_INTERVAL_SECONDS:
            freshness = 'stale'
            reasons.append('check_stale')
        else:
            freshness = 'fresh'
    else:
        reasons.append('check_unknown')
    # OpenAI: A fresh older success must not hide a newer failed/interrupted check or update.
    if state.get('last_error'):
        reasons.append('check_failed')
    if state.get('last_attempt_at') is not None and (
            checked_at is None or state['last_attempt_at'] > checked_at):
        reasons.append('check_incomplete')
    if state.get('last_update_error'):
        reasons.append('update_failed')
    if state.get('last_update_attempt_at') is not None and (
            state.get('last_updated_at') is None
            or state['last_update_attempt_at'] > state['last_updated_at']):
        reasons.append('update_incomplete')
    if any(state.get(key) is not None and state[key] > now
           for key in ('last_attempt_at', 'last_update_attempt_at', 'last_updated_at')):
        reasons.append('clock_rollback')
    reasons = list(dict.fromkeys(reasons))
    unknown = any(reason.endswith('_unknown') or reason.endswith('_invalid') for reason in reasons)
    return {'schema_version': HEALTH_SCHEMA_VERSION, 'skill': NAME,
            'status': ('unknown' if unknown else 'dirty') if reasons else 'healthy',
            'installed_version': current, 'latest_version': latest, 'auto_update': auto_update,
            'dirty': bool(reasons), 'reasons': reasons, 'notes': notes,
            'checked_at': checked_at, 'last_attempt_at': state.get('last_attempt_at'),
            'freshness': freshness, 'age_seconds': age,
            'expires_at': None if checked_at is None else checked_at + CHECK_INTERVAL_SECONDS,
            'evaluated_at': now, 'effective_interval_days': 1,
            'check_error': state.get('last_error'), 'update_error': state.get('last_update_error'),
            'health_path': str(directory / 'health.json')}


def persist_health(directory, config, current, state, *, now=None, issues=()):
    """OpenAI: 原子保存由本地事实生成的标准健康快照，并返回同一对象。"""
    snapshot = health_snapshot(directory, config, current, state, now=now, issues=issues)
    # OpenAI: Readers see either a complete prior snapshot or a complete replacement, never partial JSON.
    save_json(directory / 'health.json', snapshot)
    return snapshot


def refresh_health(skill, directory, *, now=None):
    """OpenAI: 离线重读磁盘配置、清单和状态；错误转为未知健康，不重置原文件。"""
    issues = []
    config, current, state = None, None, {}
    try:
        config = config_at(directory)
    except (OSError, ValueError, TypeError):
        issues.append('config_invalid')
    try:
        current = load_json(skill / 'assets/version.json', {}).get('version')
    except (OSError, ValueError, TypeError):
        issues.append('installed_manifest_invalid')
    try:
        state = state_at(directory)
    except (OSError, ValueError, TypeError):
        issues.append('state_invalid')
    # OpenAI: Do not trust a previous health.json after local edits; recompute without networking.
    return persist_health(directory, config, current, state, now=now, issues=issues)


def health_gate(snapshot, *, require_healthy=False, min_version=None, require_version=None):
    """OpenAI: 计算调用方选择的版本/健康门禁；0通过，4版本不符，3非健康。"""
    minimum = version_tuple(min_version) if min_version is not None else None
    exact = version_tuple(require_version) if require_version is not None else None
    installed = snapshot.get('installed_version')
    installed = version_tuple(installed) if installed is not None else None
    # OpenAI: A version constraint is independent of freshness; only an explicit healthy gate enforces both.
    if (minimum is not None and (installed is None or installed < minimum)) or (
            exact is not None and installed != exact):
        return 4
    if require_healthy and (snapshot['status'] != 'healthy' or snapshot['dirty']):
        return 3
    return 0


def check(directory, config, current, *, fetch=None, now=None, force=False):
    """OpenAI: 每24小时最多联网检查一次，含失败；force兼容保留但不得越过上限。"""
    now = time.time() if now is None else now
    version_tuple(current)
    state = state_at(directory)
    if within_daily_window(state.get('last_attempt_at'), now):
        health = persist_health(directory, config, current, state, now=now)
        return {'status': 'not_due', 'state': state, 'current_version': current,
                'latest_version': state.get('latest_version'), 'health': health, 'network_checked': False}
    # OpenAI: Reserve the attempt before touching the network; a killed process cannot appear healthy.
    state.update(last_attempt_at=now, last_error='check_in_progress')
    save_json(directory / 'state.json', state)
    persist_health(directory, config, current, state, now=now)
    try:
        manifest = (fetch or fetch_version)()
        if not isinstance(manifest, dict) or manifest.get('name') != NAME:
            raise ValueError('Unexpected upstream skill identity')
        latest = manifest['version']
        available = version_tuple(latest) > version_tuple(current)
        state.update(last_success_at=now, latest_version=latest, last_error=None)
        save_json(directory / 'state.json', state)
        health = persist_health(directory, config, current, state, now=now)
        return {'status': 'update_available' if available else 'up_to_date',
                'state': state, 'current_version': current, 'latest_version': latest,
                'health': health, 'network_checked': True}
    except Exception as exc:
        state['last_error'] = type(exc).__name__
        save_json(directory / 'state.json', state)
        persist_health(directory, config, current, state, now=now)
        raise


def run(args, *, env=None):
    """OpenAI: 以无交互、超时和 UTF-8 捕获执行子进程；失败只暴露命令名及退出码。"""
    import subprocess
    result = subprocess.run(args, capture_output=True, text=True, encoding='utf-8',
                            errors='replace', stdin=subprocess.DEVNULL, timeout=120,
                            env=env or dict(os.environ, GIT_TERMINAL_PROMPT='0'))
    if result.returncode:
        raise ValueError(f'Command failed ({result.returncode}): {args[0]}')
    return result.stdout.strip()


def update_git(skill, *, runner=run, before_apply=None):
    """OpenAI: 仅在官方 main 的干净独立克隆中拉取并快进，应用前复查本地冲突。"""
    # OpenAI: Compare physical paths consistently, including Windows 8.3 aliases.
    skill = skill.resolve()
    repo = skill.parent.parent
    if skill.relative_to(repo).as_posix() != f'skills/{NAME}':
        raise ValueError('Not a supported Git installation layout')
    cmd = ['git', '-C', str(repo)]
    if Path(runner(cmd + ['rev-parse', '--show-toplevel'])).resolve() != repo:
        raise ValueError('Skill is not in its own repository clone')
    remote = runner(cmd + ['remote', 'get-url', 'origin'])
    if remote not in tuple(f'https://github.com/{name}{suffix}'
                           for name in OFFICIAL_REPOS for suffix in ('', '.git')):
        raise ValueError('Unexpected update origin; refusing to change it')
    if runner(cmd + ['branch', '--show-current']) != 'main':
        raise ValueError('Only the main channel can auto-update; pinned versions stay pinned')
    if runner(cmd + ['status', '--porcelain', '--untracked-files=all']):
        raise ValueError('Repository has local edits; no overwrite')
    runner(cmd + ['fetch', '--no-tags', 'origin', 'main'])
    # OpenAI: 上游树和被忽略的本地文件都须检查；Git status 的未跟踪视图不会显示后者。
    paths = runner(cmd + ['ls-tree', '-r', '--name-only', 'FETCH_HEAD']).splitlines()
    if any('.ld-codestyle-data' in Path(path).parts for path in paths):
        raise ValueError('Upstream contains private state paths')
    ignored = runner(cmd + ['ls-files', '--others', '--ignored', '--exclude-standard', '-z']).split('\0')
    for local in filter(None, ignored):
        if any(local == remote or local.startswith(remote + '/') or remote.startswith(local + '/')
               for remote in paths):
            raise ValueError('Upstream conflicts with ignored local files')
    runner(cmd + ['merge-base', '--is-ancestor', 'HEAD', 'FETCH_HEAD'])
    if runner(cmd + ['status', '--porcelain', '--untracked-files=all']):
        raise ValueError('Repository gained local edits while fetching')
    if before_apply:
        before_apply()
    runner(cmd + ['merge', '--ff-only', '--no-overwrite-ignore', 'FETCH_HEAD'])
    return runner(cmd + ['rev-parse', 'HEAD'])


def backup_skill(skill, directory):
    """OpenAI: 只打包受支持的技能文件并校验快照，成功后最多保留两份旧快照。"""
    import zipfile
    backups = directory / 'backups'
    backups.mkdir(exist_ok=True, mode=0o700)
    def ordered_snapshots():
        """OpenAI: 只选数字编号的备份文件，按序号而非字典序排列。"""
        # OpenAI: Preserve unrelated files and order legacy numeric names without lexical ambiguity.
        return sorted((path for path in backups.glob('snapshot-*.zip')
                       if re.fullmatch(r'snapshot-[0-9]+\.zip', path.name)),
                      key=lambda path: int(path.stem.removeprefix('snapshot-')))
    existing = ordered_snapshots()
    sequence = max(time.time_ns(),
                   int(existing[-1].stem.removeprefix('snapshot-')) + 1 if existing else 0)
    # OpenAI: Coarse or reversed clocks must not reuse names; exclusive creation handles contention.
    for _ in range(100):
        target = backups / f'snapshot-{sequence}.zip'
        try:
            archive = zipfile.ZipFile(target, 'x', compression=zipfile.ZIP_DEFLATED)
            break
        except FileExistsError:
            sequence += 1
    else:
        raise FileExistsError('Could not reserve a unique snapshot after 100 attempts; old snapshots retained')
    with archive as out:
        for path in sorted(skill.rglob('*')):
            # OpenAI: 排除私有状态、隐藏路径及凭据，避免将安装数据带入可恢复的技能快照。
            if path.is_relative_to(directory) or '.ld-codestyle-data' in path.relative_to(skill).parts:
                continue
            relative = path.relative_to(skill)
            if any(part.startswith('.') for part in relative.parts):
                continue
            if relative.parts[0] not in ('SKILL.md', 'references', 'scripts', 'assets', 'templates'):
                continue
            if path.name.lower() in ('credentials.json', 'auth.json', 'secrets.json'):
                continue
            if path.is_symlink():
                raise ValueError('Unexpected symlink in skill; review before updating')
            if path.is_file():
                out.write(path, path.relative_to(skill).as_posix())
    target.chmod(0o600)
    with zipfile.ZipFile(target) as verify:
        if verify.testzip() is not None:
            raise ValueError('Snapshot verification failed; old snapshots retained')
    for old in [path for path in ordered_snapshots() if path != target][:-2]:
        old.unlink()
    return str(target)


def validate_native_source(entry):
    """OpenAI: 核对原生管理器的来源、官方仓库标识与固定提交 URL。"""
    prefixes = {'github': '', 'skills.sh': 'skills-sh/', 'skills-sh': 'skills-sh/'}
    source = entry.get('source')
    if source not in prefixes or entry.get('identifier') not in {
        f'{prefixes[source]}{repo}/skills/{NAME}' for repo in OFFICIAL_REPOS
    }:
        raise ValueError('Native manager source identity mismatch')
    url = entry.get('metadata', {}).get('source_url', '')
    repos = '|'.join(re.escape(repo) for repo in OFFICIAL_REPOS)
    pattern = rf'https://github\.com/(?:{repos})/tree/[0-9a-f]{{40}}/skills/{NAME}/?'
    if not re.fullmatch(pattern, url):
        raise ValueError('Native manager source URL is not this official pinned skill')


def apply_update(skill, directory):
    """OpenAI: 按 Hermes 原生安装或独立 Git 克隆选择受支持的更新路径并返回收据。"""
    home = hermes_home(skill)
    if home:
        if directory.is_relative_to(skill):
            raise ValueError('Hermes update requires a data directory outside the skill')
        lock = load_json(home / 'skills/.hub/lock.json', {})
        entry = lock.get('installed', {}).get(NAME, {})
        validate_native_source(entry)
        if (home / 'skills' / entry.get('install_path', '')).resolve() != skill:
            raise ValueError('Native manager target mismatch')
        backup = backup_skill(skill, directory)
        env = dict(os.environ, HERMES_HOME=str(home), PYTHONDONTWRITEBYTECODE='1')
        env.pop('HERMES_SESSION_PROFILE', None)
        run(['hermes', 'skills', 'update', NAME], env=env)
        return {'backend': 'hermes', 'backup': backup}
    if not (skill.parent.parent / '.git').exists():
        raise ValueError('No supported updater; install via Hermes or an independent Git clone')
    receipt = {'backend': 'git'}
    def snapshot():
        """OpenAI: 在 Git 快进前创建技能快照并附到更新收据。"""
        receipt['backup'] = backup_skill(skill, directory)
    receipt['revision'] = update_git(skill, before_apply=snapshot)
    return receipt


def synchronize(skill, directory, config, *, idle, force=False, approved=False, fetch=None, updater=None,
                now=None):
    """OpenAI: 在空档应用新鲜缓存的新版本；检查及后端尝试各受24小时硬上限。"""
    now = time.time() if now is None else now
    current = load_json(skill / 'assets/version.json', {})['version']
    result = check(directory, config, current, force=force, fetch=fetch, now=now)
    state = result['state']
    latest = state.get('latest_version')
    if (latest is None or version_tuple(latest) <= version_tuple(current)
            or state.get('last_error') or result['health']['freshness'] != 'fresh'):
        return result
    if config.get('auto_update') is not True and not approved:
        # OpenAI: A legacy false remains a preference; checking never silently re-enables updates.
        if result['status'] == 'not_due':
            return result
        return {**result, 'status': 'update_confirmation_required'}
    if not idle:
        return {**result, 'status': 'deferred_until_idle'}
    if within_daily_window(state.get('last_update_attempt_at'), now):
        return {**result, 'status': 'update_retry_not_due'}
    state.update(last_update_attempt_at=now, last_update_error='update_in_progress')
    save_json(directory / 'state.json', state)
    persist_health(directory, config, current, state, now=now)
    # OpenAI: Reserve downloads separately so a cached check can update later today, never retry endlessly.
    try:
        receipt = (updater or apply_update)(skill, directory)
        after = load_json(skill / 'assets/version.json', {})['version']
        if version_tuple(after) < version_tuple(latest):
            raise ValueError('Updater did not install the expected version; inspect native output/local edits')
    except Exception as exc:
        state['last_update_error'] = type(exc).__name__
        try:
            state['observed_version'] = load_json(skill / 'assets/version.json', {}).get('version')
        except (OSError, ValueError):
            state['observed_version'] = None
        save_json(directory / 'state.json', state)
        # OpenAI: A failed native updater may have partially changed files; report the observed disk version.
        persist_health(directory, config, state['observed_version'], state, now=now)
        raise
    state.update(installed_version=after, observed_version=after,
                 last_updated_at=now, last_update_error=None)
    save_json(directory / 'state.json', state)
    health = persist_health(directory, config, after, state, now=now)
    return {**result, **receipt, 'status': 'updated', 'installed_version': after, 'health': health}


def identity_module():
    """OpenAI: 从同目录加载纯身份模块，兼容直接CLI与importlib方式导入维护脚本。"""
    # OpenAI: Resolve relative to this script rather than caller cwd or an unrelated module on sys.path.
    spec = importlib.util.spec_from_file_location('ld_commit_identity', Path(__file__).with_name('commit_identity.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def commit_header(config, model, bot, summary, *, mixed_human=False, client='',
                  named_bot=False, computer_name=None, visibility=None, reasoning_effort=None,
                  public_name=None, omit_public_identity=False, pc=None):
    """OpenAI: 兼容旧函数入口并委派独立身份模块；所有新增身份参数显式透传。"""
    return identity_module().commit_header(
        config, model, bot, summary, mixed_human=mixed_human, client=client,
        named_bot=named_bot, computer_name=computer_name, visibility=visibility,
        reasoning_effort=reasoning_effort, public_name=public_name,
        omit_public_identity=omit_public_identity, pc=pc)


def header_result(args, config):
    """OpenAI: 将CLI参数映射到身份模块，返回首行和供Git显示名使用的相同身份。"""
    return identity_module().commit_result(
        config, args.model, args.bot, args.summary, mixed_human=args.mixed_human,
        client=args.client, named_bot=args.named_bot, computer_name=args.computer_name,
        visibility=args.visibility, reasoning_effort=args.reasoning_effort,
        public_name=args.public_name, omit_public_identity=args.omit_public_identity, pc=args.pc)


def maintenance_result(args, skill, directory):
    """OpenAI: 在调用方持锁期间执行偏好、检查或更新，并返回兼容的CLI结果。"""
    config = config_at(directory)
    if args.command == 'config':
        candidate = dict(config)
        if args.human_name is not None:
            candidate['human_name'] = args.human_name
        if args.human_commit_name is not None:
            candidate['human_commit_name'] = args.human_commit_name
        if args.interval_days is not None:
            # OpenAI: Legacy values survive reads; new writes must not imply unsupported weekly scheduling.
            if args.interval_days != 1:
                raise ValueError('The effective interval is daily; new interval_days values must be 1')
            candidate['interval_days'] = args.interval_days
        if args.auto_update is not None:
            candidate['auto_update'] = args.auto_update == 'on'
        if any(value is not None for value in (args.interaction, args.answer_wait_minutes,
                                               args.idle_after_minutes)):
            settings = interaction_config(candidate)
            if args.interaction is not None:
                settings['enabled'] = args.interaction == 'on'
            if args.answer_wait_minutes is not None:
                settings['answer_wait_minutes'] = args.answer_wait_minutes
            if args.idle_after_minutes is not None:
                settings['idle_after_minutes'] = args.idle_after_minutes
            candidate['interaction'] = settings
            interaction_config(candidate)
        if not re.fullmatch(r'[\w\-\u4e00-\u9fff]{1,40}', candidate['human_name']):
            raise ValueError('Invalid human name')
        validate_commit_name(candidate['human_commit_name'])
        config = candidate
    if args.command == 'commit-header':
        result = header_result(args, config)
    else:
        save_json(directory / 'config.json', config)
        result = {'state': state_at(directory)}
        if args.command == 'check':
            current = load_json(skill / 'assets/version.json', {})['version']
            result = check(directory, config, current, force=args.force)
        elif args.command == 'sync':
            result = synchronize(skill, directory, config, idle=args.idle,
                                 force=args.force, approved=args.approve_update)
    return {'data_dir': str(directory), 'config_path': str(directory / 'config.json'),
            'config': config, 'interaction': interaction_config(config),
            'effective_interval_days': 1, **result}


def main():
    """OpenAI: 解析CLI并在锁内刷新健康；只有依赖方选择的health门禁返回拒绝码。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--data-root', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('show')
    health = commands.add_parser('health', help='Recompute and persist local health without network access')
    health.add_argument('--require-healthy', action='store_true', help='Exit 3 unless fresh and healthy')
    health.add_argument('--min-version', help='Exit 4 if installed version is unknown or below this stable version')
    health.add_argument('--require-version', help='Exit 4 unless installed version exactly matches')
    header = commands.add_parser('commit-header', help='Render a header; does not stage, commit, push or inspect Git')
    header.add_argument('--visibility', choices=('public', 'private'), required=True,
                        help='Caller-verified destination visibility')
    header.add_argument('--model', help='Verified complete runtime model ID; never inferred from product')
    header.add_argument('--bot', default='')
    header.add_argument('--client', default='', help='Actual execution framework, such as Codex')
    header.add_argument('--named-bot', action='store_true',
                        help='Caller verified a Bot with its own persistent identity and memory')
    header.add_argument('--reasoning-effort', help='Actual reasoning strength; none only when no control exists')
    public = header.add_mutually_exclusive_group()
    public.add_argument('--public-name', help='Explicitly authorized public display name override')
    public.add_argument('--omit-public-identity', action='store_true', help='Explicitly authorized public omission')
    header.add_argument('--pc', help='Explicitly provided computer name; never read from this OS')
    header.add_argument('--computer-name', help='Compatibility alias for explicitly provided --pc')
    header.add_argument('--summary', required=True)
    header.add_argument('--mixed-human', action='store_true',
                        help='Caller has verified human contribution in the staged change')
    configure = commands.add_parser('config')
    configure.add_argument('--human-name')
    configure.add_argument('--human-commit-name')
    configure.add_argument('--interval-days', type=int)
    configure.add_argument('--auto-update', choices=('on', 'off'))
    configure.add_argument('--interaction', choices=('on', 'off'))
    configure.add_argument('--answer-wait-minutes', type=int)
    configure.add_argument('--idle-after-minutes', type=int)
    for command in ('check', 'sync'):
        sub = commands.add_parser(command)
        sub.add_argument('--force', action='store_true', help='Compatibility flag; never bypass the 24-hour limit or safety guards')
        if command == 'sync':
            sub.add_argument('--idle', action='store_true', help='Caller confirms no task uses this installation')
            sub.add_argument('--approve-update', action='store_true',
                             help='Caller has explicit user approval for this update only')
    args = parser.parse_args()
    if args.command == 'commit-header' and args.visibility == 'public':
        # OpenAI: Public output never loads local preferences or queries the machine identity.
        try:
            result = header_result(args, None)
        except (OSError, ValueError, TypeError) as exc:
            print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=True))
            return 1
        print(json.dumps(result, ensure_ascii=True))
        return 0
    skill = args.skill_root.resolve()
    directory = data_dir(skill, args.data_root)
    snapshot = None
    exit_code = 0
    try:
        with locked(directory):
            if args.command == 'health':
                # OpenAI: Reject malformed caller constraints before publishing a successful local report.
                for constraint in (args.min_version, args.require_version):
                    if constraint is not None:
                        version_tuple(constraint)
                snapshot = refresh_health(skill, directory)
                exit_code = health_gate(snapshot, require_healthy=args.require_healthy,
                                        min_version=args.min_version, require_version=args.require_version)
                result = {**snapshot, 'gate_exit_code': exit_code}
            else:
                try:
                    result = maintenance_result(args, skill, directory)
                finally:
                    # OpenAI: Refresh while still holding the writer lock, including failed checks/updates.
                    if args.command != 'commit-header':
                        snapshot = refresh_health(skill, directory)
                if snapshot is not None:
                    result['health'] = snapshot
            # OpenAI: ASCII JSON preserves Unicode values across legacy Windows console encodings.
            print(json.dumps(result, ensure_ascii=True))
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        result = {'status': 'error', 'error': str(exc)}
        if args.command == 'health':
            # OpenAI: Lock/I/O failures cannot safely persist a new snapshot; stdout must still fail closed.
            result = {**health_snapshot(directory, None, None, {}, issues=('health_unavailable',)),
                      **result, 'health_persisted': False}
        elif snapshot is not None:
            result['health'] = snapshot
        print(json.dumps(result, ensure_ascii=True))
        return 1
    return exit_code

if __name__ == '__main__':
    raise SystemExit(main())
