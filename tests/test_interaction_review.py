# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Regressions for independent review findings; exercise the public CLI.
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from test_interaction import load, question, SCRIPTS


class ReviewRegressionTests(unittest.TestCase):
    def test_all_transport_outcomes_have_explicit_non_authorizing_decisions(self):
        m = load()
        safe = dict(authorized=True, reversible=True, direction_clear=True, low_risk=True,
                    needs_new_approval=False, depends_on_pending=False)
        expected = {'channel_required':'routed_not_assessed', 'native_required':'routed_not_assessed',
                    'local_ui_not_allowed':'routed_not_assessed', 'submitted':'review_explicit_answer',
                    'cancelled':'respect_explicit_response', 'deferred':'respect_explicit_response',
                    'aborted':'reconcile_caller_abort', 'error':'reconcile_tool_state',
                    'question_locked':'reconcile_tool_state'}
        for outcome, decision in expected.items():
            with self.subTest(outcome=outcome):
                result = m.assess_nonresponse(outcome, **safe)
                self.assertEqual(result['decision'], decision)
                self.assertFalse(result['user_approved'])

    @unittest.skipUnless(sys.platform != 'win32', 'POSIX SIGINT subprocess test')
    def test_caller_interrupt_is_not_a_human_cancellation(self):
        import signal
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);q=root/'q.json';q.write_text(json.dumps(question()),encoding='utf-8')
            args=[sys.executable,'-B',str(SCRIPTS/'interact.py'),'--data-root',str(root/'data'),
                  '--question',str(q),'--actor','tool-agent','--local-ui-allowed']
            p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding='utf-8')
            try:
                assert p.stdout is not None
                event=json.loads(p.stdout.readline())
                self.assertEqual(event['event'],'local_question_ready')
                p.send_signal(signal.SIGINT)
                out,err=p.communicate(timeout=5)
                self.assertEqual(p.returncode,0,err)
                result=json.loads(out)
                self.assertEqual(result['outcome'],'aborted')
                self.assertEqual(result['decision'],'reconcile_caller_abort')
                self.assertFalse(result['user_approved'])
                self.assertEqual(list((root/'data').rglob('maintenance.lock')),[])
            finally:
                if p.poll() is None:p.terminate()
                p.communicate(timeout=5)

    def test_interrupt_during_final_output_preserves_existing_assessment(self):
        from unittest.mock import patch
        m=load()
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);q=root/'q.json';q.write_text(json.dumps(question()),encoding='utf-8')
            identity={k:question()[k] for k in ('request_id','session_id','revision')}
            evidence={**identity,'authorized':True,'reversible':True,'direction_clear':True,
                      'low_risk':True,'needs_new_approval':False,'depends_on_pending':False,
                      'basis':'授权内测试','rollback_method':'恢复临时夹具'}
            a=root/'a.json';a.write_text(json.dumps(evidence),encoding='utf-8')
            argv=['interact.py','--data-root',str(root/'data'),'--question',str(q),
                  '--actor','tool-agent','--unattended','--assessment',str(a)]
            with patch.object(sys,'argv',argv), patch('builtins.print',side_effect=[KeyboardInterrupt(),None]) as printer:
                self.assertEqual(m.main(),0)
            first=json.loads(printer.call_args_list[0].args[0])
            second=json.loads(printer.call_args_list[1].args[0])
            self.assertEqual(second,first)
            self.assertEqual(second['decision'],'safe_self_decision')
            self.assertFalse(second['user_approved'])

    def test_cli_assessment_is_bound_to_question_and_keeps_own_authority(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            q = root/'q.json'; q.write_text(json.dumps(question()), encoding='utf-8')
            assessment = root/'assessment.json'
            identity = {k:question()[k] for k in ('request_id','session_id','revision')}
            evidence = {**identity, 'authorized':True, 'reversible':True, 'direction_clear':True,
                        'low_risk':True, 'needs_new_approval':False, 'depends_on_pending':False,
                        'basis':'已授权的测试夹具选择，不改生产内容', 'rollback_method':'恢复本次临时夹具'}
            assessment.write_text(json.dumps(evidence), encoding='utf-8')
            base = [sys.executable,'-B',str(SCRIPTS/'interact.py'),'--data-root',str(root/'data'),
                    '--question',str(q),'--actor','tool-agent','--unattended']
            def invoke(extra):
                return subprocess.run(base+extra,capture_output=True,text=True,encoding='utf-8',timeout=5)
            no_evidence = invoke([])
            self.assertEqual(no_evidence.returncode,0,no_evidence.stderr)
            self.assertEqual(json.loads(no_evidence.stdout).get('decision'),'assessment_required')
            result = invoke(['--assessment',str(assessment),'--answer-wait-minutes','3'])
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data['decision'],'safe_self_decision')
            self.assertFalse(data['user_approved'])
            self.assertEqual(data['answer_wait_source'],'override')
            self.assertEqual(data['assessment']['basis'],evidence['basis'])
            self.assertIn('rollback_method',data['required_record'])
            self.assertFalse(Path(data['config_path']).exists())
            for changed, decision in (({'reversible':False},'defer_item_continue_independent'),
                                      ({'needs_new_approval':True},'defer_item_continue_independent')):
                assessment.write_text(json.dumps({**evidence,**changed}),encoding='utf-8')
                p = invoke(['--assessment',str(assessment)])
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                self.assertEqual(json.loads(p.stdout)['decision'],decision)
            for changed in ({'session_id':'wrong'},{'basis':''},{'reversible':'yes'}):
                assessment.write_text(json.dumps({**evidence,**changed}),encoding='utf-8')
                p = invoke(['--assessment',str(assessment)])
                self.assertNotEqual(p.returncode,0)
                self.assertEqual(json.loads(p.stdout)['decision'],'reconcile_tool_state')


if __name__ == '__main__':
    unittest.main()
