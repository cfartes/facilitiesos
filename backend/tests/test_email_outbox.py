import time
from io import BytesIO
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend import providers
from backend.tests.test_foundation import foundation, company, company_update, accept, login

KEY = 'resend-unit-test-key-not-real'


def configure(client, enabled=True, **changes):
    current = client.get('/api/v1/nexus/integrations').json()
    response = client.put('/api/v1/nexus/integrations', json={'expected_version': current['version'], 'resend_api_key': KEY,
        'email_from': 'facilities@example.com', 'invitation_email_enabled': enabled} | changes)
    assert response.status_code == 200, response.text
    return response.json()


def invite(client, company_id, email='queued@example.com', send=True):
    return client.post(f'/api/v1/foundation/companies/{company_id}/users', json={'name': 'Pessoa convidada', 'email': email,
        'roles': ['requester'], 'all_units': True, 'unit_ids': [], 'send_email': send})


def jobs(storage):
    with storage.connect() as db:
        return db.execute('SELECT * FROM email_outbox ORDER BY created_at,id').fetchall()


def test_opt_in_atomicity_encryption_and_acceptance(foundation, monkeypatch):
    client, storage = foundation
    tenant = company(client)
    disabled = invite(client, tenant['id'])
    assert disabled.status_code == 409
    assert not jobs(storage)
    assert all(row['email'] != 'queued@example.com' for row in client.get(f"/api/v1/foundation/companies/{tenant['id']}/users").json())
    configure(client)
    queued = invite(client, tenant['id'])
    assert queued.status_code == 201, queued.text
    assert queued.json()['invitation']['email_queued']
    token = parse_qs(urlsplit(queued.json()['invitation']['url']).fragment)['token'][0]
    stored = jobs(storage)[0]
    assert token not in stored['payload'] and 'queued@example.com' not in stored['payload']
    sends = []
    def send(key, payload, identity):
        sends.append((key, payload, identity))
        return 'provider-email-id'
    monkeypatch.setattr(providers, 'resend_invitation', send)
    outbox = client.app.state.email_outbox
    assert outbox.process_one()
    assert not outbox.process_one()
    row = jobs(storage)[0]
    assert row['status'] == 'accepted' and row['payload'] == '' and row['attempts'] == 1
    assert len(sends) == 1 and sends[0][0] == KEY
    assert token in sends[0][1]['text']
    listing = client.get(f"/api/v1/foundation/companies/{tenant['id']}/users")
    assert token not in listing.text and KEY not in listing.text and 'payload' not in listing.text
    assert any(row['invitation_email'] and row['invitation_email']['status'] == 'accepted' for row in listing.json())
    manual = invite(client, tenant['id'], email='manual@example.com', send=False)
    assert manual.status_code == 201 and not manual.json()['invitation']['email_queued']
    assert len(jobs(storage)) == 1


def test_retry_same_payload_bounded_attempts_and_lease_recovery(foundation, monkeypatch):
    client, storage = foundation
    tenant = company(client); configure(client)
    assert invite(client, tenant['id']).status_code == 201
    outbox = client.app.state.email_outbox
    moment = [time.time()]
    outbox.clock = lambda: moment[0]
    attempts = []
    def send(key, payload, identity):
        attempts.append((payload, identity))
        raise providers.InvitationSendError('Falha temporária no provedor.', True, 120)
    monkeypatch.setattr(providers, 'resend_invitation', send)
    for count in range(1, 6):
        assert outbox.process_one()
        row = jobs(storage)[0]
        assert row['attempts'] == count
        assert row['status'] == ('retrying' if count < 5 else 'failed')
        assert not outbox.process_one()
        moment[0] = row['next_attempt_at'] + 1
    assert len(attempts) == 5 and all(item == attempts[0] for item in attempts)
    assert jobs(storage)[0]['payload'] == ''
    assert invite(client, tenant['id'], email='lease@example.com').status_code == 201
    claimed = outbox._claim()
    assert claimed and claimed[0]['attempts'] == 1
    assert not outbox.process_one()
    moment[0] += 121
    assert outbox.process_one()
    assert jobs(storage)[1]['attempts'] == 2


def test_revocation_used_invitation_and_expiry_cancel_pending(foundation, monkeypatch):
    client, storage = foundation
    tenant = company(client); configure(client)
    first = invite(client, tenant['id']).json()
    second = client.post(f"/api/v1/foundation/companies/{tenant['id']}/users/{first['user']['id']}/invitation", json={'send_email': True})
    assert second.status_code == 200
    assert jobs(storage)[0]['status'] == 'cancelled' and jobs(storage)[0]['payload'] == ''
    accept(client, {'invitation': second.json()})
    assert all(row['status'] == 'cancelled' and row['payload'] == '' for row in jobs(storage))
    expired = invite(client, tenant['id'], email='expired@example.com')
    assert expired.status_code == 201
    with storage.connect() as db:
        db.execute('UPDATE email_outbox SET expires=0 WHERE user_id=:id', {'id': expired.json()['user']['id']})
    monkeypatch.setattr(providers, 'resend_invitation', lambda *args: pytest.fail('Revoked invitations must not be sent'))
    assert not client.app.state.email_outbox.process_one()
    assert all(row['status'] == 'cancelled' for row in jobs(storage))


def test_configuration_pause_credential_rotation_and_safe_retry_window(foundation, monkeypatch):
    client, storage = foundation
    tenant = company(client); configure(client)
    assert invite(client, tenant['id']).status_code == 201
    configure(client, enabled=False)
    outbox = client.app.state.email_outbox
    assert not outbox.process_one() and jobs(storage)[0]['attempts'] == 0
    configure(client, resend_api_key='replacement-test-key-not-real')
    monkeypatch.setattr(providers, 'resend_invitation', lambda *args: pytest.fail('Credential rotation must stop old queued sends'))
    assert outbox.process_one()
    assert jobs(storage)[0]['status'] == 'failed' and jobs(storage)[0]['payload'] == ''
    configure(client)
    assert invite(client, tenant['id'], email='window@example.com').status_code == 201
    outbox._claim()
    moment = time.time() + 24 * 3600
    outbox.clock = lambda: moment
    assert outbox.process_one()
    assert jobs(storage)[1]['status'] == 'failed'


def test_company_suspension_and_cross_company_permissions(foundation, monkeypatch):
    client, storage = foundation
    tenant = company(client); configure(client)
    assert invite(client, tenant['id']).status_code == 201
    other = company(client, 'Empresa Beta', 'beta')
    login(client, 'owneralpha@example.com')
    assert client.get(f"/api/v1/foundation/companies/{other['id']}/invitation-email").status_code == 404
    assert client.get(f"/api/v1/foundation/companies/{other['id']}/users").status_code == 404
    assert client.get('/api/v1/nexus/integrations').status_code == 403
    if storage.postgres:
        with storage.tenant.begin() as db:
            with pytest.raises(DBAPIError):
                db.execute(text('SELECT * FROM email_outbox'))
    login(client, 'admin@example.com')
    assert client.put(f"/api/v1/foundation/companies/{tenant['id']}", json=company_update(tenant, is_active=False)).status_code == 200
    assert jobs(storage)[0]['status'] == 'cancelled' and jobs(storage)[0]['payload'] == ''
    monkeypatch.setattr(providers, 'resend_invitation', lambda *args: pytest.fail('Suspended company must not send'))
    assert not client.app.state.email_outbox.process_one()


def test_reissue_failure_rolls_back_and_inflight_revocation_is_not_overwritten(foundation, monkeypatch):
    client, storage = foundation
    tenant = company(client); configure(client)
    first = invite(client, tenant['id']).json()
    configure(client, enabled=False)
    path = f"/api/v1/foundation/companies/{tenant['id']}/users/{first['user']['id']}/invitation"
    assert client.post(path, json={'send_email': True}).status_code == 409
    assert jobs(storage)[0]['status'] == 'queued'
    configure(client)
    def send(*args):
        # Simula uma revogação enquanto a chamada já está em andamento no provedor.
        with storage.connect() as db:
            client.app.state.email_outbox.cancel(db, first['user']['id'], 'Convite revogado durante o envio.')
        return 'already-in-flight'
    monkeypatch.setattr(providers, 'resend_invitation', send)
    assert client.app.state.email_outbox.process_one()
    assert jobs(storage)[0]['status'] == 'cancelled' and jobs(storage)[0]['payload'] == ''
    # A falha na reemissão preservou o convite original; somente seu envio foi cancelado.
    accept(client, first)


@pytest.mark.parametrize('status,retryable', [(401,False),(422,False),(429,True),(503,True),(302,False)])
def test_provider_failures_are_sanitized_and_classified(monkeypatch, status, retryable):
    class Opener:
        def open(self, request, timeout):
            assert request.get_header('Idempotency-key') == 'test-idempotency'
            raise HTTPError(request.full_url, status, 'secret-response', {'Retry-After':'180'}, BytesIO(b'secret-token'))
    monkeypatch.setattr(providers, 'build_opener', lambda *args: Opener())
    with pytest.raises(providers.InvitationSendError) as error:
        providers.resend_invitation(KEY, {'text':'secret-token'}, 'test-idempotency')
    assert error.value.retryable is retryable
    assert error.value.retry_after == 180
    assert 'secret' not in str(error.value)
