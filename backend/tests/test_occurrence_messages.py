from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError

from backend.tests.test_foundation import foundation, login, member, accept, location, company
from backend.tests.test_operations import seed, report, order, detail


def test_private_history_idempotency_and_linking(foundation):
    client, storage = foundation
    data = seed(client)
    occurrence = report(client, data)
    path = data['base'] + '/occurrences/' + occurrence['id'] + '/messages'
    login(client, 'requester@example.com')
    body = {'body': 'O vazamento aumentou desde a abertura.', 'client_request_id': str(uuid4())}
    assert client.post(path, json=body).status_code == 201
    assert client.post(path, json=body).status_code == 201
    assert client.post(path, json=body | {'body': 'Outro texto'}).status_code == 409
    history = client.get(path).json()
    assert len(history['items']) == 1
    assert history['version'] == occurrence['version'] + 1
    assert history['can_add']
    assert client.get(data['base'] + '/occurrences').json()[0]['first_response_at'] is None
    assert client.post(path, json=body | {'body': '  ', 'client_request_id': str(uuid4())}).status_code == 422
    assert client.post(path, json=body | {'body': 'x' * 4001}).status_code == 422
    login(client, 'other@example.com')
    assert client.get(path).status_code == 404
    assert client.post(path, json=body).status_code == 404
    login(client, 'owneralpha@example.com')
    assert client.post(path, json={'body': 'A equipe está avaliando o relato.', 'client_request_id': str(uuid4())}).status_code == 201
    current = client.get(data['base'] + '/occurrences').json()[0]
    assert current['first_response_at'] is not None
    work = order(client, data, current)
    assert client.get(path).json()['can_add'] is False
    assert client.post(path, json={'body': 'Novo texto', 'client_request_id': str(uuid4())}).status_code == 409
    login(client, 'tech@example.com')
    assert client.get(path).status_code == 404
    assert 'O vazamento aumentou' not in str(detail(client, data, work['id']))
    if storage.postgres:
        principal = {'role': 'company_user', 'id': data['people']['tech']['id'], 'roles': ['technician'], 'all_units': True, 'unit_ids': []}
        with storage.scoped(principal, data['tenant']['id']) as db:
            assert db.execute('SELECT * FROM occurrence_messages').fetchall() == []
    login(client, 'requester@example.com')
    assert len(client.get(path).json()['items']) == 2
    assert client.post(path, json=body).status_code == 201
    alerts = client.get(data['base'] + '/notifications').json()
    assert any(item['title'] == 'Novo complemento no relato privado.' for item in alerts)


def test_history_scope_auditor_and_postgres_immutability(foundation):
    client, storage = foundation
    data = seed(client)
    occurrence = report(client, data)
    path = data['base'] + '/occurrences/' + occurrence['id'] + '/messages'
    other_unit = location(client, data['tenant']['id'], name='Outra unidade')
    for key, roles, all_units in [('audit', ['auditor'], True), ('restricted', ['supervisor'], False)]:
        invited = member(client, data['tenant']['id'], email=key + '@example.com', roles=roles, all_units=all_units,
                         unit_ids=[] if all_units else [other_unit['id']])
        accept(client, invited)
    login(client, 'audit@example.com')
    assert client.get(path).json()['can_add'] is False
    assert client.post(path, json={'body': 'Tentativa', 'client_request_id': str(uuid4())}).status_code == 403
    login(client, 'restricted@example.com')
    assert client.get(path).status_code == 404
    login(client, 'owneralpha@example.com')
    other = company(client, 'Outra empresa', 'beta')
    assert client.get(path.replace(data['tenant']['id'], other['id'])).status_code == 404
    assert client.post(path, json={'body': 'Registro original', 'client_request_id': str(uuid4())}).status_code == 201
    if storage.postgres:
        principal = {'role': 'company_user', 'id': data['people']['requester']['id'], 'roles': ['requester'], 'all_units': True, 'unit_ids': []}
        with storage.scoped(principal, data['tenant']['id']) as db:
            assert len(db.execute('SELECT * FROM occurrence_messages').fetchall()) == 1
        for sql in ('UPDATE occurrence_messages SET body=\'Alterado\'', 'DELETE FROM occurrence_messages'):
            with pytest.raises(DBAPIError), storage.scoped(principal, data['tenant']['id']) as db:
                db.execute(sql)
        for roles in (['auditor'], ['technician']):
            principal = principal | {'roles': roles, 'id': data['people']['requester' if roles == ['auditor'] else 'tech']['id']}
            with pytest.raises(DBAPIError), storage.scoped(principal, data['tenant']['id']) as db:
                db.execute('''INSERT INTO occurrence_messages(id,company_id,unit_id,occurrence_id,actor_id,actor_name,client_request_id,body,created_at)
                    VALUES(:id,:company,:unit,:occurrence,:actor,'Tentativa',:request,'Texto','2026-10-23')''', {
                    'id': str(uuid4()), 'company': data['tenant']['id'], 'unit': data['unit']['id'],
                    'occurrence': occurrence['id'], 'actor': principal['id'], 'request': str(uuid4())})
    with storage.connect() as db:
        for _ in range(99):
            db.execute('''INSERT INTO occurrence_messages(id,company_id,unit_id,occurrence_id,actor_name,client_request_id,body,created_at)
                VALUES(:id,:company,:unit,:occurrence,'Equipe',:request,'Texto','2026-10-23')''', {
                'id': str(uuid4()), 'company': data['tenant']['id'], 'unit': data['unit']['id'],
                'occurrence': occurrence['id'], 'request': str(uuid4())})
    assert len(client.get(path).json()['items']) == 100
    assert client.post(path, json={'body': 'Limite', 'client_request_id': str(uuid4())}).status_code == 409
