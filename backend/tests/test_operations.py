from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from backend.tests.test_foundation import foundation, company, location, member, accept, login


def seed(client):
    tenant = company(client)
    unit = location(client, tenant['id'])
    base = f"/api/v1/operations/companies/{tenant['id']}"
    result = client.post(base + '/categories', json={'name': 'Climatização'})
    assert result.status_code == 201, result.text
    category = result.json()
    people = {}
    for key, role in [('requester','requester'), ('other','requester'), ('tech','technician')]:
        invited = member(client, tenant['id'], email=key + '@example.com', roles=[role])
        accept(client, invited)
        people[key] = invited['user']
    return {'tenant': tenant, 'unit': unit, 'category': category, 'people': people, 'base': base}


def report(client, data, requester='requester', **changes):
    body = {'title': 'Falha na climatização', 'description': 'O equipamento parou de refrigerar o ambiente.',
            'location_id': data['unit']['id'], 'category_id': data['category']['id'],
            'requester_id': data['people'][requester]['id'], 'client_request_id': str(uuid4())} | changes
    result = client.post(data['base'] + '/occurrences', json=body)
    assert result.status_code == 201, result.text
    return result.json()


def order(client, data, occurrence):
    result = client.post(data['base'] + '/orders', json={'occurrence_id': occurrence['id'], 'expected_occurrence_version': occurrence['version'],
        'title': occurrence['title'], 'description': occurrence['description'], 'impact': 4, 'urgency': 3, 'assignee_id': data['people']['tech']['id']})
    assert result.status_code == 201, result.text
    return result.json()


def detail(client, data, identifier):
    response = client.get(data['base'] + '/orders/' + identifier)
    assert response.status_code == 200, response.text
    return response.json()


def act(client, data, identifier, action, **changes):
    current = detail(client, data, identifier)['order']
    return client.post(data['base'] + '/orders/' + identifier + '/actions', json={'action': action, 'expected_version': current['version']} | changes)


def test_complete_resolution_confirmation_and_closure(foundation):
    client, _ = foundation
    data = seed(client)
    occurrence = report(client, data)
    work = order(client, data, occurrence)
    assert work['priority'] == 'critical'
    login(client, 'tech@example.com')
    assert act(client, data, work['id'], 'start').status_code == 200
    assert act(client, data, work['id'], 'wait', note='Aguardando peça de reposição.').status_code == 200
    assert act(client, data, work['id'], 'start').status_code == 200
    assert act(client, data, work['id'], 'resolve', solution='Peça substituída e refrigeração restabelecida.', evidence='Temperatura medida após trinta minutos de funcionamento.').status_code == 200
    login(client, 'requester@example.com')
    own = client.get(data['base'] + '/occurrences').json()[0]
    assert own['order_state'] == 'resolved'
    assert client.post(data['base'] + '/occurrences/' + own['id'] + '/confirmation', json={'outcome': 'confirmed', 'expected_version': own['version']}).status_code == 200
    login(client, 'admin@example.com')
    assert act(client, data, work['id'], 'close').status_code == 200
    history = detail(client, data, work['id'])
    assert history['order']['state'] == 'closed'
    assert any(item['action'] == 'occurrence.confirmed' for item in history['events'])


def test_duplicate_reports_link_to_one_order_without_exposing_each_other(foundation):
    client, _ = foundation
    data = seed(client)
    one, two = report(client, data), report(client, data, 'other')
    work = order(client, data, one)
    response = client.post(data['base'] + '/orders/' + work['id'] + '/link', json={'occurrence_id': two['id'], 'expected_version': work['version']})
    assert response.status_code == 200, response.text
    assert len(detail(client, data, work['id'])['occurrences']) == 2
    login(client, 'requester@example.com')
    visible = detail(client, data, work['id'])
    assert len(visible['occurrences']) == 1
    assert visible['occurrences'][0]['id'] == one['id']
    assert all(item['requester_id'] != data['people']['other']['id'] for item in client.get(data['base'] + '/occurrences').json())


def test_internal_notes_and_technician_assignment_are_protected(foundation):
    client, _ = foundation
    data = seed(client)
    work = order(client, data, report(client, data))
    path = data['base'] + '/orders/' + work['id']
    assert client.post(path + '/messages', json={'body': 'Diagnóstico interno reservado à equipe.', 'visibility': 'internal'}).status_code == 201
    login(client, 'requester@example.com')
    response = client.get(path)
    assert response.status_code == 200
    assert 'Diagnóstico interno' not in response.text
    assert client.post(path + '/messages', json={'body': 'Tentativa de nota interna', 'visibility': 'internal'}).status_code == 403
    assert act(client, data, work['id'], 'start').status_code == 403
    login(client, 'other@example.com')
    assert client.get(path).status_code == 404
    assert client.get(data['base'] + '/orders').json() == []
    login(client, 'tech@example.com')
    assert 'Diagnóstico interno' in client.get(path).text


def test_contest_reopens_cycle_and_requires_new_confirmations(foundation):
    client, _ = foundation
    data = seed(client)
    first, second = report(client, data), report(client, data, 'other')
    work = order(client, data, first)
    client.post(data['base'] + '/orders/' + work['id'] + '/link', json={'occurrence_id': second['id'], 'expected_version': work['version']})
    login(client, 'tech@example.com')
    assert act(client, data, work['id'], 'start').status_code == 200
    assert act(client, data, work['id'], 'resolve', solution='Intervenção inicial concluída.', evidence='Teste inicial com resultado normal.').status_code == 200
    login(client, 'other@example.com')
    own = client.get(data['base'] + '/occurrences').json()[0]
    assert client.post(data['base'] + '/occurrences/' + own['id'] + '/confirmation', json={'outcome': 'confirmed', 'expected_version': own['version']}).status_code == 200
    login(client, 'requester@example.com')
    own = client.get(data['base'] + '/occurrences').json()[0]
    assert client.post(data['base'] + '/occurrences/' + own['id'] + '/confirmation', json={'outcome': 'contested', 'expected_version': own['version'], 'note': 'O equipamento continua apresentando falhas.'}).status_code == 200
    assert detail(client, data, work['id'])['order']['cycle'] == 2
    login(client, 'tech@example.com')
    assert act(client, data, work['id'], 'resolve', solution='Nova intervenção corrigiu a causa.', evidence='Novo teste realizado durante uma hora.').status_code == 200
    login(client, 'admin@example.com')
    reports = detail(client, data, work['id'])['occurrences']
    assert all(item['outcome'] == 'linked' for item in reports)
    assert act(client, data, work['id'], 'close').status_code == 422
    assert act(client, data, work['id'], 'close', note='Supervisor revisou presencialmente e validou o resultado.').status_code == 200


def test_idempotency_assets_validation_and_foreign_objects(foundation):
    client, _ = foundation
    data = seed(client)
    asset = client.post(data['base'] + '/assets', json={'name': 'Ar-condicionado', 'code': 'AC-01', 'category': 'Climatização', 'criticality': 'high', 'location_id': data['unit']['id']})
    assert asset.status_code == 201, asset.text
    body = {'title': 'Falha no equipamento', 'description': 'Equipamento sem funcionamento normal.', 'location_id': data['unit']['id'],
            'category_id': data['category']['id'], 'asset_id': asset.json()['id'], 'requester_id': data['people']['requester']['id'], 'client_request_id': str(uuid4())}
    first = client.post(data['base'] + '/occurrences', json=body)
    second = client.post(data['base'] + '/occurrences', json=body)
    assert first.status_code == second.status_code == 201
    assert first.json()['id'] == second.json()['id']
    assert client.post(data['base'] + '/occurrences', json=body | {'title': 'Conteúdo diferente para o mesmo envio'}).status_code == 409
    foreign = company(client, 'Empresa Beta', 'beta')
    location_other = location(client, foreign['id'])
    invalid = client.post(data['base'] + '/assets', json={'name': 'Ativo Inválido', 'code': 'X-01', 'category': 'Equipamento', 'criticality': 'high', 'location_id': location_other['id']})
    assert invalid.status_code == 404


def test_stale_versions_invalid_transitions_and_notifications(foundation):
    client, _ = foundation
    data = seed(client)
    work = order(client, data, report(client, data))
    assert act(client, data, work['id'], 'resolve', solution='Texto suficiente de solução', evidence='Texto suficiente de evidência').status_code == 409
    assert act(client, data, work['id'], 'start').status_code == 200
    path = data['base'] + '/orders/' + work['id'] + '/actions'
    assert client.post(path, json={'action': 'wait', 'expected_version': 1, 'note': 'Motivo suficientemente detalhado.'}).status_code == 409
    assert act(client, data, work['id'], 'wait', note='curto').status_code == 422
    login(client, 'requester@example.com')
    notifications = client.get(data['base'] + '/notifications').json()
    assert notifications
    first = notifications[0]
    assert client.post(data['base'] + '/notifications/' + first['id'] + '/read').status_code == 200
    assert client.get(data['base'] + '/notifications').json()[0]['read_at']
    login(client, 'other@example.com')
    assert client.post(data['base'] + '/notifications/' + first['id'] + '/read').status_code == 404


def test_postgres_object_rls_and_internal_messages(foundation):
    client, storage = foundation
    if not storage.postgres:
        pytest.skip('RLS de objetos é verificada no PostgreSQL real.')
    data = seed(client)
    work = order(client, data, report(client, data))
    client.post(data['base'] + '/orders/' + work['id'] + '/messages', json={'body': 'Mensagem interna protegida.', 'visibility': 'internal'})
    principal = {'role': 'company_user', 'id': data['people']['requester']['id'], 'roles': ['requester'], 'all_units': True, 'unit_ids': []}
    with storage.scoped(principal, data['tenant']['id']) as db:
        assert len(db.execute('SELECT * FROM work_orders').fetchall()) == 1
        assert db.execute('SELECT * FROM order_messages').fetchall() == []
    outsider = principal | {'id': data['people']['other']['id']}
    with storage.scoped(outsider, data['tenant']['id']) as db:
        assert db.execute('SELECT * FROM work_orders').fetchall() == []
        assert db.execute('SELECT * FROM occurrences').fetchall() == []
    with storage.tenant.begin() as db:
        assert db.execute(text('SELECT * FROM work_orders')).fetchall() == []
    with storage.scoped(principal, data['tenant']['id']) as db:
        with pytest.raises(DBAPIError):
            db.execute('INSERT INTO order_messages(id,company_id,unit_id,order_id,actor_name,visibility,created_at,body) VALUES(:id,:company,:unit,:order,:name,:visibility,:time,:body)', {
                'id': str(uuid4()), 'company': data['tenant']['id'], 'unit': data['unit']['id'], 'order': work['id'], 'name': 'Intruso', 'visibility': 'internal', 'time': '2026-10-23', 'body': 'Não permitido',
            })
