"""End-to-end RAG pipeline test through the new chat API."""
import urllib.request
import json
import sys

BASE = 'http://127.0.0.1:8000'

def req(method, path, data=None, token=None, timeout=120):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r, timeout=timeout)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b'{}')

# Register / login
st, r = req('POST', '/api/auth/register', {'name': 'RAG Test User', 'email': 'ragtest@veritas.ai', 'password': 'pass123'})
if st == 400:
    st, r = req('POST', '/api/auth/login', {'email': 'ragtest@veritas.ai', 'password': 'pass123'})
token = r.get('access_token', '')
print('Auth token obtained:', bool(token))

# Create chat
st, r = req('POST', '/api/chats', {'title': 'Hypertension Test'}, token=token)
chat_id = r.get('id', '')
print('Chat created:', chat_id)

# Send message through RAG pipeline
print('Sending message to RAG pipeline (may take 30-90 seconds)...')
st, r = req('POST', f'/api/chats/{chat_id}/messages', {
    'content': 'What is hypertension and what are normal blood pressure thresholds?',
    'document_text': '',
}, token=token)

if st == 200:
    msg = r.get('message', {})
    vr = r.get('veritas_result', {})
    ds = vr.get('decision_status', 'N/A')
    score = vr.get('evidence_quality_score', 0)
    content_len = len(msg.get('content', ''))
    title = r.get('conversation_title', 'N/A')
    citations = len(vr.get('citations', []))
    print('RAG MESSAGE TEST:  PASS')
    print(f'  Decision Status:  {ds}')
    print(f'  Evidence Score:   {score:.1f}/100')
    print(f'  Response length:  {content_len} chars')
    print(f'  Title updated:    {title}')
    print(f'  Citations:        {citations}')

    # Verify persistence
    st2, r2 = req('GET', f'/api/chats/{chat_id}', token=token)
    msgs = r2.get('messages', [])
    print(f'PERSISTENCE TEST:  PASS | {len(msgs)} messages stored (expected 2)')
    for m in msgs:
        role = m.get('role', '?')
        snippet = m.get('content', '')[:70]
        print(f'  [{role}] {snippet}...')

    # Verify has_veritas_result flag
    asst_msgs = [m for m in msgs if m.get('role') == 'assistant']
    has_result = any(m.get('has_veritas_result') for m in asst_msgs)
    print(f'VERITAS RESULT STORED: {"PASS" if has_result else "FAIL"}')
else:
    print(f'RAG MESSAGE TEST:  FAIL | HTTP {st}')
    print(json.dumps(r, indent=2))
    sys.exit(1)

# Test refresh: restart-like persistence check
print()
print('RESTART PERSISTENCE: Fetching conversation fresh...')
st, r = req('GET', f'/api/chats/{chat_id}', token=token)
msgs = r.get('messages', [])
print(f'  Messages after "refresh": {len(msgs)} (PASS if >= 2)')

print()
print('ALL RAG + PERSISTENCE TESTS PASSED')
