# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: Per-install preferences and bounded, native-backend maintenance."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import time

NAME = 'ld-codestyle-online'
REPO = 'LastDreamTeam/LDAI_CodeStyleAgentSkill'
# OpenAI: The sole previous repository name is an explicit alias, not a wildcard trust rule.
OFFICIAL_REPOS = (REPO, 'LastDreamTeam/LDCodeStyleAgentSkill')
DEFAULTS = {'schema_version': 1, 'human_name': 'LD', 'human_commit_name': '主人',
            'interval_days': 7, 'auto_update': False}
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
    """OpenAI: 先写入同目录临时文件并同步，再原子替换目标 JSON。"""
    fd, name = tempfile.mkstemp(prefix='.writing-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(value, out, ensure_ascii=False, indent=2)
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
    if config.get('schema_version') != 1:
        raise ValueError('Unsupported configuration schema; no automatic migration')
    name = config.get('human_name')
    if not isinstance(name, str) or not re.fullmatch(r'[\w\-\u4e00-\u9fff]{1,40}', name):
        raise ValueError('human_name must contain 1-40 letters, digits, underscores or hyphens')
    days = config.get('interval_days')
    if type(days) is not int or not 1 <= days <= 365:
        raise ValueError('interval_days must be an integer between 1 and 365')
    # OpenAI: Older schema-1 installs inherit the safer opt-in policy, preserving all preferences.
    config.setdefault('auto_update', False)
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


def check(directory, config, current, *, fetch=None, now=None, force=False):
    """OpenAI: 按间隔检查上游版本，记录尝试、成功或错误状态并返回更新判定。"""
    now = time.time() if now is None else now
    state = load_json(directory / 'state.json', {'schema_version': 1})
    if state.get('schema_version') != 1:
        raise ValueError('Unsupported state schema')
    last = state.get('last_attempt_at')
    if not force and last is not None and 0 <= now - last < config['interval_days'] * 86400:
        return {'status': 'not_due', 'state': state, 'current_version': current}
    # OpenAI: 先记录尝试时间再触网；即使抓取失败也受同一间隔约束，避免失败后密集重试。
    state['last_attempt_at'] = now
    save_json(directory / 'state.json', state)
    try:
        manifest = (fetch or fetch_version)()
        if manifest.get('name') != NAME:
            raise ValueError('Unexpected upstream skill identity')
        latest = manifest['version']
        available = version_tuple(latest) > version_tuple(current)
        state.update(last_success_at=now, latest_version=latest, last_error=None)
        save_json(directory / 'state.json', state)
        return {'status': 'update_available' if available else 'up_to_date',
                'state': state, 'current_version': current, 'latest_version': latest}
    except Exception as exc:
        state['last_error'] = type(exc).__name__
        save_json(directory / 'state.json', state)
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


def synchronize(skill, directory, config, *, idle, force=False, approved=False, fetch=None, updater=None):
    """OpenAI: 协调版本检查、用户同意、空闲条件、重试间隔和更新后版本核验。"""
    current = load_json(skill / 'assets/version.json', {})['version']
    result = check(directory, config, current, force=force, fetch=fetch)
    state = result['state']
    latest = state.get('latest_version', current)
    if version_tuple(latest) <= version_tuple(current):
        return result
    if config.get('auto_update') is not True and not approved:
        # OpenAI: Frequency bypass is not consent; do not re-prompt within the same interval.
        if result['status'] == 'not_due':
            return result
        return {**result, 'status': 'update_confirmation_required'}
    if not idle:
        return {**result, 'status': 'deferred_until_idle'}
    now = time.time()
    attempt = state.get('last_update_attempt_at')
    if not force and attempt is not None and 0 <= now - attempt < config['interval_days'] * 86400:
        return {**result, 'status': 'update_retry_not_due'}
    state['last_update_attempt_at'] = now
    save_json(directory / 'state.json', state)
    # OpenAI: 更新时间戳先落盘，更新器报错时再记录实际可观察到的版本，不能假定回滚成功。
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
        raise
    state.update(installed_version=after, observed_version=after,
                 last_updated_at=time.time(), last_update_error=None)
    save_json(directory / 'state.json', state)
    return {**result, **receipt, 'status': 'updated', 'installed_version': after}


def commit_header(config, model, bot, summary, *, mixed_human=False, client='',
                  named_bot=False, computer_name=None, visibility=None):
    """OpenAI: 按已核实的可见性渲染提交首行；公开摘要不读取本机及个人身份。"""
    # OpenAI: Render an already-reviewed attribution decision; never guess authorship from a word match.
    if visibility not in ('public', 'private'):
        raise ValueError('Verify the destination and explicitly select public or private visibility')
    if visibility == 'public':
        if (not isinstance(summary, str) or not summary or not summary.isprintable()
                or summary != summary.strip() or '|' in summary):
            raise ValueError('Summary must be non-empty single-line text without pipe delimiters')
        if re.search(r'(?:模型|计算机|(?<![A-Za-z0-9_])PC)\s*[:：]', summary, re.IGNORECASE):
            raise ValueError('Public summary must not reintroduce model or computer identity fields')
        return summary
    for value in (model, summary) + tuple(value for value in (bot, client) if value):
        if (not isinstance(value, str) or not value or not value.isprintable()
                or value != value.strip() or '|' in value):
            raise ValueError('Commit fields must be non-empty single-line text without pipe delimiters')
    if any(token in value for value in (model, bot or '', client or '')
           for token in (' + ', '模型：', '计算机：', '##')) or any(
               re.search(r'(?<![A-Za-z0-9_])PC\s*[:：]', value, re.IGNORECASE)
               for value in (model, bot or '', client or '')):
        raise ValueError('Client/Bot/model must not contain extra header identity structure')
    # Keep the model identifier intact; only explicitly known product aliases are shortened.
    product_aliases = {'OpenAI Codex': 'Codex', 'OpenAICodex': 'Codex'}
    bot = product_aliases[bot] if bot in product_aliases else bot
    client = product_aliases[client] if client in product_aliases else client
    if bot and client:
        raise ValueError('Choose a local client or a Bot identity, not both')
    # These are known non-model labels, not a catalogue of valid or available models.
    non_models = {'ai', 'agent', 'assistant', 'bot', 'openai', 'anthropic', 'google', 'xai', 'deepseek',
                  'codex', 'openaicodex', 'claudecode', 'cursor', 'copilot', 'githubcopilot',
                  'chatgpt', 'deepseekharness', 'vscodecopilot', 'visualstudiocopilot',
                  'vscode', 'visualstudio', 'otheragentplugin',
                  'hermes', 'hermesbot', 'unknown', 'auto', 'default', 'latest',
                  '未知', '待确认', '实际模型标识', '实际模型型号'}
    normalized_model = re.sub(r'[\s_-]+', '', model).casefold()
    if (normalized_model in non_models or '<' in model or '>' in model
            or model.casefold() in {value.casefold() for value in (bot, client) if value}):
        raise ValueError('A verified exact model identifier is required; product names and placeholders are not models')
    if named_bot:
        # OpenAI: The flag attests a reviewed unique identity; familiar product/default names are not unique Bots.
        default_names = {'ai', 'agent', 'assistant', 'bot', 'dot', 'hermes', 'hermesbot',
                         'grok', 'grokbot', 'gpt', 'gptbot', 'gptdot', 'chatgpt', 'chatgptbot',
                         'codex', 'openaicodex', 'claude', 'claudecode', 'cursor', 'vscode',
                         'visualstudio', 'visualstudiocopilot', 'vscodecopilot', 'copilot',
                         'githubcopilot', 'deepseekharness', 'otheragentplugin', '助手'}
        normalized = re.sub(r'[\s_-]+', '', bot).casefold()
        if not bot or client or normalized in default_names:
            raise ValueError('named-bot requires a verified distinctive Bot name; default/local clients need a computer name')
    machine = ''
    if not named_bot or computer_name is not None:
        actual = socket.gethostname() if computer_name is None else computer_name
        if not isinstance(actual, str) or not re.fullmatch(r'[\w.-]{1,253}', actual):
            raise ValueError('A real computer name is required; verify the execution host, do not invent a fallback')
        machine = f' PC:{actual}'
    name = config['human_commit_name']
    validate_commit_name(name)
    human = f'{name} + ' if mixed_human else ''
    actor = bot or client
    identity = f'{actor} + {model}' if actor else model
    return f'##{human}模型：{identity}{machine} | {summary}'


def main():
    """OpenAI: 解析维护与提交头命令，公开渲染走免配置路径，其余操作受安装锁保护。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--data-root', type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('show')
    header = commands.add_parser('commit-header', help='Render a header; does not stage, commit, push or inspect Git')
    header.add_argument('--visibility', choices=('public', 'private'), required=True,
                        help='Caller-verified destination visibility; public omits identity')
    header.add_argument('--model', help='Verified exact runtime model ID; required for private, never inferred from product')
    actor = header.add_mutually_exclusive_group()
    actor.add_argument('--bot', default='')
    actor.add_argument('--client', default='', help='Product short name, such as Codex; not a vendor or GitHub account')
    header.add_argument('--named-bot', action='store_true',
                        help='Caller verified a distinctive non-default Bot identity; may omit the computer name')
    header.add_argument('--computer-name', help='Verified execution host rendered as PC:<name>; otherwise query this OS')
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
        sub.add_argument('--force', action='store_true', help='Bypass time interval only; never overwrite edits')
        if command == 'sync':
            sub.add_argument('--idle', action='store_true', help='Caller confirms no task uses this installation')
            sub.add_argument('--approve-update', action='store_true',
                             help='Caller has explicit user approval for this update only')
    args = parser.parse_args()
    if args.command == 'commit-header' and args.visibility == 'public':
        # OpenAI: Public output never loads local preferences or queries the machine identity.
        try:
            value = commit_header(None, None, '', args.summary, visibility='public')
        except ValueError as exc:
            print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=True))
            return 1
        print(json.dumps({'header': value, 'visibility': 'public'}, ensure_ascii=True))
        return 0
    skill = args.skill_root.resolve()
    directory = data_dir(skill, args.data_root)
    try:
        with locked(directory):
            config = config_at(directory)
            if args.command == 'config':
                candidate = dict(config)
                if args.human_name is not None:
                    candidate['human_name'] = args.human_name
                if args.human_commit_name is not None:
                    candidate['human_commit_name'] = args.human_commit_name
                if args.interval_days is not None:
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
                if not 1 <= candidate['interval_days'] <= 365:
                    raise ValueError('interval_days must be 1..365')
                validate_commit_name(candidate['human_commit_name'])
                config = candidate
            if args.command != 'commit-header':
                save_json(directory / 'config.json', config)
            result = {'state': load_json(directory / 'state.json', {})}
            if args.command == 'check':
                current = load_json(skill / 'assets/version.json', {})['version']
                result = check(directory, config, current, force=args.force)
            elif args.command == 'sync':
                result = synchronize(skill, directory, config, idle=args.idle,
                                     force=args.force, approved=args.approve_update)
            elif args.command == 'commit-header':
                result = {'header': commit_header(config, args.model, args.bot, args.summary,
                                                  mixed_human=args.mixed_human, client=args.client,
                                                  named_bot=args.named_bot, computer_name=args.computer_name,
                                                  visibility=args.visibility)}
            # OpenAI: ASCII JSON preserves Unicode values across legacy Windows console encodings.
            print(json.dumps({'data_dir': str(directory), 'config_path': str(directory/'config.json'),
                              'config': config, 'interaction': interaction_config(config),
                              **result}, ensure_ascii=True))
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'status': 'error', 'error': str(exc)}, ensure_ascii=True))
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
