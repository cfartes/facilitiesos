"""Diálogo determinístico; só a confirmação gera uma ocorrência."""
import json
import base64
from uuid import uuid4

from backend.foundation import now, record_audit
from backend.security import digest
from backend.asset_labels import equipment, qr_identifier
from backend.attachments import MAX_COMPANY_BYTES

INTRO = 'Olá! Este canal registra solicitações de manutenção. Usaremos seu nome, telefone e relato para atender sua solicitação. Não envie senhas ou dados sensíveis. Em emergências, utilize o canal de emergência da unidade.\nQual é seu nome completo?'
HELP = '\nDigite VOLTAR para corrigir, CANCELAR para descartar ou MENU para recomeçar.'
QR_PROMPT = 'Você tem a etiqueta QR Code do equipamento? Leia com a câmera do celular e envie a mensagem preenchida no WhatsApp, ou copie aqui EQUIPAMENTO seguido do identificador da etiqueta.\n0 — Pular QR Code e informar unidade/local' + HELP
PHOTO_PROMPT = 'Deseja enviar fotos do problema? Use o clipe ou a câmera do WhatsApp e envie até 3 fotos JPEG/PNG, uma por mensagem (até 5 MiB e 16 megapixels cada). Não envie dados sensíveis.\n0 — Concluir fotos / seguir sem fotos\nREMOVER FOTOS — Descartar as fotos desta solicitação' + HELP


def summary(draft):
    draft['stage'] = 'confirm'
    location = draft.get('place_text') or draft['place']['label']
    asset = draft.get('asset')
    heading = f'Revise sua solicitação:\nNome: {draft["name"]}\nUnidade: {draft["unit"]["label"]}\nLocal: {location[:250]}\nEquipamento: {asset["label"] if asset else "Não identificado"}'
    return heading[:750] + f'\nProblema: {draft["description"]}\nFotos: {len(draft.get("photos", []))}\n\n1 — Confirmar\n2 — Corrigir descrição\n3 — Cancelar' + HELP


def identify(db, company, draft, identifier):
    selected = equipment(db, company, identifier)
    if not selected:
        draft['stage'] = 'equipment'
        return 'Equipamento não encontrado ou indisponível nesta empresa. Confira a etiqueta ou informe o local manualmente.\n' + QR_PROMPT
    draft.update({key: selected[key] for key in ('unit', 'place', 'asset')})
    draft.pop('place_text', None)
    return 'Equipamento identificado: ' + selected['asset']['label'] + '\nLocal: ' + selected['place']['label'] + '\n' + advance(db, company, draft, 'description')


def begin(db, company, draft):
    identifier = draft.pop('pending_equipment', None)
    if identifier:
        return identify(db, company, draft, identifier)
    draft['stage'] = 'equipment'
    return QR_PROMPT


def menu(draft):
    labels = {'unit': 'Selecione a unidade:', 'place': 'Selecione o local:', 'asset': 'Selecione o equipamento:'}
    offset = draft.get('offset', 0)
    choices = draft['choices'][offset:offset + 8]
    lines = [labels[draft['stage']]] + [f'{i + 1} — {item["label"][:300]}' for i, item in enumerate(choices)]
    if draft['stage'] == 'place':
        lines.append('0 — Informar outro local nesta unidade')
    if draft['stage'] == 'asset':
        lines.append('0 — Não identificado / sem equipamento')
    if offset + 8 < len(draft['choices']):
        lines.append('MAIS — Próximas opções')
    if offset:
        lines.append('ANTERIOR — Opções anteriores')
    return '\n'.join(lines) + HELP


def advance(db, company, draft, stage):
    draft['stage'] = stage
    draft['offset'] = 0
    if stage in ('unit', 'place', 'asset'):
        draft.pop('photos', None)
    if stage == 'unit':
        rows = db.execute("SELECT id,name FROM locations WHERE company_id=:company AND kind='unit' AND is_active=1 ORDER BY name,id LIMIT 5000", {'company': company}).fetchall()
    elif stage == 'place':
        rows = db.execute('SELECT id,name,parent_id FROM locations WHERE company_id=:company AND unit_id=:unit AND is_active=1 ORDER BY name,id LIMIT 5000', {'company': company, 'unit': draft['unit']['id']}).fetchall()
        by_id = {item['id']: item for item in rows}
        def path(item):
            names, visited = [item['name']], {item['id']}
            while item['parent_id'] in by_id and item['parent_id'] not in visited:
                item = by_id[item['parent_id']]
                visited.add(item['id']); names.insert(0, item['name'])
            return ' / '.join(names)
        draft['choices'] = [{'id': item['id'], 'label': path(item)} for item in rows]
        return menu(draft)
    elif stage == 'asset':
        rows = db.execute("SELECT id,code || ' — ' || name AS name FROM assets WHERE company_id=:company AND location_id=:place AND status<>'retired' ORDER BY code,id LIMIT 1000", {'company': company, 'place': draft['place']['id']}).fetchall()
    else:
        draft.pop('choices', None)
        return 'Descreva o problema e o que você observou (10 a 3.000 caracteres). Se o equipamento não foi identificado, inclua seu nome/código, se souber. Depois você poderá enviar fotos.' + HELP
    draft['choices'] = [{'id': item['id'], 'label': item['name']} for item in rows]
    if not rows and stage == 'unit':
        return 'Não há unidades disponíveis para receber solicitações. Contate o administrador da empresa e tente novamente mais tarde.'
    return menu(draft)


def handle(db, cipher, company, phone_hash, chat, draft, text, category, photo=None):
    contact = db.execute('SELECT id,name FROM whatsapp_contacts WHERE company_id=:company AND phone_hash=:phone', {'company': company, 'phone': phone_hash}).fetchone()
    command = text.strip().casefold()
    if command == 'cancelar':
        draft.clear(); draft['stage'] = 'idle'
        return 'Solicitação cancelada. Nenhum novo protocolo foi criado. Digite MENU para começar novamente.'
    if command == 'menu' or draft.get('stage') == 'idle':
        draft.clear()
    qr = qr_identifier(text)
    switch_prompt = 'Há uma solicitação em andamento.\n1 — Retomar a solicitação anterior\n2 — Descartar o rascunho anterior e iniciar pelo QR Code recebido' + HELP
    if qr and draft.get('stage') in ('description', 'photos', 'confirm', 'switch_equipment'):
        if not equipment(db, company, qr):
            return 'Equipamento não encontrado ou indisponível nesta empresa. Seu rascunho anterior foi preservado.' + HELP
        draft.setdefault('resume_stage', draft['stage'])
        draft['stage'] = 'switch_equipment'
        draft['pending_equipment'] = qr
        return switch_prompt
    if qr:
        draft['pending_equipment'] = qr
    if not draft or set(draft) == {'pending_equipment'}:
        if not contact:
            draft['stage'] = 'name'
            return INTRO
        draft['contact'] = contact['id']; draft['name'] = contact['name']
        return f'Olá, {contact["name"]}! Vamos registrar uma nova solicitação.\n' + begin(db, company, draft)
    stage = draft['stage']
    if stage == 'switch_equipment':
        if command in ('1', 'voltar'):
            draft['stage'] = draft.pop('resume_stage')
            draft.pop('pending_equipment', None)
            return summary(draft) if draft['stage'] == 'confirm' else PHOTO_PROMPT if draft['stage'] == 'photos' else advance(db, company, draft, 'description')
        if command == '2':
            identifier = draft['pending_equipment']
            draft.clear()
            if not contact:
                draft.update(stage='name', pending_equipment=identifier)
                return INTRO
            draft.update(contact=contact['id'], name=contact['name'])
            return identify(db, company, draft, identifier)
        return switch_prompt
    if qr:
        if stage == 'name':
            return INTRO
        return identify(db, company, draft, draft.pop('pending_equipment'))
    if stage == 'equipment':
        if command in ('0', 'pular'):
            return advance(db, company, draft, 'unit')
        return QR_PROMPT
    if command == 'voltar':
        target = {'unit': 'equipment', 'place': 'unit', 'place_text': 'place', 'asset': 'place', 'description': 'asset', 'photos': 'description', 'confirm': 'description'}.get(stage)
        if target == 'equipment':
            draft['stage'] = 'equipment'
            return QR_PROMPT
        if not target:
            return 'Informe seu nome completo para continuar, ou CANCELAR.' if stage == 'name' else advance(db, company, draft, 'unit')
        if target == 'unit':
            for key in ('unit', 'place', 'asset', 'place_text', 'description'):
                draft.pop(key, None)
        elif target == 'place':
            for key in ('place', 'asset', 'place_text', 'description'):
                draft.pop(key, None)
        elif target == 'asset':
            draft.pop('asset', None); draft.pop('description', None)
        return advance(db, company, draft, target)
    if stage == 'name':
        name = ' '.join(text.split())
        if not 3 <= len(name) <= 160 or not any(character.isalpha() for character in name):
            return 'Informe seu nome (3 a 160 caracteres), ou CANCELAR.'
        identifier = str(uuid4())
        db.execute('INSERT INTO whatsapp_contacts(id,company_id,phone_hash,phone,name,created_at) VALUES(:id,:company,:hash,:phone,:name,:time)', {
            'id': identifier, 'company': company, 'hash': phone_hash, 'phone': cipher.encrypt(chat.encode()).decode(), 'name': name, 'time': now()})
        draft['contact'] = identifier; draft['name'] = name
        return begin(db, company, draft)
    if stage in ('unit', 'place', 'asset'):
        if command in ('mais', 'anterior'):
            draft['offset'] = max(0, min(max(0, ((len(draft['choices']) - 1) // 8) * 8), draft.get('offset', 0) + (8 if command == 'mais' else -8)))
            return menu(draft)
        if command == '0' and stage == 'place':
            draft['place'] = draft['unit']; draft['stage'] = 'place_text'
            return 'Informe o local dentro da unidade (3 a 200 caracteres).' + HELP
        if command == '0' and stage == 'asset':
            draft['asset'] = None
            return advance(db, company, draft, 'description')
        options = draft['choices'][draft.get('offset', 0):draft.get('offset', 0) + 8]
        if not command.isascii() or not command.isdigit() or not 1 <= int(command) <= len(options):
            return 'Escolha uma opção válida.\n' + menu(draft)
        selected = options[int(command) - 1]
        draft[stage] = selected
        if stage == 'unit':
            return advance(db, company, draft, 'place')
        if stage == 'place':
            draft.pop('place_text', None)
            return advance(db, company, draft, 'asset')
        return advance(db, company, draft, 'description')
    if stage == 'place_text':
        if not 3 <= len(text) <= 200:
            return 'Informe o local em 3 a 200 caracteres.' + HELP
        draft['place_text'] = text
        return advance(db, company, draft, 'asset')
    if stage == 'description':
        if not 10 <= len(text) <= 3000:
            return 'Descreva o problema em 10 a 3.000 caracteres.' + HELP
        draft['description'] = text; draft['stage'] = 'photos'
        return PHOTO_PROMPT
    if stage == 'photos':
        photos = draft.setdefault('photos', [])
        if command == 'remover fotos':
            photos.clear()
            return 'Fotos descartadas.\n' + PHOTO_PROMPT
        if photo:
            if any(item['sha256'] == photo['sha256'] for item in photos):
                return 'Esta foto já foi recebida. Envie outra ou digite 0 para concluir.' + HELP
            if len(photos) >= 3:
                return 'Limite de 3 fotos atingido. Digite 0 para revisar ou REMOVER FOTOS para substituí-las.' + HELP
            used = db.execute('SELECT COALESCE(sum(byte_size),0) AS n FROM attachments WHERE company_id=:company', {'company': company}).fetchone()['n']
            pending = db.execute('SELECT COALESCE(sum(length(draft)),0) AS n FROM whatsapp_conversations WHERE company_id=:company', {'company': company}).fetchone()['n']
            if used + pending + photo['byte_size'] * 2 > MAX_COMPANY_BYTES:
                return 'A empresa atingiu a cota de imagens. Digite 0 para seguir ou REMOVER FOTOS para descartá-las.' + HELP
            photos.append(photo)
            return f'Foto recebida ({len(photos)}/3). Envie outra ou digite 0 para revisar sua solicitação.' + HELP
        if command in ('0', 'pular', 'concluir'):
            return summary(draft)
        return PHOTO_PROMPT
    if stage == 'confirm':
        if command == '2':
            return advance(db, company, draft, 'description')
        if command == '3':
            draft.clear(); draft['stage'] = 'idle'
            return 'Solicitação cancelada. Nenhum novo protocolo foi criado.'
        if command != '1':
            return 'Digite 1 para confirmar, 2 para corrigir ou 3 para cancelar.' + HELP
        valid = db.execute('''SELECT l.id FROM locations l JOIN locations u ON u.id=l.unit_id AND u.company_id=l.company_id
            WHERE l.company_id=:company AND l.id=:place AND l.unit_id=:unit AND l.is_active=1 AND u.is_active=1''',
            {'company': company, 'place': draft['place']['id'], 'unit': draft['unit']['id']}).fetchone()
        asset = draft.get('asset')
        if not valid or (asset and (not equipment(db, company, asset['id']) or not db.execute("SELECT id FROM assets WHERE company_id=:company AND id=:id AND location_id=:place AND status<>'retired'", {'company': company, 'id': asset['id'], 'place': draft['place']['id']}).fetchone())):
            return 'O cadastro do local/equipamento mudou. Selecione novamente.\n' + advance(db, company, draft, 'unit')
        identifier = str(uuid4()); code = 'OC-' + uuid4().hex[:10].upper()
        photos = draft.get('photos', [])
        used = db.execute('SELECT COALESCE(sum(byte_size),0) AS n FROM attachments WHERE company_id=:company', {'company': company}).fetchone()['n']
        if used + sum(item['byte_size'] for item in photos) > MAX_COMPANY_BYTES:
            draft['stage'] = 'photos'
            return 'A empresa atingiu a cota de imagens. Digite REMOVER FOTOS e depois 0 para registrar sem anexos.' + HELP
        description = draft['description']
        if draft.get('place_text'):
            description = 'Local informado: ' + draft['place_text'] + '\n' + description
        db.execute('''INSERT INTO occurrences(id,company_id,unit_id,location_id,category_id,asset_id,requester_contact_id,client_request_id,request_hash,code,title,description,created_at)
            VALUES(:id,:company,:unit,:place,:category,:asset,:contact,:request,:hash,:code,:title,:description,:time)''', {
            'id': identifier, 'company': company, 'unit': draft['unit']['id'], 'place': draft['place']['id'], 'category': category,
            'asset': asset['id'] if asset else None, 'contact': draft['contact'], 'request': str(uuid4()), 'hash': digest(json.dumps(draft, sort_keys=True)),
            'code': code, 'title': draft['description'].replace('\n', ' ')[:180], 'description': description, 'time': now()})
        record_audit(db, {'email': 'system:whatsapp'}, 'occurrence.created', company, identifier, draft['unit']['id'])
        for index, photo in enumerate(photos):
            attachment_id = str(uuid4())
            db.execute('''INSERT INTO attachments(id,company_id,unit_id,occurrence_id,uploader_name,filename,content_type,byte_size,sha256,ciphertext,visibility,created_at)
                VALUES(:id,:company,:unit,:occurrence,:name,:filename,:type,:size,:hash,:cipher,'shared',:time)''', {
                'id': attachment_id, 'company': company, 'unit': draft['unit']['id'], 'occurrence': identifier,
                'name': draft['name'], 'filename': f'foto-whatsapp-{index + 1}.' + ('png' if photo['content_type'] == 'image/png' else 'jpg'),
                'type': photo['content_type'], 'size': photo['byte_size'], 'hash': photo['sha256'],
                'cipher': cipher.encrypt(base64.b64decode(photo['data'])).decode(), 'time': now()})
            record_audit(db, {'email': 'system:whatsapp'}, 'attachment.added', company, attachment_id, draft['unit']['id'])
        people = db.execute('SELECT id,roles_json,all_units,unit_ids_json FROM users WHERE company_id=:company AND is_active=1', {'company': company}).fetchall()
        for person in people:
            if set(json.loads(person['roles_json'])) & {'company_admin','supervisor'} and (person['all_units'] or draft['unit']['id'] in json.loads(person['unit_ids_json'])):
                db.execute('''INSERT INTO notifications(id,company_id,unit_id,user_id,occurrence_id,title,created_at)
                    VALUES(:id,:company,:unit,:user,:occurrence,:title,:time)''', {'id': str(uuid4()), 'company': company, 'unit': draft['unit']['id'], 'user': person['id'], 'occurrence': identifier, 'title': 'Nova ocorrência recebida pelo WhatsApp.', 'time': now()})
        draft.clear(); draft['stage'] = 'idle'
        return f'Solicitação registrada! Protocolo: {code}. A equipe fará a triagem. Digite MENU para abrir outra solicitação.'
    draft.clear()
    return 'Digite MENU para iniciar uma nova solicitação.'
