from io import BytesIO
import base64
from uuid import uuid4

from PIL import Image
from fastapi import HTTPException

from backend import providers
from backend.tests.test_foundation import foundation, login, company, location
from backend.tests.test_asset_labels import asset
from backend.tests.test_whatsapp_intake import prepare, say, message


def photo_event(client, data, **changes):
    event = {'id': str(uuid4()), 'from': '5511999999999@c.us', 'fromMe': False, 'isGroup': False, 'body': '', 'type': 'image'} | changes
    return message(client, data, '', changes={'data': event})


def picture(color='red'):
    output = BytesIO()
    image = Image.new('RGB', (30, 20), color)
    exif = image.getexif(); exif[270] = 'metadata-must-disappear'
    image.save(output, 'JPEG', exif=exif)
    return output.getvalue(), 'image/jpeg'


def qr_start(client, storage, data):
    item = asset(client, data)
    assert 'nome completo' in say(client, storage, data, 'EQUIPAMENTO ' + item['id'])
    reply = say(client, storage, data, 'Pessoa do WhatsApp')
    assert 'Equipamento identificado: AC-001' in reply and 'Descreva o problema' in reply
    assert 'Deseja enviar fotos' in say(client, storage, data, 'O ar-condicionado está pingando água na sala.')
    return item


def latest(storage, data):
    with storage.connect() as db:
        return data['service'].decode(db.execute('SELECT payload FROM whatsapp_outbox ORDER BY created_at DESC,id DESC LIMIT 1').fetchone()['payload'])['text']


def test_qr_photos_confirm_private_attachments_and_replay(foundation, monkeypatch):
    client, storage = foundation
    data = prepare(client, storage, monkeypatch)
    item = qr_start(client, storage, data)
    calls = []
    def download(key, session, chat, message_id):
        calls.append((session, chat, message_id))
        return picture()
    monkeypatch.setattr(providers, 'openwa_image', download)
    response, raw, signature = photo_event(client, data, body='CANCELAR')
    assert response.status_code == 202 and 'Foto recebida (1/3)' in latest(storage, data)
    assert len(calls) == 1
    with storage.connect() as db:
        assert not db.execute("SELECT id FROM whatsapp_outbox WHERE status='cancelled'").fetchall()
    assert client.post('/api/v1/webhooks/openwa/' + data['tenant']['id'], content=raw, headers={'Origin': '', 'X-Openwa-Signature': signature}).status_code == 202
    assert len(calls) == 1
    assert photo_event(client, data)[0].status_code == 202
    assert 'já foi recebida' in latest(storage, data)
    with storage.connect() as db:
        draft = db.execute('SELECT draft FROM whatsapp_conversations').fetchone()['draft']
        assert 'metadata-must-disappear' not in draft and 'data' not in draft
        assert db.execute('SELECT count(*) AS n FROM attachments').fetchone()['n'] == 0
    assert 'Fotos: 1' in say(client, storage, data, '0')
    assert 'Solicitação registrada! Protocolo:' in say(client, storage, data, '1')
    with storage.connect() as db:
        occurrence = db.execute('SELECT * FROM occurrences').fetchone()
        assert occurrence['asset_id'] == item['id']
        row = db.execute('SELECT * FROM attachments').fetchone()
        assert row['uploader_id'] is None and row['uploader_name'] == 'Pessoa do WhatsApp'
        decoded = data['service'].cipher.decrypt(row['ciphertext'].encode())
        with Image.open(BytesIO(decoded)) as image:
            assert not image.getexif()
        assert data['service'].decode(db.execute('SELECT draft FROM whatsapp_conversations').fetchone()['draft']) == {'stage': 'idle'}
    path = data['base'] + '/occurrences/' + occurrence['id'] + '/attachments'
    assert len(client.get(path).json()['items']) == 1
    assert client.get(path + '/' + row['id']).content == decoded
    assert 'Equipamento identificado' in say(client, storage, data, 'EQUIPAMENTO ' + item['id'])
    say(client, storage, data, 'CANCELAR')
    login(client, 'requester@example.com')
    assert client.get(path).status_code == 404
    login(client, 'tech@example.com')
    assert client.get(path + '/' + row['id']).status_code == 404


def test_no_download_for_unauthorized_or_outside_photo_stage_and_cancel_race(foundation, monkeypatch):
    client, storage = foundation
    data = prepare(client, storage, monkeypatch)
    calls = []
    monkeypatch.setattr(providers, 'openwa_image', lambda *args: calls.append(args) or picture())
    assert photo_event(client, data)[0].status_code == 202
    assert calls == []
    qr_start(client, storage, data)
    event = {'id': str(uuid4()), 'from': '5511999999999@c.us', 'fromMe': False, 'isGroup': False, 'type': 'image'}
    assert message(client, data, '', changes={'data': event}, signature=False)[0].status_code == 403
    assert message(client, data, '', changes={'data': event, 'sessionId': str(uuid4())})[0].status_code == 202
    assert calls == []
    def cancel_during_download(*args):
        say(client, storage, data, 'CANCELAR')
        return picture()
    monkeypatch.setattr(providers, 'openwa_image', cancel_during_download)
    assert photo_event(client, data)[0].status_code == 202
    with storage.connect() as db:
        draft = data['service'].decode(db.execute('SELECT draft FROM whatsapp_conversations').fetchone()['draft'])
        assert draft == {'stage': 'idle'}
        assert not db.execute('SELECT * FROM attachments').fetchall()


def test_photo_format_limit_removal_and_company_quota(foundation, monkeypatch):
    client, storage = foundation
    data = prepare(client, storage, monkeypatch)
    qr_start(client, storage, data)
    monkeypatch.setattr(providers, 'openwa_image', lambda *args: (b'not-an-image', 'image/jpeg'))
    assert photo_event(client, data)[0].status_code == 202
    assert 'Imagem inválida' in latest(storage, data)
    monkeypatch.setattr(providers, 'openwa_image', lambda *args: (b'<svg/>', 'image/svg+xml'))
    photo_event(client, data)
    assert 'somente fotos JPEG ou PNG' in latest(storage, data)
    for index, color in enumerate(('red', 'blue', 'green', 'yellow')):
        monkeypatch.setattr(providers, 'openwa_image', lambda *args, color=color: picture(color))
        assert photo_event(client, data)[0].status_code == 202
        assert (f'({index + 1}/3)' if index < 3 else 'Limite de 3 fotos') in latest(storage, data)
    assert 'Fotos descartadas' in say(client, storage, data, 'REMOVER FOTOS')
    import backend.whatsapp_dialogue as dialogue
    monkeypatch.setattr(dialogue, 'MAX_COMPANY_BYTES', 1)
    photo_event(client, data)
    assert 'cota de imagens' in latest(storage, data)
    assert 'Fotos: 0' in say(client, storage, data, '0')
    say(client, storage, data, '1')
    with storage.connect() as db:
        assert not db.execute('SELECT * FROM attachments').fetchall()


def test_qr_cannot_select_another_company_or_retired_asset(foundation, monkeypatch):
    client, storage = foundation
    data = prepare(client, storage, monkeypatch)
    say(client, storage, data, 'Oi'); say(client, storage, data, 'Pessoa Externa')
    assert 'não encontrado' in say(client, storage, data, 'EQUIPAMENTO ' + str(uuid4()))
    other = company(client, 'Empresa Beta', 'beta')
    login(client, 'ownerbeta@example.com')
    unit = location(client, other['id'])
    foreign = asset(client, {'base': '/api/v1/operations/companies/' + other['id'], 'unit': unit})
    login(client, 'owneralpha@example.com')
    assert 'não encontrado' in say(client, storage, data, 'EQUIPAMENTO ' + foreign['id'])
    item = asset(client, data)
    with storage.connect() as db:
        db.execute("UPDATE assets SET status='retired' WHERE id=:id", {'id': item['id']})
    assert 'não encontrado' in say(client, storage, data, 'EQUIPAMENTO ' + item['id'])
    assert 'Selecione a unidade' in say(client, storage, data, '0')


def test_media_download_uses_fixed_provider_url_no_redirect_and_size_limit(monkeypatch):
    from email.message import Message
    from backend import attachments
    calls = []
    class Response(BytesIO):
        headers = Message()
        headers['Content-Type'] = 'image/jpeg'
    class Opener:
        def open(self, request, timeout):
            calls.append(request.full_url)
            assert request.get_header('X-api-key') == 'test-key'
            assert timeout == 15
            return Response(b'12345678901')
    def opener(handler):
        assert isinstance(handler, providers.NoRedirect)
        return Opener()
    monkeypatch.setattr(providers, 'build_opener', opener)
    monkeypatch.setattr(attachments, 'MAX_BYTES', 10)
    import pytest
    with pytest.raises(HTTPException) as error:
        providers.openwa_image('test-key', 'session', '5511999999999@c.us', '../../message?x')
    assert error.value.status_code == 413
    assert calls == [providers.OPENWA_BASE + '/sessions/session/messages/5511999999999%40c.us/..%2F..%2Fmessage%3Fx/media']


def test_signed_inline_photo_over_old_body_limit_needs_no_download(foundation, monkeypatch):
    client, storage = foundation
    data = prepare(client, storage, monkeypatch)
    qr_start(client, storage, data)
    output = BytesIO()
    Image.effect_noise((320, 240), 90).convert('RGB').save(output, 'JPEG', quality=95)
    raw = output.getvalue()
    assert len(raw) > 24000
    monkeypatch.setattr(providers, 'openwa_image', lambda *args: (_ for _ in ()).throw(AssertionError('Inline validado não precisa de download.')))
    response, event, signature = photo_event(client, data, media={'mimetype': 'image/jpeg', 'data': base64.b64encode(raw).decode()})
    assert response.status_code == 202, response.text
    assert 'Foto recebida (1/3)' in latest(storage, data)
    assert client.post('/api/v1/webhooks/openwa/' + data['tenant']['id'], content=event, headers={'Origin': '', 'X-Openwa-Signature': 'invalid'}).status_code == 403
    assert photo_event(client, data, media={'mimetype': 'image/jpeg', 'data': 'https://example.com/photo.jpg'})[0].status_code == 202
    assert 'codificação inválida' in latest(storage, data)


def test_missing_stored_media_is_reported_as_provider_configuration(monkeypatch):
    from urllib.error import HTTPError
    import pytest
    class Opener:
        def open(self, request, timeout):
            raise HTTPError(request.full_url, 404, 'Not found', {}, BytesIO(b'{"message":"No media stored for this message"}'))
    monkeypatch.setattr(providers, 'build_opener', lambda *args: Opener())
    with pytest.raises(HTTPException) as error:
        providers.openwa_image('test', 'session', '5511999999999@c.us', 'message')
    assert 'não disponibilizou o arquivo' in error.value.detail
    assert 'download de mídia' in error.value.detail


def test_media_diagnostic_does_not_expose_other_environment_settings():
    from scripts.check_openwa_media import media_settings
    result = media_settings(['MEDIA_DOWNLOAD_ENABLED=false', 'MEDIA_DOWNLOAD_MAX_BYTES=1024', 'API_KEY=secret-not-for-output', 'DATABASE_URL=private'])
    assert result['MEDIA_DOWNLOAD_ENABLED'] == 'false'
    assert result['MEDIA_DOWNLOAD_MAX_BYTES'] == '1024'
    assert 'secret-not-for-output' not in str(result) and 'DATABASE_URL' not in result


def test_media_diagnostic_reports_logging_and_compose_without_secrets(monkeypatch, capsys):
    import json
    from scripts import check_openwa_media as check
    def command(args, **kwargs):
        assert kwargs['timeout'] == 10
        if args[1] == 'ps':
            return 'openwa-api\n'
        return json.dumps([{'Name': '/openwa-api', 'Config': {'Image': 'rmyndharis/openwa:latest',
            'Env': ['API_KEY=private-value'], 'Labels': {'com.docker.compose.project.config_files': '/opt/openwa/compose.yaml',
                'com.docker.compose.service': 'api'}}, 'HostConfig': {'LogConfig': {'Type': 'none'}}}])
    monkeypatch.setattr(check.subprocess, 'check_output', command)
    monkeypatch.setattr(check.sys, 'argv', ['check_openwa_media.py', 'openwa-api'])
    check.main()
    output = capsys.readouterr().out
    assert 'Driver de logs: none' in output
    assert '/opt/openwa/compose.yaml' in output
    assert 'private-value' not in output and 'API_KEY' not in output


def test_media_log_tail_is_bounded_and_masks_urls_and_identifiers(tmp_path):
    import json
    from scripts.check_openwa_media import media_errors
    path = tmp_path / 'container-json.log'
    path.write_text('x' * 300000 + '\n' + '\n'.join(json.dumps({'log': line}) for line in [
        'ordinary message without media',
        'Inbound media download failed; error: NetworkError https://example.com/private?token=secret 5511999999999',
        'media error ' + 'A' * 100,
    ]))
    errors = media_errors(path)
    assert len(errors) == 2 and 'NetworkError' in errors[0]
    assert 'secret' not in str(errors) and '5511999999999' not in str(errors)
    assert 'A' * 100 not in str(errors)


def test_media_log_does_not_expose_short_credentials_in_error_text(tmp_path):
    import json
    from scripts.check_openwa_media import media_errors
    path = tmp_path / 'container-json.log'
    path.write_text(json.dumps({'log': 'media download failed: X-API-Key=abc123 password="short-pass" Authorization: Bearer sensitive-value token=short-token'}))
    result = str(media_errors(path))
    for secret in ('abc123', 'short-pass', 'sensitive-value', 'short-token'):
        assert secret not in result


def test_raw_qr_link_starts_without_menu_for_new_and_known_contact(foundation, monkeypatch):
    from urllib.parse import urlencode
    client, storage = foundation
    data = prepare(client, storage, monkeypatch)
    item = asset(client, data)
    link = 'https://wa.me/5511999999999?' + urlencode({'text': 'EQUIPAMENTO ' + item['id']})
    assert 'nome completo' in say(client, storage, data, link)
    reply = say(client, storage, data, 'Contato Direto')
    assert 'Equipamento identificado' in reply and 'Descreva o problema' in reply
    assert 'Selecione a unidade' not in reply
    say(client, storage, data, 'O equipamento está com vazamento de água.')
    say(client, storage, data, '0')
    assert 'Solicitação registrada' in say(client, storage, data, '1')
    assert 'Descreva o problema' in say(client, storage, data, link)


def test_qr_switch_preserves_draft_until_explicit_choice(foundation, monkeypatch):
    from urllib.parse import urlencode
    client, storage = foundation
    data = prepare(client, storage, monkeypatch)
    qr_start(client, storage, data)
    other = asset(client, data, code='AC-002', name='Outro equipamento')
    monkeypatch.setattr(providers, 'openwa_image', lambda *args: picture())
    photo_event(client, data)
    link = 'https://wa.me/5511999999999?' + urlencode({'text': 'EQUIPAMENTO ' + other['id']})
    assert 'Retomar a solicitação anterior' in say(client, storage, data, link)
    with storage.connect() as db:
        draft = data['service'].decode(db.execute('SELECT draft FROM whatsapp_conversations').fetchone()['draft'])
        assert len(draft['photos']) == 1 and draft['description']
    assert 'Deseja enviar fotos' in say(client, storage, data, '1')
    say(client, storage, data, link)
    assert 'Outro equipamento' in say(client, storage, data, '2')
    with storage.connect() as db:
        draft = data['service'].decode(db.execute('SELECT draft FROM whatsapp_conversations').fetchone()['draft'])
        assert draft['asset']['id'] == other['id'] and not draft.get('photos')
        assert not db.execute('SELECT * FROM occurrences').fetchall()


def test_qr_parser_accepts_only_generated_links_and_equipment_identifiers():
    from backend.asset_labels import qr_identifier
    identifier = str(uuid4())
    assert qr_identifier('EQUIPAMENTO ' + identifier) == identifier
    assert qr_identifier(identifier) == identifier
    assert qr_identifier('https://wa.me/5511999999999?text=EQUIPAMENTO%20' + identifier) == identifier
    assert qr_identifier('https://evil.example/?text=EQUIPAMENTO%20' + identifier) is None
    assert qr_identifier('https://wa.me/5511999999999?text=' + identifier + '&text=' + identifier) is None
