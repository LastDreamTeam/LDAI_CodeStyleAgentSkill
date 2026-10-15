# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Test interaction preferences through the real CLI without touching installed skills.
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'skills/ld-codestyle-online/scripts/maintain.py'


class InteractionConfigTests(unittest.TestCase):
    def invoke(self, install, data, *args):
        return subprocess.run([sys.executable, '-B', str(SCRIPT), '--skill-root', str(install),
                               '--data-root', str(data), *args], capture_output=True,
                              text=True, encoding='utf-8', timeout=10)

    def test_defaults_and_separate_clocks_are_path_scoped_and_persistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); a=root/'a'; b=root/'b'; a.mkdir(); b.mkdir(); data=root/'data'
            result=self.invoke(a,data,'show'); self.assertEqual(result.returncode,0,result.stderr)
            first=json.loads(result.stdout)
            self.assertEqual(first.get('interaction'),
                             {'enabled':True,'answer_wait_minutes':15,'idle_after_minutes':0})
            self.assertEqual(first['config_path'],str(Path(first['data_dir'])/'config.json'))
            changed=self.invoke(a,data,'config','--interaction','off',
                                '--answer-wait-minutes','7','--idle-after-minutes','22')
            self.assertEqual(changed.returncode,0,changed.stdout+changed.stderr)
            value=json.loads(changed.stdout)
            self.assertEqual(value['interaction'],
                             {'enabled':False,'answer_wait_minutes':7,'idle_after_minutes':22})
            self.assertEqual(json.loads(self.invoke(a,data,'show').stdout)['interaction'],value['interaction'])
            other=json.loads(self.invoke(b,data,'show').stdout)
            self.assertNotEqual(other['data_dir'],value['data_dir'])
            self.assertEqual(other['interaction'],first['interaction'])
            raw=Path(value['config_path']).read_bytes()
            for args in (('--answer-wait-minutes','0'),('--answer-wait-minutes','1441'),
                         ('--idle-after-minutes','-1'),('--idle-after-minutes','1441')):
                bad=self.invoke(a,data,'config',*args)
                self.assertNotEqual(bad.returncode,0)
                self.assertEqual(Path(value['config_path']).read_bytes(),raw)
            config=json.loads(raw);config['interaction']['enabled']='yes'
            invalid=json.dumps(config);Path(value['config_path']).write_text(invalid,encoding='utf-8')
            bad=self.invoke(a,data,'show');self.assertNotEqual(bad.returncode,0)
            self.assertEqual(Path(value['config_path']).read_text(encoding='utf-8'),invalid)


if __name__=='__main__':
    unittest.main()
