import base64
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi import HTTPException
from PIL import Image
from sqlalchemy.exc import DBAPIError

from backend import providers
from backend.whatsapp import safe_qr
from backend.tests.test_foundation import foundation, login, company, company_update
from backend.tests.test_operations import seed


def test_superadmin_only_company_integrations_and_audit(foundation):
    client, _ = foundation
    tenant = company(client)
    base = f"/api/v1/foundation/companies/{tenant['id']}"
    for resource in ('locations', 'users', 'invitation-email'):
        assert client.get(base + '/' + resource).status_code == 403
    assert client.get(f"/api/v1/operations/companies/{tenant['id']}/metadata").status_code == 403
    assert client.get('/api/v1/company/whatsapp').status_code == 403
    assert client.post('/api/v1/company/whatsapp/connect').status_code == 403
    assert client.get(base + '/audit').status_code == 200
    assert client.get('/api/v1/nexus/integrations').status_code == 200
    assert client.put(base, json=company_update(tenant, trade_name='Empresa Alterada')).status_code == 200


def test_company_qr_connection_is_private_and_reuses_session(foundation, monkeypatch):
    client, storage = foundation
    config = client.get('/api/v1/nexus/integrations').json()
    assert client.put('/api/v1/nexus/integrations', json={'expected_version': config['version'], 'openwa_api_key': 'test-openwa-not-real'}).status_code == 200
    data = seed(client)
    identifier = str(uuid4())
    name = 'facilities-' + data['tenant']['id']
    state = ['CREATED']
    sessions, calls = [], []
    output = BytesIO()
    Image.new('RGB', (20, 20), 'white').save(output, 'PNG')
    qr = 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()
    def provider(url, headers, payload=None):
        assert headers['X-API-Key'] == 'test-openwa-not-real'
        calls.append((url, payload))
        if url.endswith('/sessions'):
            if payload:
                assert payload == {'name': name}
                sessions.append({'id': identifier, 'name': name, 'status': 'CREATED'})
                return {'data': sessions[0]}
            return {'sessions': sessions}
        assert identifier in url
        if url.endswith('/start'):
            state[0] = 'QR_READY'
            return {'success': True}
        if url.endswith('/qr'):
            return {'data': {'qrCode': qr}}
        return {'data': {'id': identifier, 'name': name, 'status': state[0]}}
    monkeypatch.setattr(providers, 'request_provider', provider)
    path = '/api/v1/company/whatsapp'
    assert client.get(path).json()['status'] == 'not_connected'
    assert not calls
    assert client.post(path + '/connect').json()['status'] == 'starting'
    response = client.get(path)
    assert response.json()['qr_code'] == qr
    assert response.headers['Cache-Control'] == 'no-store'
    assert identifier not in response.text and 'test-openwa-not-real' not in response.text
    assert client.post(path + '/connect').status_code == 200
    assert len(sessions) == 1
    state[0] = 'READY'
    assert client.get(path).json() == {'configured': True, 'status': 'connected', 'qr_code': None}
    count = len(calls)
    login(client, 'requester@example.com')
    assert client.get(path).status_code == 403
    assert client.post(path + '/connect').status_code == 403
    assert len(calls) == count
    login(client, 'owneralpha@example.com')
    company(client, 'Outra Empresa', 'beta')
    login(client, 'ownerbeta@example.com')
    assert client.get(path).json() == {'configured': True, 'status': 'not_connected', 'qr_code': None}
    assert len(calls) == count
    login(client, 'owneralpha@example.com')
    with storage.connect() as db:
        db.execute('UPDATE company_whatsapp SET lease_until=9999999999')
        audit = str(db.execute('SELECT * FROM audit').fetchall())
        assert qr not in audit and 'test-openwa-not-real' not in audit
    assert client.post(path + '/connect').status_code == 409
    if storage.postgres:
        with pytest.raises(DBAPIError), storage.scoped(client.test_principal, data['tenant']['id']) as db:
            db.execute('SELECT * FROM company_whatsapp')


def test_missing_key_and_wrong_session_never_expose_qr(foundation, monkeypatch):
    client, _ = foundation
    tenant = company(client)
    login(client, 'owneralpha@example.com')
    path = '/api/v1/company/whatsapp'
    assert client.get(path).json()['configured'] is False
    assert client.post(path + '/connect').status_code == 409
    login(client, 'admin@example.com')
    config = client.get('/api/v1/nexus/integrations').json()
    client.put('/api/v1/nexus/integrations', json={'expected_version': config['version'], 'openwa_api_key': 'test-openwa-not-real'})
    login(client, 'owneralpha@example.com')
    def provider(url, headers, payload=None):
        if url.endswith('/sessions') and payload is None:
            return []
        return {'id': str(uuid4()), 'name': 'another-company', 'status': 'QR_READY'}
    monkeypatch.setattr(providers, 'request_provider', provider)
    assert client.post(path + '/connect').status_code == 502
    login(client, 'admin@example.com')
    assert client.put(f"/api/v1/foundation/companies/{tenant['id']}", json=company_update(tenant, is_active=False)).status_code == 200
    assert client.post('/api/v1/auth/login', json={'email': 'owneralpha@example.com', 'password': 'Valid-test-password-123!'}).status_code == 401


@pytest.mark.parametrize('value', ['https://example.com/qr.png', 'data:image/svg+xml;base64,PHN2Zy8+', 'A' * 800001], ids=['remote', 'svg', 'oversized'])
def test_qr_rejects_remote_and_invalid_images(value):
    with pytest.raises(HTTPException):
        safe_qr(value)


def test_corrupt_png_is_a_controlled_provider_error():
    output = BytesIO()
    Image.new('RGB', (20, 20), 'white').save(output, 'PNG')
    raw = bytearray(output.getvalue())
    raw[29] ^= 1
    with pytest.raises(HTTPException) as error:
        safe_qr(base64.b64encode(raw).decode())
    assert error.value.status_code == 502
