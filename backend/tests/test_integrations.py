import sqlite3
import time

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.main import create_app
from backend import providers
from backend.security import digest, password_hash

ORIGIN = 'http://127.0.0.1:5180'
PASSWORD = 'Local-test-password-123!'
OPENWA_KEY = 'owa_test_secret_not_real'
RESEND_KEY = 're_test_secret_not_real'


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / 'test.db'
    key = Fernet.generate_key()
    app = create_app(path, 'admin@example.com', password_hash(PASSWORD), key, ORIGIN, start_email_worker=False)
    with TestClient(app, base_url=ORIGIN, headers={'Origin': ORIGIN}) as client:
        yield client, path, key


def login(client):
    response = client.post('/api/v1/auth/login', json={'email': 'admin@example.com', 'password': PASSWORD})
    assert response.status_code == 200
    client.headers['X-CSRF-Token'] = client.cookies.get('facilities_csrf')


def save(client, **kwargs):
    return client.put('/api/v1/nexus/integrations', json={'expected_version': 0, **kwargs})


def test_requires_authentication(setup):
    client, _, _ = setup
    assert client.get('/api/v1/nexus/integrations').status_code == 401
    assert save(client).status_code == 401
    assert client.post('/api/v1/nexus/integrations/test/openwa').status_code == 401


def test_secrets_are_encrypted_and_never_returned(setup):
    client, path, key = setup
    login(client)
    result = save(client, openwa_api_key=OPENWA_KEY, resend_api_key=RESEND_KEY, email_from='sender@example.com')
    assert result.status_code == 200
    assert result.json()['openwa_key_configured'] is True
    assert result.json()['resend_key_configured'] is True
    assert OPENWA_KEY not in result.text and RESEND_KEY not in result.text
    read = client.get('/api/v1/nexus/integrations')
    assert OPENWA_KEY not in read.text and 'openwa_key' not in read.json()
    with sqlite3.connect(path) as db:
        row = db.execute('SELECT openwa_key,resend_key FROM configuration').fetchone()
        assert row[0] != OPENWA_KEY
        assert Fernet(key).decrypt(row[0].encode()).decode() == OPENWA_KEY
        assert Fernet(key).decrypt(row[1].encode()).decode() == RESEND_KEY
        audit = db.execute('SELECT action FROM audit').fetchall()
        assert OPENWA_KEY not in str(audit) and RESEND_KEY not in str(audit)
    # O arquivo principal e WAL não contêm as chaves em texto puro.
    for file in path.parent.glob('test.db*'):
        assert OPENWA_KEY.encode() not in file.read_bytes()
        assert RESEND_KEY.encode() not in file.read_bytes()


def test_preserve_replace_remove_and_conflict(setup):
    client, _, _ = setup
    login(client)
    assert save(client, openwa_api_key=OPENWA_KEY).status_code == 200
    assert save(client, openwa_api_key='owa_conflicting_key').status_code == 409
    assert client.put('/api/v1/nexus/integrations', json={'expected_version': 1}).json()['openwa_key_configured']
    replacement = client.put('/api/v1/nexus/integrations', json={'expected_version': 2, 'openwa_api_key': 'owa_replacement_key'})
    assert replacement.status_code == 200
    removed = client.put('/api/v1/nexus/integrations', json={'expected_version': 3, 'clear_openwa_key': True})
    assert removed.json()['openwa_key_configured'] is False


def test_csrf_origin_and_restricted_role(setup):
    client, path, _ = setup
    login(client)
    assert client.put('/api/v1/nexus/integrations', json={'expected_version': 0}, headers={'Origin': 'https://evil.example'}).status_code == 403
    assert client.put('/api/v1/nexus/integrations', json={'expected_version': 0}, headers={'X-CSRF-Token': 'incorrect'}).status_code == 403
    with sqlite3.connect(path) as db:
        db.execute("UPDATE sessions SET role='nexus_restricted'")
    assert client.get('/api/v1/nexus/integrations').status_code == 403
    assert save(client).status_code == 403


@pytest.mark.parametrize('payload', [
    {'openwa_api_key': 'bad key secret'},
    {'openwa_api_key': OPENWA_KEY, 'clear_openwa_key': True},
    {'resend_api_key': RESEND_KEY},
    {'email_from': 'bad-email'},
    {'unexpected': 'field'},
    {'expected_version': True},
])
def test_validation_is_redacted(setup, payload):
    client, _, _ = setup
    login(client)
    response = save(client, **payload)
    assert response.status_code == 422
    assert 'bad key secret' not in response.text
    assert OPENWA_KEY not in response.text
    assert RESEND_KEY not in response.text


def test_openwa_uses_saved_key_and_returns_sanitized_sessions(setup, monkeypatch):
    client, _, _ = setup
    login(client)
    assert save(client, openwa_api_key=OPENWA_KEY).status_code == 200
    def fake_request(url, headers, payload=None):
        assert url == providers.OPENWA_BASE + '/sessions'
        assert headers['X-API-Key'] == OPENWA_KEY
        assert payload is None
        return {'data': [{'id': 'session-id', 'name': 'Pilot', 'status': 'READY', 'secret': 'private', 'phone': '55555'}]}
    monkeypatch.setattr(providers, 'request_provider', fake_request)
    result = client.post('/api/v1/nexus/integrations/test/openwa')
    assert result.status_code == 200
    assert result.json()['sessions'] == [{'id': 'session-id', 'name': 'Pilot', 'status': 'READY'}]


def test_resend_only_sends_on_explicit_test(setup, monkeypatch):
    client, _, _ = setup
    login(client)
    calls = []
    def fake_request(url, headers, payload=None):
        calls.append(payload)
        assert url == 'https://api.resend.com/emails'
        assert headers['Authorization'] == f'Bearer {RESEND_KEY}'
        assert payload['to'] == ['recipient@example.com']
        assert payload['from'] == 'Nexus Facilities OS <sender@example.com>'
        return {'id': 'email-id'}
    monkeypatch.setattr(providers, 'request_provider', fake_request)
    assert save(client, resend_api_key=RESEND_KEY, email_from='sender@example.com').status_code == 200
    assert not calls
    result = client.post('/api/v1/nexus/integrations/test/resend', json={'recipient': 'recipient@example.com'})
    assert result.status_code == 200
    assert 'não confirma a entrega' in result.json()['message']
    assert len(calls) == 1


def test_missing_key_logout_and_expired_session(setup):
    client, path, _ = setup
    login(client)
    assert client.post('/api/v1/nexus/integrations/test/openwa').status_code == 409
    token_hash = digest(client.cookies.get('facilities_session'))
    assert client.post('/api/v1/auth/logout').status_code == 204
    assert client.get('/api/v1/auth/me').status_code == 401
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT 1 FROM sessions WHERE token_hash=?', (token_hash,)).fetchone() is None
    login(client)
    with sqlite3.connect(path) as db:
        db.execute('UPDATE sessions SET expires=?', (time.time() - 1,))
    assert client.get('/api/v1/auth/me').status_code == 401


def test_rate_limiting_is_persistent(setup):
    client, _, _ = setup
    for _ in range(10):
        assert client.post('/api/v1/auth/login', json={'email': 'admin@example.com', 'password': 'wrong'}).status_code == 401
    result = client.post('/api/v1/auth/login', json={'email': 'admin@example.com', 'password': PASSWORD})
    assert result.status_code == 429
    assert int(result.headers['Retry-After']) > 0


def test_error_headers_and_body_limit(setup):
    client, _, _ = setup
    response = client.get('/api/v1/nexus/integrations')
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['X-Frame-Options'] == 'DENY'
    assert client.post('/api/v1/auth/login', content='x' * 25000).status_code == 413


def test_provider_failure_and_wrong_encryption_key_do_not_leak(setup, monkeypatch):
    client, path, _ = setup
    login(client)
    save(client, openwa_api_key=OPENWA_KEY)
    def failure(key):
        raise HTTPException(502, 'O provedor recusou a API Key.')
    monkeypatch.setattr(providers, 'openwa_sessions', failure)
    result = client.post('/api/v1/nexus/integrations/test/openwa')
    assert result.status_code == 502 and OPENWA_KEY not in result.text
    with sqlite3.connect(path) as db:
        db.execute("UPDATE configuration SET openwa_key='invalid-ciphertext'")
    assert client.post('/api/v1/nexus/integrations/test/openwa').status_code == 503


def test_production_is_blocked_without_postgresql(setup, monkeypatch):
    monkeypatch.setenv('FACILITIES_ENV', 'production')
    monkeypatch.delenv('FACILITIES_PLATFORM_DATABASE_URL', raising=False)
    monkeypatch.delenv('FACILITIES_DATABASE_URL', raising=False)
    with pytest.raises(RuntimeError, match='PostgreSQL'):
        create_app()
