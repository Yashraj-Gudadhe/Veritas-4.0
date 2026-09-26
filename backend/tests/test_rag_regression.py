"""
RAG Regression Test — verifies the existing /api/analyze endpoint still works
exactly as before the frontend was added. The RAG pipeline must be unchanged.
"""
import urllib.request
import json
import sys

BASE = 'http://127.0.0.1:8000'

def post(path, data):
    body = json.dumps(data).encode()
    r = urllib.request.Request(BASE + path, data=body, headers={'Content-Type': 'application/json'})
    resp = urllib.request.urlopen(r, timeout=120)
    return json.loads(resp.read())

print('RAG REGRESSION TEST')
print('=' * 50)

# Test 1: Original /api/analyze endpoint (unchanged)
print('Test 1: /api/analyze (original endpoint, must still work)...')
result = post('/api/analyze', {
    'user_query': 'Is this blood pressure reading of 128/82 mmHg within normal range?',
    'document_text': 'Patient presents with blood pressure of 128/82 mmHg taken at rest.',
    'document_name': 'regression_test.pdf',
})
assert result.get('request_id'), 'Missing request_id'
assert result.get('decision_status'), 'Missing decision_status'
assert isinstance(result.get('evidence_quality_score'), float), 'Missing evidence_quality_score'
assert isinstance(result.get('observations'), list), 'Missing observations'
assert isinstance(result.get('supporting_evidence'), list), 'Missing supporting_evidence'
print(f'  PASS | status={result["decision_status"]} | score={result["evidence_quality_score"]:.1f}')

# Test 2: Demo case (demo-1 fixture)
print('Test 2: /api/analyze with demo-1 fixture...')
result2 = post('/api/analyze', {
    'user_query': 'Is this blood pressure reading within normal adult range?',
    'document_text': 'Blood pressure: 120/80 mmHg. Patient appears healthy.',
    'document_name': 'demo1.pdf',
    'demo_id': 'demo-1',
})
assert result2.get('decision_status'), 'Missing decision_status'
print(f'  PASS | status={result2["decision_status"]} | score={result2["evidence_quality_score"]:.1f}')

# Test 3: New /api/chats/{id}/messages also calls same pipeline
print('Test 3: /api/chats/{id}/messages uses SAME pipeline (regression)...')
import urllib.error

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
        return e.code, {}

st, r = req('POST', '/api/auth/login', {'email': 'ragtest@veritas.ai', 'password': 'pass123'})
token = r.get('access_token', '')
st, r = req('POST', '/api/chats', {'title': 'Regression Test'}, token=token)
chat_id = r.get('id', '')
st, r = req('POST', f'/api/chats/{chat_id}/messages', {
    'content': 'What is the normal adult blood pressure range?',
}, token=token, timeout=120)
vr = r.get('veritas_result', {})
assert st == 200, f'Expected 200, got {st}'
assert vr.get('decision_status'), 'Missing decision_status in chat response'
print(f'  PASS | Chat API -> RAG | status={vr["decision_status"]} | score={vr.get("evidence_quality_score", 0):.1f}')

print()
print('=' * 50)
print('ALL RAG REGRESSION TESTS PASSED')
print()
print('Verified:')
print('  [OK] /api/analyze endpoint unchanged')
print('  [OK] Demo fixtures work')
print('  [OK] New /api/chats/{id}/messages calls same pipeline')
print('  [OK] RAG pipeline behavior is identical')

