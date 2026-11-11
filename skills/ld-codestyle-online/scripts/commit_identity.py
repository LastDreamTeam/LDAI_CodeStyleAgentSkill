# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: Pure commit identity rendering; caller declarations never prove runtime identity."""
import re

_PRODUCT_ALIASES = {'OpenAI Codex': 'Codex', 'OpenAICodex': 'Codex'}
_REASONING_EFFORTS = frozenset(('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max'))
_NON_MODELS = frozenset((
    'ai', 'agent', 'assistant', 'bot', 'model', 'modelid', 'modelname', 'openai',
    'anthropic', 'google', 'xai', 'deepseek', 'codex', 'openaicodex', 'claudecode',
    'cursor', 'copilot', 'githubcopilot', 'chatgpt', 'deepseekharness', 'vscodecopilot',
    'visualstudiocopilot', 'vscode', 'visualstudio', 'otheragentplugin', 'hermes',
    'hermesbot', 'dsh', 'dshbot', 'gpt', 'sol', 'gptsol', 'claude', 'gemini', 'grok',
    'opus', 'sonnet', 'haiku', 'unknown', 'unknownmodel', 'actualmodel', 'actualmodelid',
    'yourmodel', 'unspecified', 'na', 'auto', 'default', 'latest', 'none', 'null',
    'placeholder', 'tbd', 'todo',
    '未知', '待确认', '实际模型标识', '实际模型型号', '完整型号',
))
_DEFAULT_BOT_NAMES = _NON_MODELS | frozenset(('dot', 'grokbot', 'gptbot', 'gptdot',
                                            'chatgptbot', '助手'))
_IDENTITY_STRUCTURE = re.compile(r'(?:模型|计算机|(?<![A-Za-z0-9_])PC)\s*[:：]', re.IGNORECASE)
_EMBEDDED_EFFORT = re.compile(r'^(.*?) (none|minimal|low|medium|high|xhigh|max)$', re.IGNORECASE)


def _text(value, field, *, forbidden='|'):
    """OpenAI: 校验单行原值并原样返回；错误只含字段名，不回显潜在敏感输入。"""
    if (not isinstance(value, str) or not value or not value.isprintable()
            or value != value.strip() or any(char in value for char in forbidden)):
        raise ValueError(f'{field} must be non-empty single-line text without identity delimiters')
    return value


def _normalized(value):
    """OpenAI: 仅为拒绝已知笼统名称建立比较键，不用于改写输出身份。"""
    return re.sub(r'[\s_./-]+', '', value).casefold()


def _name(value, field):
    """OpenAI: 校验框架、昵称或公开名称的结构，保留合法原值和大小写。"""
    value = _text(value, field, forbidden='#|+:：<>[]{}')
    if _IDENTITY_STRUCTURE.search(value):
        raise ValueError(f'{field} must not contain embedded identity fields')
    if _normalized(value) in {'unknown', 'auto', 'default', 'placeholder', 'tbd', '未知', '待确认'}:
        raise ValueError(f'{field} requires an explicit name, not a placeholder')
    return value


def _effort(value, *, required):
    """OpenAI: 只接受显式实际推理档位；none 声明无推理控制，缺失不自动变成 none。"""
    # OpenAI: 公开可没有档位；私有缺值不能自动降为 none，以免把未知写成已知事实。
    if value is None and not required:
        return None
    if not isinstance(value, str) or value not in _REASONING_EFFORTS:
        raise ValueError('An actual reasoning_effort is required: none, minimal, low, medium, high, xhigh or max')
    return value


def _model(value, effort):
    """OpenAI: 返回完整输入、纯型号及已匹配的尾部强度；只识别明确一致的空格档位。"""
    original = _text(value, 'model', forbidden='#|+<>[]{}')
    # OpenAI: 厂商命名空间、版本、大小写和连字符后缀均属型号；不得靠猜测缩短。
    match = _EMBEDDED_EFFORT.fullmatch(original)
    base = original
    embedded = False
    if match:
        if effort is None or match[2].casefold() != effort or _EMBEDDED_EFFORT.fullmatch(match[1]):
            raise ValueError('Separate the exact model and its matching actual reasoning_effort')
        base = match[1]
        embedded = True
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/@: -]*', base)
            or base != base.strip() or _IDENTITY_STRUCTURE.search(base)):
        raise ValueError('model must be an exact identifier without embedded identity fields')
    leaf = base.rsplit('/', 1)[-1]
    if _normalized(base) in _NON_MODELS or _normalized(leaf) in _NON_MODELS:
        raise ValueError('A verified complete model identifier is required; generic names and placeholders are invalid')
    return original, base, embedded


def _bot_name(bot, named_bot):
    """OpenAI: 验证昵称与独立 Bot 声明成对出现；此声明不认证人格或长期资料。"""
    if not isinstance(bot, str):
        raise ValueError('bot must be a nickname string or an empty string for an Agent')
    if not bot:
        if named_bot:
            raise ValueError('named_bot requires a real Bot nickname and independent identity records')
        return ''
    # OpenAI: 昵称本身无法区分 Bot 与工具会话，必须连同真实身份资料声明提供。
    if not named_bot:
        raise ValueError('A session nickname is not a Bot; named_bot must declare independent identity and memory')
    bot = _name(bot, 'bot')
    if _normalized(bot) in _DEFAULT_BOT_NAMES:
        raise ValueError('bot requires a distinctive nickname, not a framework or default assistant name')
    return bot


def _pc(pc, computer_name):
    """OpenAI: 只渲染显式主机值；两个兼容参数冲突时报错，绝不读取操作系统。"""
    # OpenAI: 显式冲突不能靠参数优先级静默覆盖，也不能用本机主机名作为缺值兜底。
    if pc is not None and computer_name is not None and pc != computer_name:
        raise ValueError('pc and computer_name must agree when both are supplied')
    value = pc if pc is not None else computer_name
    if value is None:
        return ''
    if not isinstance(value, str) or not re.fullmatch(r'[\w.-]{1,253}', value):
        raise ValueError('pc must be an explicitly verified execution host name')
    return f' PC:{value}'


def commit_identity(model=None, bot='', *, client='', named_bot=False, computer_name=None,
                    visibility=None, reasoning_effort=None, public_name=None,
                    omit_public_identity=False, pc=None):
    """OpenAI: 按已核目标返回可复用的真实身份字符串，省略公开身份时返回空串。

    私有 Bot 需要框架、昵称和独立身份声明；私有 Agent 需要框架、完整型号及实际
    推理强度。公开默认返回 Bot 昵称或型号；公开覆盖由调用方传达用户明确要求。
    函数无文件、主机或 Git 副作用；不验证调用者的运行身份、授权或资料真实性。
    """
    if visibility not in ('public', 'private'):
        raise ValueError('Verify the destination and explicitly select public or private visibility')
    if type(named_bot) is not bool or type(omit_public_identity) is not bool:
        raise ValueError('Identity declaration flags must be boolean')
    if public_name is not None and omit_public_identity:
        raise ValueError('Choose either public_name or omit_public_identity')
    if visibility == 'private' and (public_name is not None or omit_public_identity):
        raise ValueError('Public identity overrides cannot weaken private identity requirements')

    # OpenAI: 明确公开覆盖先于内部身份字段处理，避免读取、验证或泄漏无关私有资料。
    if visibility == 'public':
        if omit_public_identity:
            return ''
        if public_name is not None:
            return _name(public_name, 'public_name')

    bot = _bot_name(bot, named_bot)
    if visibility == 'public':
        if bot:
            return bot
        effort = _effort(reasoning_effort, required=False)
        return _model(model, effort)[1]

    client = _name(client, 'client')
    client = _PRODUCT_ALIASES.get(client, client)
    if bot:
        rendered = f'{client}-{bot}'
    else:
        effort = _effort(reasoning_effort, required=True)
        original, base, embedded = _model(model, effort)
        if _normalized(base) == _normalized(client):
            raise ValueError('model must identify the runtime model, not repeat its framework')
        # OpenAI: 已提供完整“型号 档位”时保留原串，私有身份不再重复追加相同强度。
        rendered = f'{client} {original}' if embedded else f'{client} {original} {effort}'
    return rendered + _pc(pc, computer_name)


def commit_result(config, model, bot, summary, *, mixed_human=False, client='',
                  named_bot=False, computer_name=None, visibility=None, reasoning_effort=None,
                  public_name=None, omit_public_identity=False, pc=None):
    """OpenAI: 返回 header、identity、visibility；身份可供获准的 Git 显示名复用。

    config 仅在私有混合贡献时读取 human_commit_name，且不修改传入对象；公开输出
    不读取私人配置或回显私有字段。summary 仍需调用方完成内容与隐私审核。
    """
    summary = _text(summary, 'summary')
    if type(mixed_human) is not bool:
        raise ValueError('mixed_human must be boolean')
    if _IDENTITY_STRUCTURE.search(summary):
        raise ValueError('Summary must not reintroduce model or computer identity fields')
    rendered = commit_identity(model, bot, client=client, named_bot=named_bot,
                               computer_name=computer_name, visibility=visibility,
                               reasoning_effort=reasoning_effort, public_name=public_name,
                               omit_public_identity=omit_public_identity, pc=pc)
    human = ''
    if visibility == 'private' and mixed_human:
        if not isinstance(config, dict) or 'human_commit_name' not in config:
            raise ValueError('Private mixed attribution requires configured human_commit_name')
        name = _name(config['human_commit_name'], 'human_commit_name')
        if len(name) > 40 or any(char in name for char in '【】'):
            raise ValueError('human_commit_name must be at most 40 visible characters without header delimiters')
        human = f'{name} + '
    # OpenAI: 公开混合贡献只在正文说明范围，不把私有人类显示名带进生成结果。
    header = f'##{human}模型：{rendered} | {summary}' if rendered else summary
    return {'header': header, 'identity': rendered, 'visibility': visibility}


def commit_header(config, model, bot, summary, *, mixed_human=False, client='',
                  named_bot=False, computer_name=None, visibility=None, reasoning_effort=None,
                  public_name=None, omit_public_identity=False, pc=None):
    """OpenAI: 保留旧可导入调用签名并追加新选项，返回经身份规则验证的提交首行。"""
    return commit_result(config, model, bot, summary, mixed_human=mixed_human, client=client,
                         named_bot=named_bot, computer_name=computer_name, visibility=visibility,
                         reasoning_effort=reasoning_effort, public_name=public_name,
                         omit_public_identity=omit_public_identity, pc=pc)['header']
