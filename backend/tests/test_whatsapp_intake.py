from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import json
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException
import pytest
from sqlalchemy.exc import DBAPIError
from sqlalchemy import MetaData, ForeignKeyConstraint, CheckConstraint, text as sql
from sqlalchemy.schema import CreateTable

from backend import providers
from backend.tests.test_foundation import foundation, login, company
from backend.tests.test_operations import seed, order
from backend.schema import metadata, migrate_schema


def prepare(client, storage, monkeypatch):
    data = seed(client)
    service = client.app.state.whatsapp_intake
    session = str(uuid4())
    sent, hooks = [], []
    monkeypatch.setenv('FACILITIES_WEBHOOK_ORIGIN', 'https://facilities.example.com')
    def provider(url, headers, payload=None):
        if '/webhooks' in url:
            if payload:
                hooks.append(payload | {'active': True})
                return {'id': 'test-hook'}
            return hooks
        assert url.endswith('/messages/send-text')
        sent.append(payload)
        return {'id': 'test-message'}
    monkeypatch.setattr(providers, 'request_provider', provider)
    with storage.connect() as db:
        db.execute('UPDATE configuration SET openwa_key=:key WHERE id=1', {'key': service.cipher.encrypt(b'test-key-not-real').decode()})
        db.execute("INSERT INTO company_whatsapp(company_id,session_id,status) VALUES(:company,:session,'connected')", {'company': data['tenant']['id'], 'session': session})
    response = client.post('/api/v1/company/whatsapp/intake', json={'enabled': True})
    assert response.status_code == 200, response.text
    assert response.json()['enabled'] is True
    assert hooks[0]['events'] == ['message.received']
    assert hooks[0]['secret'] not in response.text
    data.update(service=service, session=session, secret=hooks[0]['secret'], sent=sent)
    return data


def message(client, data, body, *, phone='5511999999999@c.us', changes=None, signature=True):
    event = {'event': 'message.received', 'sessionId': data['session'], 'timestamp': datetime.now(timezone.utc).isoformat(),
             'data': {'id': str(uuid4()), 'from': phone, 'fromMe': False, 'isGroup': False, 'body': body, 'type': 'chat'}}
    if changes:
        event.update(changes)
    raw = json.dumps(event).encode()
    signed = 'sha256=' + hmac.new(data['secret'].encode(), raw, hashlib.sha256).hexdigest() if signature else 'invalid'
    response = client.post('/api/v1/webhooks/openwa/' + data['tenant']['id'], content=raw,
                           headers={'Origin': '', 'X-Openwa-Signature': signed, 'Content-Type': 'application/json'})
    return response, raw, signed


def say(client, storage, data, text, **kwargs):
    response, _, _ = message(client, data, text, **kwargs)
    assert response.status_code == 202, response.text
    with storage.connect() as db:
        row = db.execute('SELECT payload FROM whatsapp_outbox ORDER BY created_at DESC,id DESC LIMIT 1').fetchone()
    return data['service'].decode(row['payload'])['text']


def test_signed_dialogue_contact_without_login_and_work_order(foundation, monkeypatch):
    client, storage = foundation
    data = prepare(client, storage, monkeypatch)
    with storage.connect() as db:
        users_before = db.execute('SELECT count(*) AS n FROM users').fetchone()['n']
    assert 'nome completo' in say(client, storage, data, 'Olá')
    assert 'Selecione a unidade' in say(client, storage, data, 'João Colaborador')
    assert 'Selecione o local' in say(client, storage, data, '1')
    assert 'Selecione o equipamento' in say(client, storage, data, '1')
    assert 'Descreva o problema' in say(client, storage, data, '0')
    assert 'Revise sua solicitação' in say(client, storage, data, 'O equipamento apresenta vazamento na recepção.')
    with storage.connect() as db:
        assert db.execute('SELECT count(*) AS n FROM occurrences').fetchone()['n'] == 0
    response, raw, signature = message(client, data, '1')
    assert response.status_code == 202
    response = client.post('/api/v1/webhooks/openwa/' + data['tenant']['id'], content=raw, headers={'Origin': '', 'X-Openwa-Signature': signature})
    assert response.status_code == 202
    with storage.connect() as db:
        rows = db.execute('SELECT * FROM occurrences').fetchall()
        assert len(rows) == 1 and rows[0]['requester_id'] is None
        assert rows[0]['requester_contact_id']
        contact = db.execute('SELECT * FROM whatsapp_contacts').fetchone()
        assert '5511999999999' not in contact['phone']
        assert db.execute('SELECT count(*) AS n FROM users').fetchone()['n'] == users_before
        assert db.execute('SELECT count(*) AS n FROM auth_accounts').fetchone()['n'] == users_before
    visible = client.get(data['base'] + '/occurrences').json()
    assert visible[0]['requester_name'] == 'João Colaborador'
    work = order(client, data, visible[0])
    assert work['id']
    with storage.connect() as db:
        assert db.execute('SELECT * FROM order_participants').fetchall() == []
    assert 'Olá, João Colaborador' in say(client, storage, data, 'MENU')
    # Confirmação já persistida não é enviada duas vezes pelo replay do webhook.
    while data['service'].process_one():
        pass
    assert sum('Protocolo: OC-' in item['text'] for item in data['sent']) == 1
    assert all(len(item['text']) <= 4096 for item in data['sent'])
    login(client, 'requester@example.com')
    assert client.get(data['base'] + '/occurrences').json() == []
    assert client.get('/api/v1/company/whatsapp/intake').status_code == 403
    if storage.postgres:
        with pytest.raises(DBAPIError), storage.scoped(client.test_principal, data['tenant']['id']) as db:
            db.execute('SELECT phone FROM whatsapp_contacts')


def test_invalid_events_back_cancel_and_expired_conversation(foundation, monkeypatch):
    client, storage = foundation
    data = prepare(client, storage, monkeypatch)
    assert message(client, data, 'Olá', signature=False)[0].status_code == 403
    assert message(client, data, 'Olá', changes={'sessionId': str(uuid4())})[0].status_code == 202
    assert message(client, data, 'Olá', changes={'timestamp': (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()})[0].status_code == 202
    assert message(client, data, 'Olá', phone='12345678@g.us')[0].status_code == 202
    with storage.connect() as db:
        assert db.execute('SELECT * FROM whatsapp_events').fetchall() == []
    say(client, storage, data, 'oi'); say(client, storage, data, 'Maria Colaboradora')
    say(client, storage, data, '1')
    assert 'Selecione a unidade' in say(client, storage, data, 'VOLTAR')
    say(client, storage, data, '1')
    assert 'Informe o local' in say(client, storage, data, '0')
    say(client, storage, data, 'Sala externa sem cadastro')
    say(client, storage, data, '0')
    assert '10 a 3.000' in say(client, storage, data, 'curto')
    say(client, storage, data, 'Ar-condicionado da sala externa sem refrigeração.')
    say(client, storage, data, '1')
    with storage.connect() as db:
        assert 'Sala externa sem cadastro' in db.execute('SELECT description FROM occurrences').fetchone()['description']
    assert 'Nenhum novo protocolo' in say(client, storage, data, 'CANCELAR')
    with storage.connect() as db:
        db.execute('UPDATE whatsapp_conversations SET expires=0')
    assert 'Olá, Maria Colaboradora' in say(client, storage, data, 'oi')


def test_ambiguous_delivery_is_not_retried_and_disable_cancels(foundation, monkeypatch):
    client, storage = foundation
    data = prepare(client, storage, monkeypatch)
    say(client, storage, data, 'Olá')
    calls = []
    def unavailable(*args):
        calls.append(args)
        raise HTTPException(502, 'Timeout')
    monkeypatch.setattr(providers, 'request_provider', unavailable)
    assert data['service'].process_one()
    assert not data['service'].process_one()
    assert len(calls) == 1
    assert client.get('/api/v1/company/whatsapp/intake').json()['replies']['uncertain'] == 1
    say(client, storage, data, 'MENU')
    monkeypatch.setattr(providers, 'request_provider', lambda *args: {'success': False, 'id': 'failed-message'})
    assert data['service'].process_one()
    assert client.get('/api/v1/company/whatsapp/intake').json()['replies']['uncertain'] == 2
    say(client, storage, data, 'MENU')
    assert client.post('/api/v1/company/whatsapp/intake', json={'enabled': False}).status_code == 200
    assert not data['service'].process_one()
    with storage.connect() as db:
        assert all(not item['payload'] for item in db.execute('SELECT * FROM whatsapp_outbox').fetchall())
        assert db.execute('SELECT * FROM whatsapp_conversations').fetchall() == []
    login(client, 'admin@example.com')
    assert client.get('/api/v1/company/whatsapp/intake').status_code == 403


def test_concurrent_replay_and_public_url_requirement(foundation, monkeypatch):
    client, storage = foundation
    data = prepare(client, storage, monkeypatch)
    _, raw, signature = message(client, data, 'Olá')
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(data['service'].receive, data['tenant']['id'], raw, signature) for _ in range(2)]
        for job in jobs:
            job.result(timeout=15)
    with storage.connect() as db:
        assert db.execute('SELECT count(*) AS n FROM whatsapp_events').fetchone()['n'] == 1
        assert db.execute('SELECT count(*) AS n FROM whatsapp_outbox').fetchone()['n'] == 1
        db.execute("UPDATE whatsapp_outbox SET status='sending',lease_until=0")
    assert not data['service'].process_one()
    assert data['sent'] == []
    monkeypatch.delenv('FACILITIES_WEBHOOK_ORIGIN')
    assert client.post('/api/v1/company/whatsapp/intake', json={'enabled': True}).status_code == 409
    assert client.post('/api/v1/company/whatsapp/intake', json={'enabled': False}).status_code == 200


def test_same_phone_is_a_different_contact_in_each_company(foundation, monkeypatch):
    client, storage = foundation
    first = prepare(client, storage, monkeypatch)
    say(client, storage, first, 'Olá'); say(client, storage, first, 'Pessoa Alpha')
    tenant = company(client, 'Empresa Beta', 'beta')
    login(client, 'ownerbeta@example.com')
    session = str(uuid4())
    with storage.connect() as db:
        db.execute("INSERT INTO company_whatsapp(company_id,session_id,status) VALUES(:company,:session,'connected')", {'company': tenant['id'], 'session': session})
    assert client.post('/api/v1/company/whatsapp/intake', json={'enabled': True}).status_code == 200
    with storage.connect() as db:
        secret = db.execute('SELECT webhook_secret FROM company_whatsapp WHERE company_id=:company', {'company': tenant['id']}).fetchone()['webhook_secret']
    second = first | {'tenant': tenant, 'session': session, 'secret': first['service'].decode(secret)}
    assert 'nome completo' in say(client, storage, second, 'Olá')
    say(client, storage, second, 'Pessoa Beta')
    with storage.connect() as db:
        contacts = db.execute('SELECT * FROM whatsapp_contacts').fetchall()
        assert len(contacts) == 2 and contacts[0]['phone_hash'] != contacts[1]['phone_hash']
    assert client.get(first['base'] + '/occurrences').status_code == 404


def test_private_sender_requires_provider_phone_proof(foundation, monkeypatch):
    client, storage = foundation
    data = prepare(client, storage, monkeypatch)
    original = providers.request_provider
    lookups = []
    def provider(url, headers, payload=None):
        if url.endswith('/phone'):
            lookups.append(url)
            return {'phone': '5511999999999'}
        return original(url, headers, payload)
    monkeypatch.setattr(providers, 'request_provider', provider)
    sender = '123456789012345@lid'
    assert message(client, data, 'Olá', phone=sender, signature=False)[0].status_code == 403
    assert lookups == []
    assert 'nome completo' in say(client, storage, data, 'Olá', phone=sender)
    say(client, storage, data, 'Pessoa Identificada', phone=sender)
    assert '%40lid/phone' in lookups[0]
    # O mesmo telefone em JID normal retoma o mesmo contato e o mesmo rascunho.
    assert 'Selecione o local' in say(client, storage, data, '1')
    with storage.connect() as db:
        assert db.execute('SELECT count(*) AS n FROM whatsapp_contacts').fetchone()['n'] == 1
        assert '123456789012345' not in str(db.execute('SELECT * FROM whatsapp_contacts').fetchall())
    monkeypatch.setattr(providers, 'request_provider', lambda *args: {'phone': sender})
    assert message(client, data, '1', phone=sender)[0].status_code == 503
    monkeypatch.setattr(providers, 'request_provider', original)
    with storage.connect() as db:
        db.execute("UPDATE company_whatsapp SET webhook_secret='',bot_enabled=0")
    for _ in range(2):
        assert client.post('/api/v1/company/whatsapp/intake', json={'enabled': True}).status_code == 409
    assert client.get('/api/v1/company/whatsapp/intake').json()['enabled'] is False


def test_legacy_sqlite_occurrence_upgrade_preserves_child_records(foundation):
    client, storage = foundation
    if storage.postgres:
        pytest.skip('Reconstrução de tabela é exclusiva do SQLite; PostgreSQL usa ALTER.')
    from backend.tests.test_operations import report
    from backend.tests.test_attachments import upload
    data = seed(client)
    occurrence = report(client, data)
    work = order(client, data, occurrence)
    path = data['base'] + '/occurrences/' + occurrence['id'] + '/attachments'
    image = upload(client, path).json()
    copied = MetaData()
    for table in metadata.tables.values():
        table.to_metadata(copied)
    legacy = metadata.tables['occurrences'].to_metadata(copied, name='occurrences_pre0010')
    for constraint in list(legacy.constraints):
        if (isinstance(constraint, ForeignKeyConstraint) and 'requester_contact_id' in constraint.column_keys) or (isinstance(constraint, CheckConstraint) and 'requester_contact_id' in str(constraint.sqltext)):
            legacy.constraints.remove(constraint)
    legacy._columns.remove(legacy.c.requester_contact_id)
    legacy.c.requester_id.nullable = False
    with storage.platform.connect() as db:
        db.exec_driver_sql('PRAGMA foreign_keys=OFF'); db.commit()
        with db.begin():
            db.execute(CreateTable(legacy))
            columns = ','.join(column.name for column in legacy.columns)
            db.execute(sql(f'INSERT INTO occurrences_pre0010({columns}) SELECT {columns} FROM occurrences'))
            db.execute(sql('DROP TABLE occurrences'))
            db.execute(sql('ALTER TABLE occurrences_pre0010 RENAME TO occurrences'))
        db.exec_driver_sql('PRAGMA foreign_keys=ON'); db.commit()
    migrate_schema(storage.platform)
    result = client.get(data['base'] + '/occurrences')
    assert result.json()[0]['id'] == occurrence['id']
    assert result.json()[0]['order_id'] == work['id']
    assert client.get(path + '/' + image['id']).status_code == 200
    with storage.platform.connect() as db:
        assert db.exec_driver_sql('PRAGMA foreign_keys').scalar_one() == 1
        assert db.exec_driver_sql('PRAGMA foreign_key_check').fetchall() == []
