import json
import re
import secrets
import time

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend import providers
from backend.password_reset import REQUEST_MESSAGE
from backend.security import digest
from backend.tests.test_foundation import foundation, company, company_update, member, accept, login, PASSWORD
from backend.tests.test_email_outbox import configure, jobs

NEW_PASSWORD = 'Changed-test-password-456!'
BASE = '/api/v1/public/password-reset'


def request(client, email='owneralpha@example.com'):
    return client.post(BASE + '/request', json={'email': email})


def token(client, storage):
    rows = [row for row in jobs(storage) if row['kind'] == 'password_reset']
    payload = json.loads(client.app.state.email_outbox.cipher.decrypt(rows[-1]['payload'].encode()))
    return re.search(r'token=([A-Za-z0-9_-]+)', payload['text']).group(1)


def confirm(client, value, password=NEW_PASSWORD):
    return client.post(BASE + '/confirm', json={'token': value, 'password': password})


def test_reset_complete_single_use_sessions_and_notice(foundation, monkeypatch):
    client, storage = foundation
    tenant = company(client); configure(client, password_reset_enabled=True)
    response = request(client)
    assert response.status_code == 202 and response.json() == {'message': REQUEST_MESSAGE}
    value = token(client, storage)
    assert value not in response.text and 'token' not in response.json()
    with storage.connect() as db:
        user = db.execute('SELECT id FROM users WHERE company_id=:company', {'company': tenant['id']}).fetchone()
        for _ in range(2):
            db.execute('INSERT INTO sessions(token_hash,csrf_hash,email,role,expires,credential_hash) VALUES(:token,:csrf,:email,:role,:expires,:credential)', {
                'token': digest(secrets.token_urlsafe(48)), 'csrf': digest('test-csrf'), 'email': 'owneralpha@example.com',
                'role': 'company_user', 'expires': time.time() + 3600, 'credential': digest('old-credential'),
            })
        assert db.execute('SELECT token_hash FROM password_resets WHERE user_id=:id', {'id': user['id']}).fetchone()['token_hash'] == digest(value)
    sends = []
    monkeypatch.setattr(providers, 'resend_invitation', lambda key, payload, identity: sends.append(payload) or 'provider-reset-id')
    outbox = client.app.state.email_outbox
    assert outbox.process_one()
    assert value in sends[0]['text']
    assert confirm(client, value, PASSWORD).status_code == 422
    result = confirm(client, value)
    assert result.status_code == 200, result.text
    assert NEW_PASSWORD not in result.text and value not in result.text
    with storage.connect() as db:
        assert not db.execute('SELECT * FROM sessions WHERE email=:email', {'email': 'owneralpha@example.com'}).fetchall()
        assert db.execute('SELECT * FROM sessions WHERE email=:email', {'email': 'admin@example.com'}).fetchall()
    assert confirm(client, value).status_code == 400
    assert outbox.process_one()
    assert len(sends) == 2 and 'foi alterada' in sends[1]['text']
    assert value not in sends[1]['text'] and NEW_PASSWORD not in sends[1]['text']
    assert all(row['payload'] == '' for row in jobs(storage))
    assert client.post('/api/v1/auth/login', json={'email': 'owneralpha@example.com', 'password': PASSWORD}).status_code == 401
    login(client, 'owneralpha@example.com', NEW_PASSWORD)
    assert client.get('/api/v1/auth/me').status_code == 200


def test_generic_responses_pending_invitation_and_valid_request_does_not_revoke(foundation):
    client, storage = foundation
    tenant = company(client); configure(client, password_reset_enabled=True)
    invited = member(client, tenant['id'], email='pending@example.com')
    for email in ('unknown@example.com', 'pending@example.com', 'admin@example.com'):
        assert request(client, email).json() == {'message': REQUEST_MESSAGE}
    assert not jobs(storage)
    assert request(client).status_code == 202
    value = token(client, storage)
    for _ in range(3):
        response = request(client)
        assert response.status_code == 202 and response.json() == {'message': REQUEST_MESSAGE}
    assert len(jobs(storage)) == 1 and token(client, storage) == value
    invitation_token = invited['invitation']['url'].split('token=')[1]
    assert confirm(client, invitation_token).status_code == 400
    assert client.post('/api/v1/public/invitations/accept', json={'token': value, 'password': NEW_PASSWORD}).status_code == 400
    assert confirm(client, value).status_code == 200


def test_disabled_recovery_and_disabled_invites_are_independent(foundation):
    client, storage = foundation
    company(client); configure(client, password_reset_enabled=False)
    assert request(client).json() == {'message': REQUEST_MESSAGE}
    assert not jobs(storage)
    configure(client, enabled=False, password_reset_enabled=True)
    assert request(client).status_code == 202
    value = token(client, storage)
    configure(client, password_reset_enabled=False)
    assert jobs(storage)[0]['status'] == 'cancelled' and jobs(storage)[0]['payload'] == ''
    configure(client, password_reset_enabled=True)
    assert confirm(client, value).status_code == 400


def test_expiry_suspension_and_changed_credential_invalidate_tokens(foundation, monkeypatch):
    client, storage = foundation
    tenant = company(client); configure(client, password_reset_enabled=True)
    assert request(client).status_code == 202
    value = token(client, storage)
    with storage.connect() as db:
        db.execute('UPDATE password_resets SET expires=0')
    assert confirm(client, value).status_code == 400
    assert not client.app.state.email_outbox.process_one()
    assert jobs(storage)[0]['status'] == 'cancelled'
    assert request(client).status_code == 202
    value = token(client, storage)
    with storage.connect() as db:
        db.execute("UPDATE password_resets SET credential_hash=:hash", {'hash': digest('different-credential')})
    assert confirm(client, value).status_code == 400
    monkeypatch.setattr(providers, 'resend_invitation', lambda *args: pytest.fail('Stale credential must not receive reset email'))
    assert client.app.state.email_outbox.process_one()
    assert jobs(storage)[-1]['status'] == 'cancelled'
    assert request(client).status_code == 202
    value = token(client, storage)
    assert client.put(f"/api/v1/foundation/companies/{tenant['id']}", json=company_update(tenant, is_active=False)).status_code == 200
    assert confirm(client, value).status_code == 400
    assert request(client).json() == {'message': REQUEST_MESSAGE}


def test_origin_rate_limits_payload_validation_and_platform_only_table(foundation):
    client, storage = foundation
    company(client); configure(client, password_reset_enabled=True)
    assert client.get('/api/v1/_test/mailbox?recipient=unknown@example.com').status_code == 404
    assert client.post(BASE + '/request', json={'email': 'unknown@example.com'}, headers={'Origin': 'https://external.invalid'}).status_code == 403
    assert client.post(BASE + '/request', json={'email': 'unknown@example.com', 'company_id':'forged'}).status_code == 422
    assert client.post(BASE + '/confirm', json={'token': 'not-a-valid-token', 'password': 'weak'}).status_code == 422
    for index in range(10):
        assert request(client, f'unknown{index}@example.com').status_code == 202
    response = request(client)
    assert response.status_code == 429 and response.headers['Retry-After']
    if storage.postgres:
        with storage.tenant.begin() as db:
            with pytest.raises(DBAPIError):
                db.execute(text('SELECT * FROM password_resets'))


def test_user_reactivation_does_not_revive_reset_and_provider_errors_are_generic(foundation):
    client, storage = foundation
    tenant = company(client); configure(client, password_reset_enabled=True)
    invited = member(client, tenant['id'], email='recover-user@example.com')
    accept(client, invited)
    assert request(client, 'recover-user@example.com').status_code == 202
    value = token(client, storage)
    path = f"/api/v1/foundation/companies/{tenant['id']}/users/{invited['user']['id']}"
    body = {'name': invited['user']['name'], 'roles':['requester'], 'all_units':True, 'unit_ids':[], 'is_active':False, 'expected_version':1}
    assert client.put(path, json=body).status_code == 200
    assert client.put(path, json=body | {'is_active':True, 'expected_version':2}).status_code == 200
    assert confirm(client, value).status_code == 400
    with storage.connect() as db:
        db.execute("UPDATE configuration SET resend_key='invalid-ciphertext'")
    response = request(client)
    assert response.status_code == 202 and response.json() == {'message': REQUEST_MESSAGE}
    assert request(client, 'unknown@example.com').json() == response.json()
    assert all(row['status'] == 'cancelled' for row in jobs(storage))
