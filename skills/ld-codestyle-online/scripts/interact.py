# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: Collect local decisions; never execute options or grant approval."""
import argparse
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import re
import secrets
from socketserver import TCPServer
import threading
import time
from typing import cast


def validate_question(value):
    """OpenAI: 验证问题身份、文本与选项边界，并复制载荷避免调用者事后改题。"""
    if not isinstance(value, dict):
        raise ValueError('Question must be an object')
    for key in ('request_id', 'session_id', 'revision'):
        if not isinstance(value.get(key), str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', value[key]):
            raise ValueError('Invalid question identity: ' + key)
    for key, maximum in (('title', 200), ('question', 8000)):
        text = value.get(key)
        if not isinstance(text, str) or not text.strip() or len(text) > maximum or '\x00' in text:
            raise ValueError('Invalid question text: ' + key)
    options = value.get('options', [])
    if not isinstance(options, list) or len(options) > 6:
        raise ValueError('Expected at most six options')
    ids = set()
    for item in options:
        if (not isinstance(item, dict) or not isinstance(item.get('id'), str)
                or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', item['id'])):
            raise ValueError('Invalid option id')
        if item['id'] in ids or item['id'] == '__custom__':
            raise ValueError('Duplicate/reserved option id')
        ids.add(item['id'])
        for key, maximum in (('label', 200), ('detail', 2000)):
            text = item.get(key, '')
            if not isinstance(text, str) or len(text) > maximum or '\x00' in text or (key == 'label' and not text.strip()):
                raise ValueError('Invalid option text')
    if value.get('recommended_id') is not None and value['recommended_id'] not in ids:
        raise ValueError('Recommended option is missing')
    return copy.deepcopy(value)


class QuestionSession:
    """OpenAI: One immutable question, one answer, monotonic delivery/answer deadlines."""

    def __init__(self, question, answer_seconds, delivery_seconds, clock=time.monotonic):
        """OpenAI: 固定问题快照与单调时钟，分别维护送达和展示后的回答时限。"""
        self.question = validate_question(question)
        for value in (answer_seconds, delivery_seconds):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 86400:
                raise ValueError('Expected a positive finite timeout')
        self.clock = clock
        self.answer_seconds = answer_seconds
        self.delivery_deadline = clock() + delivery_seconds
        self.answer_deadline = None
        self.result = None

    def identity(self):
        """OpenAI: 返回请求、会话和修订三元组，绑定每一次显示确认与回答。"""
        return {key: self.question[key] for key in ('request_id', 'session_id', 'revision')}

    def finish(self, outcome, **fields):
        """OpenAI: 只保存第一个终态；收集答案永不直接授予操作权限。"""
        if self.result is None:
            self.result = {**self.identity(), 'outcome': outcome, 'user_approved': False, **fields}
        return self.result

    def check(self):
        """OpenAI: 根据当前送达阶段处理超时，已有终态不被后续时钟改写。"""
        if self.result is None:
            if self.answer_deadline is not None and self.clock() >= self.answer_deadline:
                self.finish('timed_out', reason='No answer after display acknowledgement')
            elif self.answer_deadline is None and self.clock() >= self.delivery_deadline:
                self.finish('undelivered', reason='No display acknowledgement; presence unknown')
        return self.result

    def validate_identity(self, payload):
        """OpenAI: 拒绝串会话、旧修订和已结束问题的请求，不接纳迟到答案。"""
        if not isinstance(payload, dict) or any(payload.get(k) != v for k, v in self.identity().items()):
            raise ValueError('Question/session/revision mismatch')
        if self.check() is not None:
            raise ValueError('Question expired or already resolved')

    def ready(self, payload):
        """OpenAI: 首次真实展示确认才开始回答计时，重复确认不延长窗口。"""
        self.validate_identity(payload)
        if self.answer_deadline is None:
            self.answer_deadline = self.clock() + self.answer_seconds
        return {'status': 'display_acknowledged', **self.identity()}

    def answer(self, payload):
        """OpenAI: 检查已展示状态、动作和答案内容，再形成不可覆盖的回答终态。"""
        self.validate_identity(payload)
        if self.answer_deadline is None:
            raise ValueError('Question not yet displayed')
        action = payload.get('action')
        if action not in ('submitted', 'cancelled', 'deferred'):
            raise ValueError('Invalid answer action')
        choice = payload.get('choice_id')
        text = payload.get('text', '')
        if not isinstance(text, str) or len(text) > 8000 or '\x00' in text:
            raise ValueError('Invalid answer text')
        if choice is not None and choice not in [item['id'] for item in self.question.get('options', [])]:
            raise ValueError('Unknown answer option')
        if action == 'submitted' and choice is None and not text.strip():
            raise ValueError('Choose an option or enter an answer')
        if action != 'submitted' and (choice is not None or text):
            raise ValueError('Cancellation must not carry a submitted answer')
        return self.finish(action, choice_id=choice, text=text)


class QuestionServer(ThreadingHTTPServer):
    """OpenAI: Ephemeral loopback-only UI; no file browsing or option execution."""
    daemon_threads = True
    block_on_close = False

    def __init__(self, session):
        """OpenAI: 仅绑定数字loopback，生成一次性能力令牌并限制并发请求数。"""
        self.session = session
        self.token = secrets.token_urlsafe(32)
        self.guard = threading.Lock()
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(('127.0.0.1', 0), QuestionHandler)
        self.origin = f'http://127.0.0.1:{self.server_port}'
        self.host_header = f'127.0.0.1:{self.server_port}'
        self.timeout = 0.2

    def server_bind(self):
        """OpenAI: 绑定本机数字地址而不做反向DNS，避免阻塞吞掉交互时限。"""
        # OpenAI: Numeric loopback needs no reverse DNS, which can exhaust the delivery deadline.
        TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]

    def get_request(self):
        """OpenAI: 接收连接并限制每个socket的读写等待，避免慢请求无限占用线程。"""
        sock, address = super().get_request()
        sock.settimeout(2)
        return sock, address

    def process_request(self, request, client_address):
        """OpenAI: 有界接纳HTTP工作线程；满额立即关连接，启动失败归还槽位。"""
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        """OpenAI: 无论请求成功或异常都归还并发槽位，socket清理由父实现负责。"""
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class QuestionHandler(BaseHTTPRequestHandler):
    """OpenAI: Require exact origin, secret header and question identity for every mutation."""

    @property
    def host(self):
        """OpenAI: 提供带具体类型的所属服务器引用，不创建第二个交互实例。"""
        return cast(QuestionServer, self.server)

    def log_message(self, format, *args):
        """OpenAI: 禁用默认访问日志，避免URL及交互内容进入终端日志。"""
        pass

    def reply(self, status, value, content_type='application/json; charset=utf-8'):
        """OpenAI: 发送准确长度的UTF-8响应及隔离头；写失败交给请求生命周期处理。"""
        raw = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(raw)

    def authorized(self, *, secret=True, origin=False):
        """OpenAI: 按端点核精确Host、Origin和随机令牌，不把同机恶意程序当安全边界。"""
        # OpenAI: A same-machine adversary is outside this capability-token boundary.
        if self.headers.get('Host') != self.host.host_header:
            return False
        if origin and self.headers.get('Origin') != self.host.origin:
            return False
        return not secret or secrets.compare_digest(self.headers.get('X-LD-Token', ''), self.host.token)

    def do_GET(self):
        """OpenAI: 仅提供固定静态资源与当前问题，不开放任意文件或执行接口。"""
        if not self.authorized(secret=self.path not in ('/', '/app.js')):
            self.reply(403, {'error': 'Invalid local request'})
            return
        if self.path in ('/', '/app.js'):
            name = 'question.html' if self.path == '/' else 'question.js'
            body = (Path(__file__).resolve().parents[1]/'assets'/name).read_bytes()
            kind = 'text/html; charset=utf-8' if self.path == '/' else 'text/javascript; charset=utf-8'
            self.reply(200, body, kind)
        elif self.path == '/question':
            with self.host.guard:
                result = self.host.session.check()
                body = self.host.session.question if result is None else {'error': 'Question expired or resolved'}
            self.reply(200 if result is None else 409, body)
        else:
            self.reply(404, {'error': 'Not found'})

    def do_POST(self):
        """OpenAI: 接收有界JSON确认/回答；完整回包后才向主循环暴露回答终态。"""
        if not self.authorized(origin=True):
            self.reply(403, {'error': 'Invalid local request'})
            return
        if self.path not in ('/ready', '/answer'):
            self.reply(404, {'error': 'Not found'})
            return
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            self.reply(415, {'error': 'Expected JSON'})
            return
        if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
            self.reply(400, {'error': 'Expected one bounded content length'})
            return
        try:
            size = int(self.headers.get('Content-Length', ''))
            if not 0 < size <= 65536:
                raise ValueError('Payload too large or empty')
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError('Incomplete body')
            payload = json.loads(raw)
        except (ValueError, UnicodeError, OSError):
            self.reply(400, {'error': 'Invalid or incomplete JSON body'})
            return
        try:
            with self.host.guard:
                method = self.host.session.ready if self.path == '/ready' else self.host.session.answer
                result = method(payload)
                # OpenAI: daemon工作线程可能随CLI退出被截断；主循环须等响应体写完再看到终态。
                self.reply(200, result)
                self.wfile.flush()
        except ValueError as exc:
            self.reply(409, {'error': str(exc)})


ASSESSMENT_FLAGS = ('authorized', 'reversible', 'direction_clear', 'low_risk',
                    'needs_new_approval', 'depends_on_pending')


def assess_nonresponse(outcome, *, authorized=None, reversible=None, direction_clear=None,
                       low_risk=None, needs_new_approval=None, depends_on_pending=None):
    """OpenAI: 将回答或缺席结果映射为有限下一步，不以沉默、路由失败或取消生成批准。"""
    # OpenAI: Route/answer/abort outcomes never masquerade as an unresponsive human.
    flags = (authorized, reversible, direction_clear, low_risk, needs_new_approval, depends_on_pending)
    if not all(value is None for value in flags) and any(type(value) is not bool for value in flags):
        raise ValueError('Decision assessments must be complete explicit booleans')
    if outcome in ('channel_required', 'native_required', 'local_ui_not_allowed'):
        decision = 'routed_not_assessed'
    elif outcome in ('cancelled', 'declined', 'deferred'):
        decision = 'respect_explicit_response'
    elif outcome == 'submitted':
        decision = 'review_explicit_answer'
    elif outcome == 'aborted':
        decision = 'reconcile_caller_abort'
    elif outcome in ('error', 'question_locked'):
        decision = 'reconcile_tool_state'
    elif outcome in ('timed_out', 'undelivered', 'unattended', 'disabled'):
        if all(value is None for value in flags):
            decision = 'assessment_required'
        else:
            safe = authorized and reversible and direction_clear and low_risk
            decision = ('safe_self_decision' if safe and not needs_new_approval and not depends_on_pending
                        else 'defer_item_continue_independent')
    else:
        raise ValueError('Unknown interaction outcome')
    return {'decision': decision, 'user_approved': False,
            'required_record': ['item', 'decision', 'basis', 'rollback_method'],
            'remaining': 'continue_only_independent_authorized_work; summarize_pending_at_closeout'}


def read_assessment(path, identity):
    """OpenAI: 读取有界、与当前问题绑定的调用者安全评估；该材料不是批准令牌。"""
    # OpenAI: An optional, question-bound caller evaluation is evidence to review, not an approval token.
    if path is None:
        return None
    with path.open('rb') as stream:
        raw = stream.read(16385)
    if len(raw) > 16384:
        raise ValueError('Assessment exceeds 16 KiB')
    value = json.loads(raw)
    if not isinstance(value, dict) or any(value.get(k) != v for k, v in identity.items()):
        raise ValueError('Assessment question/session/revision mismatch')
    if any(type(value.get(k)) is not bool for k in ASSESSMENT_FLAGS):
        raise ValueError('Assessment requires all safety flags')
    for key in ('basis', 'rollback_method'):
        if not isinstance(value.get(key), str) or not value[key].strip() or len(value[key]) > 2000:
            raise ValueError('Assessment requires a concise basis and rollback method')
    return {**identity, **{k: value[k] for k in ASSESSMENT_FLAGS},
            'basis': value['basis'], 'rollback_method': value['rollback_method']}


def result_with_assessment(result, metadata, assessment=None):
    """OpenAI: 合并结果、实际配置来源与评估决定，保留尚需记录和处理的边界。"""
    flags = {} if assessment is None else {key: assessment[key] for key in ASSESSMENT_FLAGS}
    return {**result, **metadata, **assess_nonresponse(result['outcome'], **flags),
            'assessment': assessment}


def main():
    """OpenAI: 运行单次宿主路由或本机询问，用ASCII JSON报告结果并释放锁和监听端口。"""
    import hashlib
    import subprocess
    import sys
    from maintain import config_at, data_dir, interaction_config, locked

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--data-root', type=Path)
    parser.add_argument('--question', type=Path, required=True)
    parser.add_argument('--assessment', type=Path, help='Optional question-bound safety assessment; never grants permission')
    parser.add_argument('--actor', choices=('tool-agent', 'bot'), required=True)
    parser.add_argument('--unattended', action='store_true')
    parser.add_argument('--native-available', action='store_true')
    parser.add_argument('--local-ui-allowed', action='store_true',
                        help='Caller verified the current authorized user terminal supports this local UI')
    parser.add_argument('--open-browser', action='store_true', help='Open only this terminal browser; no remote route')
    parser.add_argument('--answer-wait-minutes', type=int, help='Explicit user override for this question only')
    parser.add_argument('--delivery-seconds', type=int, default=60)
    args = parser.parse_args()
    session = None
    metadata = {}
    assessment = None
    try:
        with args.question.open('rb') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('Question file exceeds 64 KiB')
        question = validate_question(json.loads(raw))
        directory = data_dir(args.skill_root.resolve(), args.data_root)
        config = config_at(directory)
        settings = interaction_config(config)
        wait_source = 'config' if 'answer_wait_minutes' in config.get('interaction', {}) else 'default'
        if args.answer_wait_minutes is not None:
            settings['answer_wait_minutes'] = args.answer_wait_minutes
            settings = interaction_config({'interaction': settings})
            wait_source = 'override'
        if not 1 <= args.delivery_seconds <= 300:
            raise ValueError('delivery-seconds must be 1..300')
        session = QuestionSession(question, settings['answer_wait_minutes'] * 60, args.delivery_seconds)
        assessment = read_assessment(args.assessment, session.identity())
        metadata = {'config_path': str(directory/'config.json'), 'interaction': settings,
                    'answer_wait_source': wait_source,
                    'idle_detection': 'unsupported_not_observed', 'actor': args.actor}
        outcome = ('unattended' if args.unattended else 'disabled' if not settings['enabled'] else
                   'channel_required' if args.actor == 'bot' else 'native_required' if args.native_available else
                   'local_ui_not_allowed' if not args.local_ui_allowed else None)
        # OpenAI: ASCII JSON preserves Unicode values across locale-dependent subprocess pipes.
        if outcome:
            print(json.dumps(result_with_assessment(session.finish(outcome), metadata, assessment), ensure_ascii=True))
            return 0
        key = hashlib.sha256((question['session_id'] + '\n' + question['request_id']).encode()).hexdigest()
        # OpenAI: Lock only this question, not all maintenance or unrelated concurrent work.
        with locked(directory/'interactions'/key):
            with QuestionServer(session) as server:
                url = server.origin + '/#token=' + server.token
                print(json.dumps({'event': 'local_question_ready', 'url': url,
                                  **session.identity(), **metadata}, ensure_ascii=True), flush=True)
                if args.open_browser:
                    try:
                        subprocess.run([sys.executable, '-m', 'webbrowser', '-t', url],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=True)
                    except (OSError, subprocess.SubprocessError):
                        session.finish('undelivered', reason='Could not launch this terminal browser')
                try:
                    while True:
                        with server.guard:
                            result = session.check()
                        if result is not None:
                            break
                        server.handle_request()
                except KeyboardInterrupt:
                    with server.guard:
                        result = session.finish('aborted', reason='Caller interrupted; not a user answer')
                print(json.dumps(result_with_assessment(result, metadata, assessment), ensure_ascii=True), flush=True)
        return 0
    except KeyboardInterrupt:
        result = session.finish('aborted', reason='Caller interrupted; reconcile original state') if session else {'outcome': 'aborted'}
        print(json.dumps(result_with_assessment(result, metadata, assessment), ensure_ascii=True), flush=True)
        return 0
    except FileExistsError as exc:
        result = {'outcome': 'question_locked', 'error': str(exc),
                  'reason': 'Existing question lock; inspect owner and prior result, never auto-steal'}
        if session is not None:
            result.update(session.identity())
        print(json.dumps(result_with_assessment(result, metadata), ensure_ascii=True))
        return 1
    except (OSError, ValueError, TypeError) as exc:
        result = {'outcome': 'error', 'error': str(exc)}
        if session is not None:
            result.update(session.identity())
        print(json.dumps(result_with_assessment(result, metadata), ensure_ascii=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
