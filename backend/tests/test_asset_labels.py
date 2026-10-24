import base64
from io import BytesIO
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from PIL import Image

from backend.tests.test_foundation import foundation, login, company, location
from backend.tests.test_operations import seed


def asset(client, data, **changes):
    response = client.post(data['base'] + '/assets', json={'location_id': data['unit']['id'], 'code': 'AC-001', 'name': 'Ar da recepção', 'category': 'Climatização', 'criticality': 'high'} | changes)
    assert response.status_code == 201, response.text
    return response.json()


def test_labels_are_scoped_and_have_whatsapp_handoff(foundation):
    client, storage = foundation
    data = seed(client)
    item = asset(client, data)
    path = data['base'] + '/assets/labels'
    body = {'asset_ids': [item['id'], item['id']], 'phone': '5511999999999'}
    response = client.post(path, json=body)
    assert response.status_code == 200, response.text
    labels = response.json()['items']
    assert len(labels) == 1
    label = labels[0]
    assert label['code'] == 'AC-001'
    assert label['location'] == data['unit']['name']
    parsed = urlsplit(label['url'])
    assert parsed.netloc == 'wa.me' and parsed.path == '/5511999999999'
    assert parse_qs(parsed.query)['text'] == ['EQUIPAMENTO ' + item['id']]
    with Image.open(BytesIO(base64.b64decode(label['qr_code'].split(',')[1]))) as image:
        assert image.format == 'PNG' and image.width == image.height and image.width > 100
    assert client.post(path, json=body | {'phone': 'https://evil.example'}).status_code == 422
    assert client.post(path, json=body | {'asset_ids': [str(uuid4())]}).status_code == 404
    login(client, 'requester@example.com')
    assert client.post(path, json=body).status_code == 403
    login(client, 'admin@example.com')
    assert client.post(path, json=body).status_code == 403
    other = company(client, 'Outra empresa', 'beta')
    login(client, 'ownerbeta@example.com')
    assert client.post(path, json=body).status_code == 404
    login(client, 'owneralpha@example.com')
    with storage.connect() as db:
        db.execute("UPDATE assets SET status='retired' WHERE id=:id", {'id': item['id']})
    assert client.post(path, json=body).status_code == 404


def test_label_rejects_inactive_parent_and_unit_outside_access(foundation):
    from backend.tests.test_foundation import member, accept
    client, storage = foundation
    data = seed(client)
    building = location(client, data['tenant']['id'], 'Prédio', 'building', data['unit']['id'])
    item = asset(client, data, location_id=building['id'])
    body = {'asset_ids': [item['id']], 'phone': '5511999999999'}
    with storage.connect() as db:
        db.execute('UPDATE locations SET is_active=0 WHERE id=:id', {'id': data['unit']['id']})
    assert client.post(data['base'] + '/assets/labels', json=body).status_code == 404
    with storage.connect() as db:
        db.execute('UPDATE locations SET is_active=1 WHERE id=:id', {'id': data['unit']['id']})
    second = location(client, data['tenant']['id'], 'Filial')
    person = member(client, data['tenant']['id'], email='restricted@example.com', roles=['supervisor'], all_units=False, unit_ids=[second['id']])
    accept(client, person)
    login(client, 'restricted@example.com')
    assert client.post(data['base'] + '/assets/labels', json=body).status_code == 404
