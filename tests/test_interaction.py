# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Exercise decision boundaries and the actual local question transport.
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'skills/ld-codestyle-online/scripts'


def load():
    path=SCRIPTS/'interact.py'
    if not path.is_file():
        raise AssertionError('Missing local interaction helper')
    sys.path.insert(0,str(SCRIPTS))
    spec=importlib.util.spec_from_file_location('interaction_under_test',path)
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def question():
    return {'request_id':'q-1','session_id':'session-a','revision':'r1',
            'title':'测试模块','question':'选择处理方式？',
            'options':[{'id':'a','label':'方式A','detail':'可回退'},
                       {'id':'b','label':'方式B','detail':'保持原样'}], 'recommended_id':'a'}


class ContinuationTests(unittest.TestCase):
    def test_nonresponse_is_assessed_not_approval_or_whole_task_stop(self):
        m=load()
        safe=dict(authorized=True, reversible=True, direction_clear=True,
                  low_risk=True, needs_new_approval=False, depends_on_pending=False)
        for outcome in ('timed_out','undelivered','unattended','disabled'):
            result=m.assess_nonresponse(outcome,**safe)
            self.assertEqual(result['decision'],'safe_self_decision')
            self.assertFalse(result['user_approved'])
        for key,value in (('authorized',False),('reversible',False),('direction_clear',False),
                          ('low_risk',False),('needs_new_approval',True),('depends_on_pending',True)):
            result=m.assess_nonresponse('timed_out',**{**safe,key:value})
            self.assertEqual(result['decision'],'defer_item_continue_independent')
        for outcome in ('cancelled','declined','deferred'):
            self.assertEqual(m.assess_nonresponse(outcome,**safe)['decision'],'respect_explicit_response')
        with self.assertRaises(ValueError):
            m.assess_nonresponse('timed_out',**{**safe,'reversible':'yes'})


class QuestionStateTests(unittest.TestCase):
    def test_state_requires_display_and_exact_identity_and_expires_late_answers(self):
        m=load()
        self.assertTrue(hasattr(m,'QuestionSession'),'Missing question state machine')
        now=[10.0]
        s=m.QuestionSession(question(),answer_seconds=60,delivery_seconds=5,clock=lambda:now[0])
        ids={k:question()[k] for k in ('request_id','session_id','revision')}
        with self.assertRaises(ValueError):
            s.answer({**ids,'action':'submitted','choice_id':'a','text':''})
        with self.assertRaises(ValueError):
            s.ready({**ids,'session_id':'other'})
        now[0]=14
        s.ready(ids)
        now[0]=19
        self.assertIsNone(s.check())
        s.ready(ids)
        now[0]=74
        self.assertEqual(s.check()['outcome'],'timed_out')
        with self.assertRaises(ValueError):
            s.answer({**ids,'action':'submitted','choice_id':'a','text':''})
        other=m.QuestionSession(question(),answer_seconds=60,delivery_seconds=5,clock=lambda:now[0])
        now[0]=79
        self.assertEqual(other.check()['outcome'],'undelivered')

    def test_custom_answers_cancel_and_bad_input_remain_distinct(self):
        m=load()
        self.assertTrue(hasattr(m,'QuestionSession'),'Missing question state machine')
        ids={k:question()[k] for k in ('request_id','session_id','revision')}
        for action in ('submitted','cancelled','deferred'):
            s=m.QuestionSession(question(),60,5)
            s.ready(ids)
            response=s.answer({**ids,'action':action,'choice_id':None,'text':'自定义方案' if action=='submitted' else ''})
            self.assertEqual(response['outcome'],action)
            self.assertFalse(response['user_approved'])
            self.assertEqual(response['session_id'],'session-a')
            with self.assertRaises(ValueError):
                s.answer({**ids,'action':action,'choice_id':None,'text':''})
        s=m.QuestionSession(question(),60,5);s.ready(ids)
        for values in ({'choice_id':'not-listed','text':''},{'choice_id':None,'text':''},
                       {'choice_id':None,'text':'x'*8001}):
            with self.assertRaises(ValueError):
                s.answer({**ids,'action':'submitted',**values})
        for overrides in ({'request_id':'bad\nID'}, {'options':[{'id':'a','label':'x'},{'id':'a','label':'y'}]},
                          {'options':[{'id':7,'label':'integer-id'}], 'recommended_id':None},
                          {'recommended_id':'missing'}, {'question':'x'*8001}):
            with self.assertRaises(ValueError):m.QuestionSession({**question(),**overrides},60,5)


class LocalTransportTests(unittest.TestCase):
    def test_loopback_server_binding_never_resolves_hostnames(self):
        from unittest.mock import patch
        m=load()
        session=m.QuestionSession(question(),60,5)
        with patch('socket.getfqdn',side_effect=AssertionError('Loopback UI must not depend on DNS')):
            with m.QuestionServer(session) as server:
                self.assertEqual(server.server_name,'127.0.0.1')
                self.assertGreater(server.server_port,0)
                self.assertEqual(server.server_address,('127.0.0.1',server.server_port))

    def test_real_http_roundtrip_rejects_wrong_origin_token_and_session(self):
        import json
        import threading
        import urllib.request
        import urllib.error
        m=load()
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.assertTrue(hasattr(m,'QuestionServer'),'Missing loopback transport')
        s=m.QuestionSession(question(),60,5)
        server=m.QuestionServer(s)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            def get(path, token=server.token):
                req=urllib.request.Request(server.origin+path,headers={'X-LD-Token':token})
                return opener.open(req,timeout=3)
            def post(path,payload,origin=None,token=None):
                headers={'Content-Type':'application/json','Origin':origin or server.origin,
                         'X-LD-Token':server.token if token is None else token}
                req=urllib.request.Request(server.origin+path,data=json.dumps(payload).encode(),headers=headers)
                return opener.open(req,timeout=3)
            with get('/') as response:
                page=response.read().decode()
                self.assertIn('自定义',page)
                self.assertIn('取消',page)
                self.assertIn('稍后',page)
                self.assertIn('Content-Security-Policy',response.headers)
                self.assertNotIn(server.token,page)
            with self.assertRaises(urllib.error.HTTPError) as error:get('/question','bad')
            self.assertEqual(error.exception.code,403)
            with get('/question') as response:self.assertEqual(json.load(response)['request_id'],'q-1')
            ids=s.identity()
            with self.assertRaises(urllib.error.HTTPError) as error:post('/ready',ids,'https://unrelated.invalid')
            self.assertEqual(error.exception.code,403)
            with post('/ready',ids) as response:self.assertEqual(json.load(response)['status'],'display_acknowledged')
            with self.assertRaises(urllib.error.HTTPError) as error:
                post('/answer',{**ids,'session_id':'wrong','action':'submitted','choice_id':'a','text':''})
            self.assertEqual(error.exception.code,409)
            with post('/answer',{**ids,'action':'submitted','choice_id':None,'text':'我选自定义'}) as response:
                result=json.load(response)
            self.assertEqual(result['text'],'我选自定义')
            self.assertFalse(result['user_approved'])
            with self.assertRaises(urllib.error.HTTPError):
                post('/answer',{**ids,'action':'submitted','choice_id':'a','text':''})
        finally:
            server.shutdown();server.server_close();thread.join(timeout=3)


    def test_parallel_questions_cannot_exchange_answers(self):
        import json
        import threading
        import urllib.request
        import urllib.error
        m=load()
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        a=m.QuestionSession(question(),60,5)
        b=m.QuestionSession({**question(),'session_id':'session-b','revision':'r2'},60,5)
        servers=[m.QuestionServer(a),m.QuestionServer(b)]
        threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in servers]
        for t in threads:t.start()
        try:
            def post(server,path,payload,token):
                req=urllib.request.Request(server.origin+path,data=json.dumps(payload).encode(),headers={
                    'Origin':server.origin,'X-LD-Token':token,'Content-Type':'application/json'})
                with opener.open(req,timeout=3) as r:return json.load(r)
            post(servers[0],'/ready',a.identity(),servers[0].token)
            post(servers[1],'/ready',b.identity(),servers[1].token)
            payload={**a.identity(),'action':'submitted','choice_id':'a','text':''}
            for token in (servers[0].token,servers[1].token):
                with self.assertRaises(urllib.error.HTTPError):post(servers[1],'/answer',payload,token)
            self.assertIsNone(b.result)
            result=post(servers[1],'/answer',{**b.identity(),'action':'submitted','choice_id':'b','text':''},servers[1].token)
            self.assertEqual(result['session_id'],'session-b')
            self.assertIsNone(a.result)
        finally:
            for s in servers:s.shutdown();s.server_close()
            for t in threads:t.join(timeout=3)


class InteractionCliTests(unittest.TestCase):
    def test_role_and_unattended_gates_never_open_local_server(self):
        import json
        import subprocess
        import tempfile
        m=load()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);q=root/'q.json';q.write_text(json.dumps(question()),encoding='utf-8')
            base=[sys.executable,'-B',str(SCRIPTS/'interact.py'),'--data-root',str(root/'data'),
                  '--question',str(q)]
            for flags,outcome in ((['--actor','bot'],'channel_required'),
                                  (['--actor','tool-agent','--unattended'],'unattended'),
                                  (['--actor','tool-agent','--native-available'],'native_required'),
                                  (['--actor','tool-agent'],'local_ui_not_allowed')):
                p=subprocess.run(base+flags,capture_output=True,text=True,encoding='utf-8',timeout=5)
                self.assertEqual(p.returncode,0,p.stderr)
                self.assertTrue(p.stdout.strip(),'Missing structured CLI result')
                result=json.loads(p.stdout)
                self.assertEqual(result['outcome'],outcome)
                self.assertNotIn('url',result)
                self.assertFalse(result['user_approved'])

    def test_undelivered_cli_exits_and_duplicate_question_does_not_rebind(self):
        import json
        import socket
        import subprocess
        import tempfile
        from urllib.parse import urlsplit
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);q=root/'q.json';q.write_text(json.dumps(question()),encoding='utf-8')
            args=[sys.executable,'-B',str(SCRIPTS/'interact.py'),'--data-root',str(root/'data'),
                  '--actor','tool-agent','--local-ui-allowed','--question',str(q),
                  '--delivery-seconds','2','--answer-wait-minutes','1']
            p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
            try:
                assert p.stdout is not None
                event=json.loads(p.stdout.readline());url=urlsplit(event['url'])
                duplicate=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',timeout=3)
                self.assertNotEqual(duplicate.returncode,0)
                self.assertEqual(json.loads(duplicate.stdout)['outcome'],'question_locked')
                self.assertEqual(json.loads(duplicate.stdout)['decision'],'reconcile_tool_state')
                self.assertNotIn('local_question_ready',duplicate.stdout)
                output,err=p.communicate(timeout=5)
                self.assertEqual(p.returncode,0,err)
                result=json.loads(output);self.assertEqual(result['outcome'],'undelivered')
                self.assertFalse(result['user_approved'])
                self.assertFalse(Path(result['config_path']).exists(),'One-question override must not create persistent preferences')
                self.assertEqual(list((root/'data').rglob('maintenance.lock')),[])
                with socket.socket() as sock:
                    sock.settimeout(1)
                    self.assertNotEqual(sock.connect_ex((url.hostname,url.port)),0)
            finally:
                if p.poll() is None:p.terminate()
                p.communicate(timeout=5)

    def test_real_cli_question_and_unicode_answer_roundtrip_across_output_encodings(self):
        import json
        import os
        import subprocess
        import tempfile
        import urllib.request
        from urllib.parse import urlsplit,parse_qs
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        answer='真实CLI协议测试 \U0001f9ea'
        for encoding in ('cp936','cp1252'):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as td:
                root=Path(td);q=root/'q.json';q.write_text(json.dumps(question()),encoding='utf-8')
                data=root/'中文配置'
                cmd=[sys.executable,'-B',str(SCRIPTS/'interact.py'),'--data-root',str(data),
                     '--actor','tool-agent','--local-ui-allowed','--question',str(q),'--delivery-seconds','3']
                env={**os.environ,'PYTHONIOENCODING':encoding}
                p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
                try:
                    assert p.stdout is not None
                    line=p.stdout.readline()
                    self.assertTrue(line,'Missing listening event')
                    ready=json.loads(line.decode('ascii'))
                    self.assertEqual(ready['event'],'local_question_ready')
                    self.assertTrue(Path(ready['config_path']).resolve().is_relative_to(data.resolve()))
                    url=urlsplit(ready['url']);token=parse_qs(url.fragment)['token'][0]
                    origin=f'{url.scheme}://{url.netloc}'
                    def post(path,payload):
                        req=urllib.request.Request(origin+path,data=json.dumps(payload).encode(),
                             headers={'Content-Type':'application/json','Origin':origin,'X-LD-Token':token})
                        with opener.open(req,timeout=3) as response:return json.load(response)
                    ids={k:question()[k] for k in ('request_id','session_id','revision')}
                    post('/ready',ids)
                    post('/answer',{**ids,'action':'submitted','choice_id':'b','text':answer})
                    out,err=p.communicate(timeout=5);self.assertEqual(p.returncode,0,err)
                    result=json.loads(out.decode('ascii'))
                    self.assertEqual(result['outcome'],'submitted')
                    self.assertEqual(result['choice_id'],'b')
                    self.assertEqual(result['text'],answer)
                    self.assertFalse(result['user_approved'])
                    self.assertEqual(result['idle_detection'],'unsupported_not_observed')
                finally:
                    if p.poll() is None:p.terminate()
                    p.communicate(timeout=5)


if __name__=='__main__':
    unittest.main()
