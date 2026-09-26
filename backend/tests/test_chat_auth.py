"""
Backend API test suite for the new VERITAS chat authentication and conversation endpoints.
Tests all critical flows without touching the RAG pipeline.
"""
import urllib.request
import json
import sys

BASE = 'http://127.0.0.1:8000'
results = []

def req(method, path, data=None, token=None):
    url = BASE + path
    body = json.dumps(data).encode() if data else None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    r = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(r)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}

def check(name, cond, detail=''):
    status = 'PASS' if cond else 'FAIL'
    results.append((name, status))
    print(f"{name:<30} {status}  {detail}")
    return cond

# ── Health ──
st, h = req('GET', '/api/health')
check('Health Check', st == 200, h.get('status', ''))

# ── Register User A ──
st, r = req('POST', '/api/auth/register', {'name': 'Dr. Alice', 'email': 'alice_test@veritas.ai', 'password': 'password123'})
check('Register User A', st in (201, 400))  # 400 = already exists from prev run
if st == 201:
    token_a = r.get('access_token', '')
else:
    # Already registered, login instead
    st2, r2 = req('POST', '/api/auth/login', {'email': 'alice_test@veritas.ai', 'password': 'password123'})
    token_a = r2.get('access_token', '')

# ── Duplicate email ──
st, _ = req('POST', '/api/auth/register', {'name': 'Alice2', 'email': 'alice_test@veritas.ai', 'password': 'abc123'})
check('Duplicate Email Rejected', st == 400, f'HTTP {st}')

# ── Login ──
st, r = req('POST', '/api/auth/login', {'email': 'alice_test@veritas.ai', 'password': 'password123'})
check('Login', st == 200, f'HTTP {st}')
token_a = r.get('access_token', token_a)

# ── Wrong password ──
st, _ = req('POST', '/api/auth/login', {'email': 'alice_test@veritas.ai', 'password': 'wrongpassword'})
check('Wrong Password Rejected', st == 401, f'HTTP {st}')

# ── /auth/me ──
st, r = req('GET', '/api/auth/me', token=token_a)
check('GET /auth/me', st == 200, r.get('email', ''))

# ── Unauthenticated request ──
st, _ = req('GET', '/api/chats')
check('Unauthenticated Chats 401', st == 401, f'HTTP {st}')

# ── Create conversation ──
st, r = req('POST', '/api/chats', {'title': 'Test Chat'}, token=token_a)
check('Create Conversation', st == 201, f'HTTP {st}')
chat_id = r.get('id', '')

# ── List conversations ──
st, r = req('GET', '/api/chats', token=token_a)
check('List Conversations', st == 200, f'count={len(r)}')

# ── Get conversation ──
st, r = req('GET', f'/api/chats/{chat_id}', token=token_a)
check('Get Conversation', st == 200, f'msgs={len(r.get("messages", []))}')

# ── Rename conversation ──
st, r = req('PATCH', f'/api/chats/{chat_id}', {'title': 'Renamed Chat'}, token=token_a)
check('Rename Conversation', st == 200 and r.get('title') == 'Renamed Chat', r.get('title', ''))

# ── Register User B ──
st, r = req('POST', '/api/auth/register', {'name': 'Dr. Bob', 'email': 'bob_test@veritas.ai', 'password': 'password123'})
check('Register User B', st in (201, 400))
if st == 201:
    token_b = r.get('access_token', '')
else:
    st2, r2 = req('POST', '/api/auth/login', {'email': 'bob_test@veritas.ai', 'password': 'password123'})
    token_b = r2.get('access_token', '')

# ── User isolation: B cannot access A's chat ──
st, _ = req('GET', f'/api/chats/{chat_id}', token=token_b)
check('User Isolation GET', st == 404, f'HTTP {st}')

st, _ = req('DELETE', f'/api/chats/{chat_id}', token=token_b)
check('User Isolation DELETE', st == 404, f'HTTP {st}')

# ── Account endpoint ──
st, r = req('GET', '/api/account/me', token=token_a)
check('GET /account/me', st == 200, r.get('email', ''))

# ── Update account name ──
st, r = req('PATCH', '/api/account/me', {'name': 'Dr. Alice Updated'}, token=token_a)
check('PATCH /account/me', st == 200, r.get('name', ''))

# ── Delete conversation ──
st = None
r_del = urllib.request.Request(BASE + f'/api/chats/{chat_id}',
    headers={'Authorization': f'Bearer {token_a}'}, method='DELETE')
try:
    resp = urllib.request.urlopen(r_del)
    st = resp.status
except urllib.error.HTTPError as e:
    st = e.code
check('Delete Conversation', st == 204, f'HTTP {st}')

# ── Verify conversation is gone ──
st, _ = req('GET', f'/api/chats/{chat_id}', token=token_a)
check('Deleted Conversation Gone', st == 404, f'HTTP {st}')

# ── Summary ──
print()
print('=' * 50)
passed = sum(1 for _, s in results if s == 'PASS')
failed = sum(1 for _, s in results if s == 'FAIL')
print(f'Results: {passed} PASS, {failed} FAIL out of {len(results)} tests')
if failed:
    print('FAILED TESTS:')
    for name, s in results:
        if s == 'FAIL':
            print(f'  - {name}')
    sys.exit(1)
else:
    print('ALL TESTS PASSED')
