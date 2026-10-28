# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 请求内部发现超时时，真实HTTP错误响应也必须完整送出。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ld-codestyle-online/scripts'


class TerminalResponseTests(unittest.TestCase):
    """OpenAI: GET检查和POST身份检查均能生成终态，分别覆盖其错误回包。"""

    def test_expiry_discovered_by_request_returns_complete_error(self):
        """OpenAI: 仅测试线程使送达期限过期并延迟回包，核409正文与CLI终态完整一致。"""
        for endpoint in ('/question', '/ready'):
            with self.subTest(endpoint=endpoint), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                question = dict(request_id='expiry', session_id='fixture', revision='1',
                                title='合成询问', question='合成超时边界', options=[])
                path = root / 'question.json'
                path.write_text(json.dumps(question), encoding='utf-8')
                wrapper = root / 'expiry.py'
                wrapper.write_text(
                    'import sys,time,threading\n'
                    f'sys.path.insert(0,{str(SCRIPTS)!r})\n'
                    'import interact\n'
                    'original=interact.QuestionSession.check\n'
                    'def expire_in_worker(self):\n'
                    '    """Make the delivery deadline expire only while a request is being handled."""\n'
                    '    if threading.current_thread() is not threading.main_thread():\n'
                    '        self.delivery_deadline=0\n'
                    '    return original(self)\n'
                    'interact.QuestionSession.check=expire_in_worker\n'
                    'headers=interact.QuestionHandler.end_headers\n'
                    'def delay_body(self):\n'
                    '    """Delay the body after sending real HTTP response headers."""\n'
                    '    headers(self)\n'
                    '    time.sleep(0.6)\n'
                    'interact.QuestionHandler.end_headers=delay_body\n'
                    'raise SystemExit(interact.main())\n', encoding='utf-8')
                proc = subprocess.Popen([sys.executable, '-B', str(wrapper), '--question', str(path),
                    '--data-root', str(root / 'data'), '--actor', 'tool-agent', '--local-ui-allowed'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
                try:
                    assert proc.stdout is not None
                    event = json.loads(proc.stdout.readline())
                    url = urlsplit(event['url'])
                    origin = f'{url.scheme}://{url.netloc}'
                    headers = {'X-LD-Token': parse_qs(url.fragment)['token'][0],
                               'Origin': origin, 'Content-Type': 'application/json'}
                    payload = None if endpoint == '/question' else json.dumps(
                        {key: question[key] for key in ('request_id', 'session_id', 'revision')}).encode()
                    request = urllib.request.Request(origin + endpoint, data=payload, headers=headers)
                    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        opener.open(request, timeout=4)
                    with caught.exception as response:
                        self.assertEqual(response.code, 409)
                        self.assertIn('expired', json.load(response)['error'].lower())
                    output, error = proc.communicate(timeout=5)
                    self.assertEqual(proc.returncode, 0, error)
                    self.assertEqual(json.loads(output)['outcome'], 'undelivered')
                finally:
                    if proc.poll() is None:
                        proc.terminate()
                    proc.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
