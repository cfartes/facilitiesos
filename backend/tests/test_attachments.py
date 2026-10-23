from io import BytesIO
from urllib.parse import quote

from fastapi import HTTPException
from PIL import Image, PngImagePlugin
import pytest

from backend import attachments
from backend.tests.test_foundation import foundation, login, member, accept, location, company
from backend.tests.test_operations import seed, report, order, act


def photo(color='blue', format='PNG'):
    output = BytesIO()
    image = Image.new('RGB', (12, 8), color)
    if format == 'PNG':
        info = PngImagePlugin.PngInfo()
        info.add_text('private-note', 'Never retain this metadata')
        image.save(output, format=format, pnginfo=info)
    else:
        exif = Image.Exif()
        exif[270] = 'Never retain this metadata'
        exif[274] = 6
        image.save(output, format=format, exif=exif)
    return output.getvalue()


def upload(client, path, raw=None, filename='foto.png', media='image/png', visibility='shared'):
    return client.post(path + '?visibility=' + visibility, content=photo() if raw is None else raw,
                       headers={'Content-Type': media, 'X-File-Name': quote(filename)})


@pytest.mark.parametrize('format,media,name', [('PNG','image/png','foto.png'), ('JPEG','image/jpeg','foto.jpg')])
def test_image_normalization_removes_metadata_and_corrects_orientation(format, media, name):
    _, clean, fingerprint = attachments.normalize_image(photo(format=format), name, media)
    assert len(fingerprint) == 64
    assert b'Never retain' not in clean
    with Image.open(BytesIO(clean)) as image:
        assert not image.getexif()
        assert 'private-note' not in image.info
        assert image.size == ((8, 12) if format == 'JPEG' else (12, 8))


@pytest.mark.parametrize('raw,name,media,status', [
    (b'<svg><script>alert(1)</script></svg>', 'foto.png', 'image/png', 422),
    (b'%PDF-1.7 test', 'documento.pdf', 'application/pdf', 415),
    (b'bad', '../foto.png', 'image/png', 422),
    (b'bad', 'foto.png', 'image/jpeg', 415),
    (b'bad', 'foto%FF.png', 'image/png', 422),
    (b'bad', 'foto\n.png', 'image/png', 422),
    (b'', 'foto.png', 'image/png', 413),
])
def test_rejects_untrusted_content_and_names(raw, name, media, status):
    with pytest.raises(HTTPException) as error:
        attachments.normalize_image(raw, name, media)
    assert error.value.status_code == status


def test_pixel_and_processing_limits(monkeypatch):
    monkeypatch.setattr(attachments, 'MAX_PIXELS', 50)
    with pytest.raises(HTTPException) as error:
        attachments.normalize_image(photo(), 'foto.png', 'image/png')
    assert error.value.status_code == 422
    assert attachments.processing_slots.acquire(False)
    assert attachments.processing_slots.acquire(False)
    try:
        with pytest.raises(HTTPException) as error:
            attachments.normalize_image(photo(), 'foto.png', 'image/png')
        assert error.value.status_code == 429
    finally:
        attachments.processing_slots.release()
        attachments.processing_slots.release()


def test_appended_content_is_discarded_and_animated_png_is_rejected():
    _, normalized, _ = attachments.normalize_image(photo() + b'<script>not an image</script>', 'foto.png', 'image/png')
    assert b'<script>' not in normalized
    output = BytesIO()
    Image.new('RGB', (10, 10), 'blue').save(output, format='PNG', save_all=True, append_images=[Image.new('RGB', (10, 10), 'red')])
    with pytest.raises(HTTPException) as error:
        attachments.normalize_image(output.getvalue(), 'foto.png', 'image/png')
    assert error.value.status_code == 422


def test_private_upload_download_idempotency_and_authorized_removal(foundation):
    client, storage = foundation
    data = seed(client)
    occurrence = report(client, data)
    path = data['base'] + '/occurrences/' + occurrence['id'] + '/attachments'
    login(client, 'requester@example.com')
    saved = upload(client, path, filename='Evidência do local.png')
    assert saved.status_code == 201, saved.text
    row = saved.json()
    assert row['can_remove']
    duplicate = upload(client, path)
    assert duplicate.status_code == 201
    assert duplicate.json()['id'] == row['id']
    assert len(client.get(path).json()['items']) == 1
    response = client.get(path + '/' + row['id'])
    assert response.status_code == 200, response.text
    assert response.headers['content-type'] == 'image/png'
    assert 'no-store' in response.headers['cache-control']
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert 'attachment;' in response.headers['content-disposition']
    assert b'Never retain' not in response.content
    assert 'ciphertext' not in client.get(path).text
    with storage.connect() as db:
        encrypted = db.execute('SELECT ciphertext FROM attachments WHERE id=:id', {'id': row['id']}).fetchone()['ciphertext']
        assert not encrypted.startswith('\x89PNG')
        assert 'Never retain' not in encrypted
    login(client, 'other@example.com')
    assert client.get(path).status_code == 404
    assert client.get(path + '/' + row['id']).status_code == 404
    assert upload(client, path).status_code == 404
    login(client, 'requester@example.com')
    assert client.request('DELETE', path + '/' + row['id'], json={}).status_code == 204
    assert client.get(path + '/' + row['id']).status_code == 404
    assert client.get(path).json()['items'] == []


def test_order_internal_images_and_original_report_stay_separate(foundation):
    client, storage = foundation
    data = seed(client)
    occurrence = report(client, data)
    work = order(client, data, occurrence)
    path = data['base'] + '/orders/' + work['id'] + '/attachments'
    own_path = data['base'] + '/occurrences/' + occurrence['id'] + '/attachments'
    shared = upload(client, path).json()
    private = upload(client, path, visibility='internal').json()
    original = upload(client, own_path, raw=photo('red')).json()
    assert shared['id'] != private['id']
    login(client, 'requester@example.com')
    assert [item['id'] for item in client.get(path).json()['items']] == [shared['id']]
    assert client.get(path + '/' + private['id']).status_code == 404
    assert upload(client, path, visibility='internal').status_code == 403
    assert upload(client, own_path, visibility='internal').status_code == 403
    assert client.request('DELETE', path + '/' + shared['id'], json={'note': 'Tentativa de remover imagem de outro autor.'}).status_code == 403
    principal = {'role': 'company_user', 'id': data['people']['requester']['id'], 'roles': ['requester'], 'all_units': True, 'unit_ids': []}
    with storage.scoped(principal, data['tenant']['id']) as db:
        if storage.postgres:
            ids = {item['id'] for item in db.execute('SELECT id FROM attachments').fetchall()}
            assert ids == {shared['id'], original['id']}
            assert db.execute('DELETE FROM attachments WHERE id=:id', {'id': shared['id']}).rowcount == 0
    login(client, 'tech@example.com')
    assert client.get(path + '/' + private['id']).status_code == 200
    assert client.get(own_path + '/' + original['id']).status_code == 404
    uploaded = upload(client, path, raw=photo('green'))
    assert uploaded.status_code == 201, uploaded.text
    assert act(client, data, work['id'], 'start').status_code == 200
    assert act(client, data, work['id'], 'resolve', solution='Dreno desobstruído pela equipe.', evidence='Teste de funcionamento sem novo vazamento.').status_code == 200
    login(client, 'admin@example.com')
    assert act(client, data, work['id'], 'close', note='Revisão presencial confirmou a solução apresentada.').status_code == 200
    assert client.get(path).json()['can_upload'] is False
    assert upload(client, path).status_code == 403
    assert client.request('DELETE', path + '/' + shared['id'], json={'note': 'Tentativa de remover após encerramento.'}).status_code == 403
    assert client.get(path + '/' + shared['id']).status_code == 200


def test_cross_company_and_unit_access_auditor_and_limits(foundation, monkeypatch):
    client, _ = foundation
    data = seed(client)
    occurrence = report(client, data)
    path = data['base'] + '/occurrences/' + occurrence['id'] + '/attachments'
    saved = upload(client, path).json()
    tenant = company(client, 'Outra empresa', 'outra')
    foreign_path = path.replace(data['tenant']['id'], tenant['id'])
    assert client.get(foreign_path + '/' + saved['id']).status_code == 404
    auditor = member(client, data['tenant']['id'], email='audit@example.com', roles=['auditor'])
    accept(client, auditor)
    login(client, 'audit@example.com')
    assert client.get(path).status_code == 200
    assert upload(client, path).status_code == 403
    assert client.request('DELETE', path + '/' + saved['id'], json={'note': 'Auditor não pode remover imagens.'}).status_code == 403
    login(client, 'admin@example.com')
    other_unit = location(client, data['tenant']['id'], 'Unidade Restrita')
    restricted = member(client, data['tenant']['id'], email='restricted-photo@example.com', roles=['manager'], all_units=False, unit_ids=[other_unit['id']])
    accept(client, restricted)
    login(client, 'restricted-photo@example.com')
    assert client.get(path).status_code == 404
    assert client.get(path + '/' + saved['id']).status_code == 404
    login(client, 'admin@example.com')
    # As cotas são consultadas no momento do registro, inclusive sobre imagens internas.
    monkeypatch.setattr(attachments, 'MAX_PER_RECORD', 1)
    assert upload(client, path, raw=photo('yellow')).status_code == 409
    monkeypatch.setattr(attachments, 'MAX_PER_RECORD', 10)
    monkeypatch.setattr(attachments, 'MAX_COMPANY_BYTES', 1)
    assert upload(client, path, raw=photo('yellow')).status_code == 409
    monkeypatch.setattr(attachments, 'MAX_COMPANY_BYTES', 200 * 1024 * 1024)
    original_slots = attachments.processing_slots
    assert original_slots.acquire(False)
    assert original_slots.acquire(False)
    try:
        assert upload(client, path, raw=photo('yellow')).status_code == 429
    finally:
        original_slots.release()
        original_slots.release()
    oversized = b'x' * (attachments.MAX_BYTES + 1)
    assert upload(client, path, raw=oversized).status_code == 413
    client.headers.pop('X-CSRF-Token')
    assert upload(client, path).status_code == 403
