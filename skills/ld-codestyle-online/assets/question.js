// SPDX-License-Identifier: AGPL-3.0-only
// OpenAI: Keep secrets in the fragment/header, and bind every answer to its exact question.
'use strict';
const token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
history.replaceState(null, '', location.pathname);
const element = id => document.getElementById(id);
let question;
let sending = false;
let ready = false;
const identity = () => ({request_id: question.request_id, session_id: question.session_id, revision: question.revision});
function controls(disabled) {
  for (const id of ['submit', 'later', 'cancel']) element(id).disabled = disabled;
}
async function request(path, payload) {
  const options = {headers: {'X-LD-Token': token}, cache: 'no-store'};
  if (payload !== undefined) {
    options.method = 'POST';
    options.headers['Content-Type'] = 'application/json';
    options.body = JSON.stringify(payload);
  }
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '请求已失效，请回到原任务查看状态。');
  return data;
}
async function acknowledgeDisplay() {
  if (ready || !question || document.visibilityState !== 'visible') return;
  await request('/ready', identity());
  ready = true;
  controls(false);
  element('status').textContent = '问题已显示，等待你的回答。';
}
async function submit(action) {
  if (sending || !ready) return;
  const selected = document.querySelector('input[name="choice"]:checked');
  const choice = selected && selected.value !== '__custom__' ? selected.value : null;
  const text = element('custom').value.trim();
  if (action === 'submitted' && !choice && !text) {
    element('status').textContent = '请选择一个方案或填写自定义回答。';
    return;
  }
  sending = true;
  controls(true);
  try {
    await request('/answer', {...identity(), action,
      choice_id: action === 'submitted' ? choice : null,
      text: action === 'submitted' ? text : ''});
    element('status').textContent = '已回传当前任务，可以关闭页面。';
  } catch (error) {
    element('status').textContent = String(error.message) + ' 请回到原任务确认结果，不重复点击。';
  }
}
element('form').addEventListener('submit', event => {event.preventDefault(); void submit('submitted');});
element('later').addEventListener('click', () => void submit('deferred'));
element('cancel').addEventListener('click', () => void submit('cancelled'));
document.addEventListener('visibilitychange', () => {
  void acknowledgeDisplay().catch(error => {element('status').textContent = error.message;});
});
(async () => {
  try {
    question = await request('/question');
    element('title').textContent = question.title;
    element('question').textContent = question.question;
    element('identity').textContent = `${question.session_id} / ${question.request_id} / ${question.revision}`;
    for (const option of [...(question.options || []), {id: '__custom__', label: '自定义回答', detail: '在下方输入'}]) {
      const row = document.createElement('p');
      const label = document.createElement('label');
      const input = document.createElement('input');
      input.type = 'radio'; input.name = 'choice'; input.value = option.id;
      label.appendChild(input);
      label.appendChild(document.createTextNode(` ${option.label}${option.id === question.recommended_id ? '（推荐）' : ''} — ${option.detail || ''}`));
      row.appendChild(label); element('options').appendChild(row);
    }
    await acknowledgeDisplay();
  } catch (error) {element('status').textContent = error.message;}
})();
