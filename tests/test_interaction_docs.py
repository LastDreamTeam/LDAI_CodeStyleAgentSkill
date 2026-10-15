# SPDX-License-Identifier: AGPL-3.0-only
# OpenAI: Document contracts supplement execution tests; they do not prove human comprehension.
from pathlib import Path
import re
import unittest
ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/ld-codestyle-online'


class InteractionDocsTests(unittest.TestCase):
    def test_roles_routing_continuation_and_configuration_are_explicit(self):
        spec=(SKILL/'references/interaction.md').read_text(encoding='utf-8')
        for term in ('工具类 Agent','Bot','不是普遍行业定义','VistualStudio',
                     '非远程运行终端','当前实际角色','A2A+Gateway',
                     '不得跨其他电脑','相关聊天渠道','没有回答','安全自行决定',
                     '无法回档和涉及的业务方向多','收尾结果集中询问','回档办法',
                     '不依赖','取消、拒绝、稍后不是沉默','answer_wait_minutes',
                     'idle_after_minutes','config_path','unsupported_not_observed',
                     'request_id','session_id','revision','Windows原生表单不在首版'):
            self.assertIn(term,spec)
        for path in (ROOT/'README.md',SKILL/'SKILL.md',SKILL/'references/contract.md'):
            self.assertIn('interaction.md',path.read_text(encoding='utf-8'))
        self.assertIn('question.example.json',spec)
        page=(SKILL/'assets/question.html').read_text(encoding='utf-8')
        js=(SKILL/'assets/question.js').read_text(encoding='utf-8')
        for term in ('自定义','取消','稍后'):self.assertIn(term,page)
        self.assertNotIn('innerHTML',js)
        self.assertNotIn('input.checked = true',js)
        self.assertIn("visibilityState !== 'visible'",js)
        self.assertIn('textContent',js)
        self.assertNotRegex(page,r'<(?:script|link)[^>]+(?:src|href)=["\']https?://')

if __name__=='__main__':unittest.main()
