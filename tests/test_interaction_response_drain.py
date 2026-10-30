# SPDX-License-Identifier: AGPL-3.0-only
"""OpenAI: 用真实CLI延迟响应体，确定性检验回答确认不会被进程提前退出截断。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.request
from urllib.parse import parse_qs, urlsplit

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/ld-codestyle-online/scripts'


class ResponseDrainTests(unittest.TestCase):
    """OpenAI: 仅在测试子进程延迟回包，不改生产超时或隐藏网络错误。"""

    def test_cli_finishes_only_after_answer_response_body_is_sent(self):
        """OpenAI: 状态已提交而响应体尚未发送时，主循环不能退出杀死HTTP工作线程。"""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            question = dict(request_id='drain', session_id='fixture', revision='1',
                            title='合成询问', question='仅测试回应完成', options=[])
            path = root / 'question.json'
            path.write_text(json.dumps(question), encoding='utf-8')
            wrapper = root / 'delayed_response.py'
            wrapper.write_text(
                'import sys,time\n'
                f'sys.path.insert(0, {str(SCRIPTS)!r})\n'
                'import interact\n'
                'original=interact.QuestionHandler.end_headers\n'
                'def delayed_headers(self):\n'
                '    """Delay only the answer body after real HTTP headers have been sent."""\n'
                '    original(self)\n'
                '    if self.path == "/answer": time.sleep(0.6)\n'
                'interact.QuestionHandler.end_headers=delayed_headers\n'
                'raise SystemExit(interact.main())\n', encoding='utf-8')
            command = [sys.executable, '-B', str(wrapper), '--question', str(path),
                       '--data-root', str(root / 'data'), '--actor', 'tool-agent', '--local-ui-allowed']
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding='utf-8')
            try:
                assert proc.stdout is not None
                ready = json.loads(proc.stdout.readline())
                url = urlsplit(ready['url'])
                origin = f'{url.scheme}://{url.netloc}'
                token = parse_qs(url.fragment)['token'][0]
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
                ids = {key: question[key] for key in ('request_id', 'session_id', 'revision')}
                for endpoint, payload in (('/ready', ids), ('/answer', {**ids, 'action': 'submitted', 'text': '合成回答'})):
                    request = urllib.request.Request(origin + endpoint, data=json.dumps(payload).encode(),
                        headers={'Content-Type': 'application/json', 'Origin': origin, 'X-LD-Token': token})
                    with opener.open(request, timeout=4) as response:
                        answer = json.load(response)
                self.assertEqual(answer['outcome'], 'submitted')
                output, error = proc.communicate(timeout=5)
                self.assertEqual(proc.returncode, 0, error)
                self.assertEqual(json.loads(output)['text'], '合成回答')
            finally:
                if proc.poll() is None:
                    proc.terminate()
                proc.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
