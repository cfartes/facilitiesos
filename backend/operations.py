"""Operação do piloto: relatos, atendimento humano e comprovação textual."""
import json
import os
import hashlib
from typing import Literal
from urllib.parse import quote
from uuid import UUID, uuid4

from cryptography.fernet import InvalidToken
from fastapi import Body, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError

from backend.foundation import now, record_audit
from backend.security import digest

COORDINATORS = {'company_admin', 'supervisor'}
REVIEWERS = {'manager', 'auditor'}
ACTIVE_STATES = {'triage', 'assigned', 'in_progress', 'waiting'}


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class CategoryInput(Input):
    name: str = Field(min_length=2, max_length=120)


class CategoryUpdate(CategoryInput):
    is_active: bool = Field(strict=True)
    expected_version: int = Field(ge=1, strict=True)


class AssetInput(Input):
    name: str = Field(min_length=2, max_length=160)
    code: str = Field(min_length=2, max_length=40, pattern=r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
    location_id: UUID
    category: str = Field(min_length=2, max_length=100)
    criticality: str = Field(pattern=r'^(low|medium|high|critical)$')


class AssetUpdate(Input):
    name: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=100)
    criticality: str = Field(pattern=r'^(low|medium|high|critical)$')
    status: str = Field(pattern=r'^(active|out_of_service|retired)$')
    expected_version: int = Field(ge=1, strict=True)


class OccurrenceInput(Input):
    title: str = Field(min_length=5, max_length=180)
    description: str = Field(min_length=10, max_length=4000)
    location_id: UUID
    category_id: UUID
    asset_id: UUID | None = None
    requester_id: UUID | None = None
    client_request_id: UUID


class OrderInput(Input):
    occurrence_id: UUID
    expected_occurrence_version: int = Field(ge=1, strict=True)
    title: str = Field(min_length=5, max_length=180)
    description: str = Field(min_length=10, max_length=4000)
    impact: int = Field(ge=1, le=4, strict=True)
    urgency: int = Field(ge=1, le=4, strict=True)
    assignee_id: UUID | None = None


class LinkInput(Input):
    occurrence_id: UUID
    expected_version: int = Field(ge=1, strict=True)


class AssignInput(Input):
    assignee_id: UUID
    expected_version: int = Field(ge=1, strict=True)


class ActionInput(Input):
    action: str = Field(pattern=r'^(start|wait|resolve|close|reopen|cancel)$')
    expected_version: int = Field(ge=1, strict=True)
    note: str = Field(default='', max_length=4000)
    solution: str = Field(default='', max_length=4000)
    evidence: str = Field(default='', max_length=4000)


class MessageInput(Input):
    body: str = Field(min_length=1, max_length=4000)
    visibility: str = Field(default='shared', pattern=r'^(shared|internal)$')


class ConfirmationInput(Input):
    outcome: str = Field(pattern=r'^(confirmed|contested)$')
    expected_version: int = Field(ge=1, strict=True)
    note: str = Field(default='', max_length=2000)


def coordinates(user):
    return user['role'] == 'superadmin' or bool(set(user.get('roles', [])) & COORDINATORS)


def reviews(user):
    return coordinates(user) or bool(set(user.get('roles', [])) & REVIEWERS)


def unit_allowed(user, unit_id):
    return user['role'] == 'superadmin' or user['all_units'] or unit_id in user['unit_ids']


def priority(impact, urgency):
    score = impact * urgency
    return 'critical' if score >= 12 else 'high' if score >= 8 else 'medium' if score >= 4 else 'low'


ORDER_SELECT = '''SELECT w.*,l.name AS location_name,c.name AS category_name,u.name AS assignee_name,a.name AS asset_name
 FROM work_orders w JOIN locations l ON l.id=w.location_id AND l.company_id=w.company_id
 JOIN service_categories c ON c.id=w.category_id AND c.company_id=w.company_id
 LEFT JOIN users u ON u.id=w.assignee_id AND u.company_id=w.company_id
 LEFT JOIN assets a ON a.id=w.asset_id AND a.company_id=w.company_id'''
OCCURRENCE_SELECT = '''SELECT o.*,l.name AS location_name,c.name AS category_name,u.name AS requester_name,
 a.name AS asset_name,w.code AS order_code,w.state AS order_state,w.solution,w.evidence,w.cycle
 FROM occurrences o JOIN locations l ON l.id=o.location_id AND l.company_id=o.company_id
 JOIN service_categories c ON c.id=o.category_id AND c.company_id=o.company_id
 JOIN users u ON u.id=o.requester_id AND u.company_id=o.company_id
 LEFT JOIN assets a ON a.id=o.asset_id AND a.company_id=o.company_id
 LEFT JOIN work_orders w ON w.id=o.order_id AND w.company_id=o.company_id'''


def register_operations(app, storage, actor, rate_limit, cipher):
    def scope(user, company_id):
        company = str(company_id)
        if user['role'] != 'superadmin' and (user['role'] != 'company_user' or user.get('company_id') != company):
            raise HTTPException(404, 'Empresa não encontrada.')
        if user['role'] == 'superadmin' and os.getenv('FACILITIES_ENV', 'development') != 'development':
            raise HTTPException(403, 'O acesso de suporte à operação precisa ser autorizado pela empresa.')
        with storage.connect() as db:
            row = db.execute('SELECT is_active FROM companies WHERE id=:id', {'id': company}).fetchone()
        if not row:
            raise HTTPException(404, 'Empresa não encontrada.')
        if not row['is_active']:
            raise HTTPException(403, 'Ative a empresa antes de operar.')
        return company

    def write(user, coordinate=False):
        if coordinate and not coordinates(user):
            raise HTTPException(403, 'Esta ação exige supervisor ou administrador da empresa.')
        if user['role'] != 'superadmin' and not (set(user.get('roles', [])) - {'auditor'}):
            raise HTTPException(403, 'O perfil de auditoria permite apenas consulta.')
        rate_limit('operations-write:' + digest(user['email']), 60, 60)

    def place(db, user, company, identifier):
        row = db.execute('SELECT * FROM locations WHERE company_id=:company AND id=:id', {'company': company, 'id': str(identifier)}).fetchone()
        if not row or not unit_allowed(user, row['unit_id']):
            raise HTTPException(404, 'Local não encontrado no seu acesso.')
        if not row['is_active']:
            raise HTTPException(409, 'Selecione um local ativo.')
        return row

    def person(company, unit_id, identifier, technician=False):
        with storage.connect() as db:
            row = db.execute('''SELECT u.* FROM users u JOIN auth_accounts a ON a.user_id=u.id
                WHERE u.company_id=:company AND u.id=:id AND u.is_active=1 AND a.password_hash IS NOT NULL''', {'company': company, 'id': str(identifier)}).fetchone()
        if not row or not (row['all_units'] or unit_id in json.loads(row['unit_ids_json'])):
            raise HTTPException(422, 'Selecione uma pessoa ativa, com acesso configurado nesta unidade.')
        roles = set(json.loads(row['roles_json']))
        if technician and not roles & (COORDINATORS | {'technician'}):
            raise HTTPException(422, 'O responsável deve ser técnico, supervisor ou administrador.')
        if not technician and not roles - {'auditor'}:
            raise HTTPException(422, 'O solicitante precisa de perfil operacional.')
        return row

    def order_allowed(db, user, row):
        if not unit_allowed(user, row['unit_id']):
            return False
        if reviews(user) or row['assignee_id'] == user.get('id'):
            return True
        return bool(db.execute('SELECT user_id FROM order_participants WHERE company_id=:company AND order_id=:order AND user_id=:user',
                               {'company': row['company_id'], 'order': row['id'], 'user': user.get('id', '')}).fetchone())

    def get_order(db, user, company, identifier):
        row = db.execute(ORDER_SELECT + ' WHERE w.company_id=:company AND w.id=:id', {'company': company, 'id': str(identifier)}).fetchone()
        if not row or not order_allowed(db, user, row):
            raise HTTPException(404, 'Ordem não encontrada no seu acesso.')
        return row

    def get_occurrence(db, user, company, identifier):
        row = db.execute(OCCURRENCE_SELECT + ' WHERE o.company_id=:company AND o.id=:id', {'company': company, 'id': str(identifier)}).fetchone()
        if not row or not unit_allowed(user, row['unit_id']) or (not reviews(user) and row['requester_id'] != user.get('id')):
            raise HTTPException(404, 'Ocorrência não encontrada no seu acesso.')
        return row

    def internal(user, order):
        return reviews(user) or order['assignee_id'] == user.get('id')

    def event(db, user, order, action, note='', visibility='shared'):
        db.execute('''INSERT INTO order_events(id,company_id,unit_id,order_id,actor_name,visibility,created_at,action,note,cycle)
            VALUES(:id,:company,:unit,:order,:actor,:visibility,:created,:action,:note,:cycle)''', {
            'id': str(uuid4()), 'company': order['company_id'], 'unit': order['unit_id'], 'order': order['id'],
            'actor': user.get('name', 'Administração Nexus'), 'visibility': visibility, 'created': now(),
            'action': action, 'note': note, 'cycle': order['cycle'],
        })
        record_audit(db, user, action, order['company_id'], order['id'], order['unit_id'])

    def notify(db, user, company, unit_id, title, order_id=None, occurrence_id=None, requester=None, private=False):
        # A consulta privilegiada serve apenas para entrega; não retorna o diretório ao solicitante.
        with storage.connect() as platform:
            people = platform.execute('SELECT id,roles_json,all_units,unit_ids_json FROM users WHERE company_id=:company AND is_active=1', {'company': company}).fetchall()
            participants = platform.execute('SELECT user_id FROM order_participants WHERE company_id=:company AND order_id=:order', {'company': company, 'order': order_id}).fetchall() if order_id else []
        targets = {item['user_id'] for item in participants} if not private else set()
        if requester and not private:
            targets.add(requester)
        if order_id:
            assigned = db.execute('SELECT assignee_id FROM work_orders WHERE id=:id AND company_id=:company', {'id': order_id, 'company': company}).fetchone()
            if assigned and assigned['assignee_id']:
                targets.add(assigned['assignee_id'])
        for item in people:
            if set(json.loads(item['roles_json'])) & COORDINATORS:
                targets.add(item['id'])
        for item in people:
            if item['id'] == user.get('id') or item['id'] not in targets or not (item['all_units'] or unit_id in json.loads(item['unit_ids_json'])):
                continue
            db.execute('''INSERT INTO notifications(id,company_id,unit_id,user_id,order_id,occurrence_id,title,created_at)
                VALUES(:id,:company,:unit,:user,:order,:occurrence,:title,:created)''', {
                'id': str(uuid4()), 'company': company, 'unit': unit_id, 'user': item['id'], 'order': order_id,
                'occurrence': occurrence_id, 'title': title, 'created': now(),
            })

    def link(db, user, order, occurrence):
        if order['state'] not in ACTIVE_STATES:
            raise HTTPException(409, 'Vincule relatos somente a atendimentos em andamento.')
        if occurrence['order_id']:
            raise HTTPException(409, 'A ocorrência já está vinculada a uma ordem.')
        if any(order[key] != occurrence[key] for key in ('company_id','unit_id','location_id','category_id','asset_id')):
            raise HTTPException(422, 'Os relatos devem corresponder ao mesmo local, categoria e ativo da ordem.')
        db.execute("UPDATE occurrences SET order_id=:order,outcome='linked',first_response_at=COALESCE(first_response_at,:time),version=version+1 WHERE id=:id AND company_id=:company", {
            'order': order['id'], 'id': occurrence['id'], 'company': order['company_id'], 'time': now(),
        })
        db.execute('INSERT INTO order_participants(company_id,unit_id,order_id,user_id) VALUES(:company,:unit,:order,:user) ON CONFLICT(company_id,order_id,user_id) DO NOTHING', {
            'company': order['company_id'], 'unit': order['unit_id'], 'order': order['id'], 'user': occurrence['requester_id'],
        })
        event(db, user, order, 'occurrence.linked', 'Relato vinculado ao atendimento.')
        notify(db, user, order['company_id'], order['unit_id'], 'Ocorrência vinculada a uma ordem de serviço.', order['id'], occurrence['id'], occurrence['requester_id'])

    from backend import attachments

    def attachment_context(db, user, company, resource, parent_id):
        row = (get_order if resource == 'orders' else get_occurrence)(db, user, company, parent_id)
        state = row['state'] if resource == 'orders' else row['order_state']
        can_write = (user['role'] == 'superadmin' or bool(set(user.get('roles', [])) - {'auditor'})) and state not in ('closed', 'cancelled')
        return row, resource == 'orders' and internal(user, row), can_write

    def attachment_query(resource):
        return 'order_id' if resource == 'orders' else 'occurrence_id'

    def attachment_public(row, user, can_write):
        return {key: row[key] for key in ('id', 'filename', 'content_type', 'byte_size', 'visibility', 'uploader_name', 'created_at')} | {
            'can_remove': can_write and (coordinates(user) or (user.get('id') is not None and row['uploader_id'] == user['id'])),
        }

    attachment_fields = 'id,filename,content_type,byte_size,visibility,uploader_id,uploader_name,created_at'
    attachment_path = '/api/v1/operations/companies/{company_id}/{resource}/{parent_id}/attachments'

    @app.get(attachment_path)
    def list_attachments(company_id: UUID, resource: Literal['orders', 'occurrences'], parent_id: UUID, user=Depends(actor)):
        company = scope(user, company_id)
        with storage.scoped(user, company) as db:
            _, private, can_write = attachment_context(db, user, company, resource, parent_id)
            rows = db.execute(f'SELECT {attachment_fields} FROM attachments WHERE company_id=:company AND {attachment_query(resource)}=:parent' + ('' if private else " AND visibility='shared'") + ' ORDER BY created_at,id', {
                'company': company, 'parent': str(parent_id),
            }).fetchall()
            return {'items': [attachment_public(row, user, can_write) for row in rows], 'can_upload': can_write, 'can_internal': private}

    @app.post(attachment_path, status_code=201)
    def upload_attachment(company_id: UUID, resource: Literal['orders', 'occurrences'], parent_id: UUID,
                          body: bytes = Body(media_type='application/octet-stream'), visibility: Literal['shared', 'internal'] = 'shared',
                          filename: str = Header(default='', alias='X-File-Name', max_length=1500),
                          content_type: str = Header(default='', alias='Content-Type'), user=Depends(actor)):
        company = scope(user, company_id); write(user)
        rate_limit('attachment-upload:' + digest(user['email']), 10, 60)
        # Autorizar antes de decodificar fotos ou consultar a cota privilegiada.
        with storage.scoped(user, company) as db:
            _, private, can_write = attachment_context(db, user, company, resource, parent_id)
            if not can_write:
                raise HTTPException(403, 'Seu perfil ou a situação do atendimento não permite adicionar arquivos.')
            if visibility == 'internal' and not private:
                raise HTTPException(403, 'Seu acesso não permite anexos internos neste atendimento.')
        name, image, fingerprint = attachments.normalize_image(body, filename, content_type)
        with storage.scoped(user, company) as db:
            db.execute('BEGIN IMMEDIATE')
            row, private, can_write = attachment_context(db, user, company, resource, parent_id)
            if not can_write or (visibility == 'internal' and not private):
                raise HTTPException(409, 'O atendimento mudou. Recarregue antes de anexar a imagem.')
            column = attachment_query(resource)
            params = {'company': company, 'parent': str(parent_id), 'visibility': visibility, 'hash': fingerprint}
            duplicate = db.execute(f'SELECT {attachment_fields} FROM attachments WHERE company_id=:company AND {column}=:parent AND visibility=:visibility AND sha256=:hash', params).fetchone()
            if duplicate:
                return attachment_public(duplicate, user, can_write)
            # Contagens não dependem da visibilidade do solicitante, para evitar contornar os limites.
            with storage.connect() as platform:
                count = platform.execute(f'SELECT count(*) AS total FROM attachments WHERE company_id=:company AND {column}=:parent', params).fetchone()['total']
                used = platform.execute('SELECT COALESCE(sum(byte_size),0) AS total FROM attachments WHERE company_id=:company', {'company': company}).fetchone()['total']
            if count >= attachments.MAX_PER_RECORD:
                raise HTTPException(409, 'Este registro atingiu o limite de dez imagens.')
            if used + len(image) > attachments.MAX_COMPANY_BYTES:
                raise HTTPException(409, 'A empresa atingiu a cota de imagens do piloto. Procure o administrador.')
            identifier = str(uuid4())
            payload = {'id': identifier, 'company': company, 'unit': row['unit_id'], 'order': str(parent_id) if resource == 'orders' else None,
                       'occurrence': str(parent_id) if resource == 'occurrences' else None, 'uploader': user.get('id'),
                       'actor': user.get('name', 'Administração Nexus'), 'filename': name, 'type': content_type,
                       'size': len(image), 'hash': fingerprint, 'cipher': cipher.encrypt(image).decode(), 'visibility': visibility, 'time': now()}
            db.execute('''INSERT INTO attachments(id,company_id,unit_id,order_id,occurrence_id,uploader_id,uploader_name,filename,content_type,byte_size,sha256,ciphertext,visibility,created_at)
                VALUES(:id,:company,:unit,:order,:occurrence,:uploader,:actor,:filename,:type,:size,:hash,:cipher,:visibility,:time)''', payload)
            record_audit(db, user, 'attachment.added', company, identifier, row['unit_id'])
            if resource == 'orders':
                event(db, user, row, 'attachment.added', 'Imagem adicionada ao atendimento.', visibility)
            notify(db, user, company, row['unit_id'], 'Nova imagem no atendimento.',
                   order_id=str(parent_id) if resource == 'orders' else None, occurrence_id=str(parent_id) if resource == 'occurrences' else None,
                   requester=row.get('requester_id'), private=visibility == 'internal')
            saved = db.execute(f'SELECT {attachment_fields} FROM attachments WHERE id=:id AND company_id=:company', {'id': identifier, 'company': company}).fetchone()
            return attachment_public(saved, user, can_write)

    def find_attachment(db, user, company, resource, parent_id, identifier):
        parent, private, can_write = attachment_context(db, user, company, resource, parent_id)
        row = db.execute(f'SELECT {attachment_fields} FROM attachments WHERE company_id=:company AND {attachment_query(resource)}=:parent AND id=:id' + ('' if private else " AND visibility='shared'"), {
            'company': company, 'parent': str(parent_id), 'id': str(identifier),
        }).fetchone()
        if not row:
            raise HTTPException(404, 'Imagem não encontrada no seu acesso.')
        return parent, row, can_write

    @app.get(attachment_path + '/{attachment_id}')
    def download_attachment(company_id: UUID, resource: Literal['orders', 'occurrences'], parent_id: UUID, attachment_id: UUID, user=Depends(actor)):
        company = scope(user, company_id)
        rate_limit('attachment-download:' + digest(user['email']), 60, 60)
        with storage.scoped(user, company) as db:
            parent, row, _ = find_attachment(db, user, company, resource, parent_id, attachment_id)
            stored = db.execute('SELECT ciphertext,sha256 FROM attachments WHERE company_id=:company AND id=:id', {'company': company, 'id': str(attachment_id)}).fetchone()
            try:
                image = cipher.decrypt(stored['ciphertext'].encode())
            except (InvalidToken, ValueError):
                raise HTTPException(503, 'Não foi possível abrir a imagem. Procure o administrador.') from None
            if hashlib.sha256(image).hexdigest() != stored['sha256']:
                raise HTTPException(503, 'Não foi possível verificar a integridade da imagem.')
            record_audit(db, user, 'attachment.downloaded', company, str(attachment_id), parent['unit_id'])
            return Response(image, media_type=row['content_type'], headers={
                'Content-Disposition': "attachment; filename*=UTF-8''" + quote(row['filename'], safe=''), 'Cache-Control': 'private, no-store',
            })

    class RemoveAttachment(Input):
        note: str = Field(default='', max_length=1000)

    @app.delete(attachment_path + '/{attachment_id}', status_code=204)
    def remove_attachment(company_id: UUID, resource: Literal['orders', 'occurrences'], parent_id: UUID, attachment_id: UUID,
                          data: RemoveAttachment, user=Depends(actor)):
        company = scope(user, company_id); write(user)
        with storage.scoped(user, company) as db:
            db.execute('BEGIN IMMEDIATE')
            parent, row, can_write = find_attachment(db, user, company, resource, parent_id, attachment_id)
            if not attachment_public(row, user, can_write)['can_remove']:
                raise HTTPException(403, 'Somente o autor ou a coordenação podem remover imagens de um atendimento aberto.')
            if resource == 'orders' and len(data.note) < 10:
                raise HTTPException(422, 'Informe o motivo da remoção com pelo menos dez caracteres.')
            db.execute('DELETE FROM attachments WHERE company_id=:company AND id=:id', {'company': company, 'id': str(attachment_id)})
            record_audit(db, user, 'attachment.removed', company, str(attachment_id), parent['unit_id'])
            if resource == 'orders':
                event(db, user, parent, 'attachment.removed', data.note, row['visibility'])
            return Response(status_code=204)

    @app.get('/api/v1/operations/companies/{company_id}/metadata')
    def metadata(company_id: UUID, user=Depends(actor)):
        company = scope(user, company_id)
        with storage.scoped(user, company) as db:
            locations = [dict(row) for row in db.execute('SELECT id,name,kind,parent_id,unit_id,is_active FROM locations WHERE company_id=:company ORDER BY name,id LIMIT 5000', {'company': company}).fetchall() if unit_allowed(user, row['unit_id'])]
            categories = [dict(row) | {'is_active': bool(row['is_active'])} for row in db.execute('SELECT * FROM service_categories WHERE company_id=:company ORDER BY name,id LIMIT 500', {'company': company}).fetchall()]
            assets = [dict(row) for row in db.execute('SELECT * FROM assets WHERE company_id=:company ORDER BY name,id LIMIT 1000', {'company': company}).fetchall() if unit_allowed(user, row['unit_id'])]
        people = []
        if coordinates(user):
            with storage.connect() as db:
                rows = db.execute('SELECT u.* FROM users u JOIN auth_accounts a ON a.user_id=u.id WHERE u.company_id=:company AND u.is_active=1 AND a.password_hash IS NOT NULL ORDER BY u.name,u.id LIMIT 1000', {'company': company}).fetchall()
            for row in rows:
                units = json.loads(row['unit_ids_json'])
                if user['role'] != 'superadmin' and not user['all_units'] and not row['all_units'] and not set(units) & set(user['unit_ids']):
                    continue
                people.append({'id': row['id'], 'name': row['name'], 'roles': json.loads(row['roles_json']), 'all_units': bool(row['all_units']), 'unit_ids': units})
        return {'locations': locations, 'categories': categories, 'assets': assets, 'people': people,
                'can_coordinate': coordinates(user), 'can_review': reviews(user), 'can_report': user['role'] == 'superadmin' or bool(set(user.get('roles', [])) - {'auditor'}), 'viewer_id': user.get('id')}

    @app.post('/api/v1/operations/companies/{company_id}/categories', status_code=201)
    def create_category(company_id: UUID, data: CategoryInput, user=Depends(actor)):
        company = scope(user, company_id); write(user, coordinate=True)
        if user['role'] != 'superadmin' and not user['all_units']:
            raise HTTPException(403, 'Categorias compartilhadas exigem acesso a todas as unidades.')
        values = {'id': str(uuid4()), 'company': company, 'name': data.name}
        try:
            with storage.scoped(user, company) as db:
                db.execute('INSERT INTO service_categories(id,company_id,name) VALUES(:id,:company,:name)', values)
                record_audit(db, user, 'category.created', company, values['id'])
                return dict(db.execute('SELECT * FROM service_categories WHERE id=:id AND company_id=:company', values).fetchone())
        except IntegrityError:
            raise HTTPException(409, 'Já existe uma categoria com esse nome.') from None

    @app.put('/api/v1/operations/companies/{company_id}/categories/{category_id}')
    def update_category(company_id: UUID, category_id: UUID, data: CategoryUpdate, user=Depends(actor)):
        company = scope(user, company_id); write(user, coordinate=True)
        if user['role'] != 'superadmin' and not user['all_units']:
            raise HTTPException(403, 'Categorias compartilhadas exigem acesso a todas as unidades.')
        try:
            with storage.scoped(user, company) as db:
                result = db.execute('UPDATE service_categories SET name=:name,is_active=:active,version=version+1 WHERE company_id=:company AND id=:id AND version=:version', {'name': data.name, 'active': int(data.is_active), 'company': company, 'id': str(category_id), 'version': data.expected_version})
                if result.rowcount != 1:
                    raise HTTPException(409, 'Categoria alterada ou indisponível. Recarregue os dados.')
                record_audit(db, user, 'category.updated', company, str(category_id))
                return {'message': 'Categoria atualizada.'}
        except IntegrityError:
            raise HTTPException(409, 'Já existe uma categoria com esse nome.') from None

    @app.post('/api/v1/operations/companies/{company_id}/assets', status_code=201)
    def create_asset(company_id: UUID, data: AssetInput, user=Depends(actor)):
        company = scope(user, company_id); write(user, coordinate=True)
        try:
            with storage.scoped(user, company) as db:
                location = place(db, user, company, data.location_id)
                values = {'id': str(uuid4()), 'company': company, 'unit': location['unit_id'], 'location': location['id'], 'name': data.name, 'code': data.code.upper(), 'category': data.category, 'criticality': data.criticality, 'created': now()}
                db.execute('INSERT INTO assets(id,company_id,unit_id,location_id,name,code,category,criticality,created_at) VALUES(:id,:company,:unit,:location,:name,:code,:category,:criticality,:created)', values)
                record_audit(db, user, 'asset.created', company, values['id'], location['unit_id'])
                return dict(db.execute('SELECT * FROM assets WHERE id=:id AND company_id=:company', values).fetchone())
        except IntegrityError:
            raise HTTPException(409, 'Identificação do ativo já utilizada nesta empresa.') from None

    @app.put('/api/v1/operations/companies/{company_id}/assets/{asset_id}')
    def update_asset(company_id: UUID, asset_id: UUID, data: AssetUpdate, user=Depends(actor)):
        company = scope(user, company_id); write(user, coordinate=True)
        with storage.scoped(user, company) as db:
            row = db.execute('SELECT * FROM assets WHERE id=:id AND company_id=:company', {'id': str(asset_id), 'company': company}).fetchone()
            if not row or not unit_allowed(user, row['unit_id']):
                raise HTTPException(404, 'Ativo não encontrado.')
            result = db.execute('UPDATE assets SET name=:name,category=:category,criticality=:criticality,status=:status,version=version+1 WHERE id=:id AND company_id=:company AND version=:version', {
                'name': data.name, 'category': data.category, 'criticality': data.criticality, 'status': data.status, 'id': row['id'], 'company': company, 'version': data.expected_version,
            })
            if result.rowcount != 1:
                raise HTTPException(409, 'O ativo foi alterado. Recarregue os dados.')
            record_audit(db, user, 'asset.updated', company, row['id'], row['unit_id'])
            return {'message': 'Ativo atualizado.'}

    @app.get('/api/v1/operations/companies/{company_id}/occurrences')
    def occurrences(company_id: UUID, user=Depends(actor)):
        company = scope(user, company_id)
        params = {'company': company, 'user': user.get('id', '')}
        condition = '' if reviews(user) else ' AND o.requester_id=:user'
        with storage.scoped(user, company) as db:
            rows = db.execute(OCCURRENCE_SELECT + ' WHERE o.company_id=:company' + condition + ' ORDER BY o.created_at DESC,o.id DESC LIMIT 500', params).fetchall()
        return [dict(row) for row in rows if unit_allowed(user, row['unit_id'])]

    @app.post('/api/v1/operations/companies/{company_id}/occurrences', status_code=201)
    def create_occurrence(company_id: UUID, data: OccurrenceInput, user=Depends(actor)):
        company = scope(user, company_id); write(user)
        requester = str(data.requester_id) if data.requester_id else user.get('id')
        if not requester or (requester != user.get('id') and not coordinates(user)):
            raise HTTPException(403, 'Selecione um solicitante autorizado. Você só pode abrir relatos em seu próprio nome.')
        fingerprint = digest(json.dumps(data.model_dump(mode='json') | {'requester_id': requester}, sort_keys=True))
        with storage.scoped(user, company) as db:
            db.execute('BEGIN IMMEDIATE')
            previous = db.execute('SELECT id,request_hash FROM occurrences WHERE company_id=:company AND requester_id=:user AND client_request_id=:request', {'company': company, 'user': requester, 'request': str(data.client_request_id)}).fetchone()
            if previous:
                if previous['request_hash'] != fingerprint:
                    raise HTTPException(409, 'Esta tentativa já foi usada para outro conteúdo. Abra um novo relato.')
                return dict(get_occurrence(db, user, company, previous['id']))
            location = place(db, user, company, data.location_id)
            person(company, location['unit_id'], requester)
            category = db.execute('SELECT id FROM service_categories WHERE company_id=:company AND id=:id AND is_active=1', {'company': company, 'id': str(data.category_id)}).fetchone()
            if not category:
                raise HTTPException(422, 'Selecione uma categoria ativa da empresa.')
            if data.asset_id:
                asset = db.execute("SELECT id FROM assets WHERE company_id=:company AND id=:id AND location_id=:location AND status<>'retired'", {'company': company, 'id': str(data.asset_id), 'location': location['id']}).fetchone()
                if not asset:
                    raise HTTPException(422, 'Selecione um ativo disponível no local informado.')
            identifier = str(uuid4())
            values = {'id': identifier, 'company': company, 'unit': location['unit_id'], 'location': location['id'], 'category': str(data.category_id), 'asset': str(data.asset_id) if data.asset_id else None,
                      'user': requester, 'request': str(data.client_request_id), 'hash': fingerprint, 'code': 'OC-' + identifier.replace('-', '')[:10].upper(), 'title': data.title, 'description': data.description, 'created': now()}
            db.execute('''INSERT INTO occurrences(id,company_id,unit_id,location_id,category_id,asset_id,requester_id,client_request_id,request_hash,code,title,description,created_at)
                VALUES(:id,:company,:unit,:location,:category,:asset,:user,:request,:hash,:code,:title,:description,:created)''', values)
            record_audit(db, user, 'occurrence.created', company, identifier, location['unit_id'])
            notify(db, user, company, location['unit_id'], 'Nova ocorrência aguardando triagem.', occurrence_id=identifier)
            return dict(get_occurrence(db, user, company, identifier))

    @app.get('/api/v1/operations/companies/{company_id}/orders')
    def orders(company_id: UUID, user=Depends(actor)):
        company = scope(user, company_id)
        condition = '' if reviews(user) else ' AND (w.assignee_id=:user OR EXISTS(SELECT 1 FROM order_participants p WHERE p.company_id=w.company_id AND p.order_id=w.id AND p.user_id=:user))'
        with storage.scoped(user, company) as db:
            rows = db.execute(ORDER_SELECT + ' WHERE w.company_id=:company' + condition + ' ORDER BY w.updated_at DESC,w.id DESC LIMIT 500', {'company': company, 'user': user.get('id', '')}).fetchall()
        return [dict(row) for row in rows if unit_allowed(user, row['unit_id'])]

    @app.get('/api/v1/operations/companies/{company_id}/orders/{order_id}')
    def order_detail(company_id: UUID, order_id: UUID, user=Depends(actor)):
        company = scope(user, company_id)
        with storage.scoped(user, company) as db:
            row = get_order(db, user, company, order_id)
            private = internal(user, row)
            visibility = '' if private else " AND visibility='shared'"
            messages = db.execute('SELECT id,actor_name,body,visibility,created_at FROM order_messages WHERE company_id=:company AND order_id=:order' + visibility + ' ORDER BY created_at,id LIMIT 500', {'company': company, 'order': row['id']}).fetchall()
            events = db.execute('SELECT id,actor_name,action,note,cycle,visibility,created_at FROM order_events WHERE company_id=:company AND order_id=:order' + visibility + ' ORDER BY created_at,id LIMIT 500', {'company': company, 'order': row['id']}).fetchall()
            own = '' if reviews(user) else ' AND o.requester_id=:user'
            reports = db.execute(OCCURRENCE_SELECT + ' WHERE o.company_id=:company AND o.order_id=:order' + own + ' ORDER BY o.created_at,o.id', {'company': company, 'order': row['id'], 'user': user.get('id', '')}).fetchall()
            return {'order': dict(row), 'messages': [dict(item) for item in messages], 'events': [dict(item) for item in events], 'occurrences': [dict(item) for item in reports],
                    'can_coordinate': coordinates(user), 'can_execute': coordinates(user) or row['assignee_id'] == user.get('id'), 'can_internal': private,
                    'can_message': user['role'] == 'superadmin' or bool(set(user.get('roles', [])) - {'auditor'})}

    @app.post('/api/v1/operations/companies/{company_id}/orders', status_code=201)
    def create_order(company_id: UUID, data: OrderInput, user=Depends(actor)):
        company = scope(user, company_id); write(user, coordinate=True)
        with storage.scoped(user, company) as db:
            db.execute('BEGIN IMMEDIATE')
            occurrence = get_occurrence(db, user, company, data.occurrence_id)
            if occurrence['version'] != data.expected_occurrence_version or occurrence['order_id']:
                raise HTTPException(409, 'A ocorrência foi alterada ou já está em atendimento. Recarregue os dados.')
            if data.assignee_id:
                person(company, occurrence['unit_id'], data.assignee_id, technician=True)
            identifier = str(uuid4())
            created = now()
            values = {'id': identifier, 'company': company, 'unit': occurrence['unit_id'], 'location': occurrence['location_id'], 'category': occurrence['category_id'], 'asset': occurrence['asset_id'],
                      'assignee': str(data.assignee_id) if data.assignee_id else None, 'code': 'OS-' + identifier.replace('-', '')[:10].upper(), 'title': data.title, 'description': data.description,
                      'impact': data.impact, 'urgency': data.urgency, 'priority': priority(data.impact, data.urgency), 'state': 'assigned' if data.assignee_id else 'triage', 'created': created}
            db.execute('''INSERT INTO work_orders(id,company_id,unit_id,location_id,category_id,asset_id,assignee_id,code,title,description,impact,urgency,priority,state,created_at,updated_at)
                VALUES(:id,:company,:unit,:location,:category,:asset,:assignee,:code,:title,:description,:impact,:urgency,:priority,:state,:created,:created)''', values)
            row = get_order(db, user, company, identifier)
            event(db, user, row, 'order.created', 'Prioridade definida por impacto × urgência: ' + row['priority'] + '.')
            link(db, user, row, occurrence)
            return dict(row)

    @app.post('/api/v1/operations/companies/{company_id}/orders/{order_id}/link')
    def link_occurrence(company_id: UUID, order_id: UUID, data: LinkInput, user=Depends(actor)):
        company = scope(user, company_id); write(user, coordinate=True)
        with storage.scoped(user, company) as db:
            db.execute('BEGIN IMMEDIATE')
            row = get_order(db, user, company, order_id)
            occurrence = get_occurrence(db, user, company, data.occurrence_id)
            if occurrence['order_id'] == row['id']:
                return {'message': 'Relato já vinculado.'}
            if row['version'] != data.expected_version:
                raise HTTPException(409, 'A ordem foi alterada. Recarregue os dados.')
            link(db, user, row, occurrence)
            db.execute('UPDATE work_orders SET version=version+1,updated_at=:time WHERE id=:id AND company_id=:company', {'time': now(), 'id': row['id'], 'company': company})
            return {'message': 'Relato vinculado ao atendimento.'}

    @app.post('/api/v1/operations/companies/{company_id}/orders/{order_id}/assign')
    def assign(company_id: UUID, order_id: UUID, data: AssignInput, user=Depends(actor)):
        company = scope(user, company_id); write(user, coordinate=True)
        with storage.scoped(user, company) as db:
            db.execute('BEGIN IMMEDIATE')
            row = get_order(db, user, company, order_id)
            if row['version'] != data.expected_version or row['state'] not in ACTIVE_STATES:
                raise HTTPException(409, 'Ordem alterada ou encerrada. Recarregue os dados.')
            assigned = person(company, row['unit_id'], data.assignee_id, technician=True)
            db.execute("UPDATE work_orders SET assignee_id=:assignee,state=CASE WHEN state='triage' THEN 'assigned' ELSE state END,version=version+1,updated_at=:time WHERE id=:id AND company_id=:company", {'assignee': assigned['id'], 'time': now(), 'id': row['id'], 'company': company})
            event(db, user, row, 'order.assigned', 'Responsável: ' + assigned['name'] + '.')
            notify(db, user, company, row['unit_id'], 'Responsável pelo atendimento atualizado.', row['id'])
            return {'message': 'Responsável atualizado. O início do atendimento foi preservado.'}

    @app.post('/api/v1/operations/companies/{company_id}/orders/{order_id}/actions')
    def action(company_id: UUID, order_id: UUID, data: ActionInput, user=Depends(actor)):
        company = scope(user, company_id); write(user)
        with storage.scoped(user, company) as db:
            db.execute('BEGIN IMMEDIATE')
            row = get_order(db, user, company, order_id)
            if not coordinates(user) and row['assignee_id'] != user.get('id'):
                raise HTTPException(403, 'Somente a coordenação ou o responsável pode executar esta ação.')
            if data.action in ('close','reopen','cancel') and not coordinates(user):
                raise HTTPException(403, 'Esta decisão exige a coordenação.')
            if data.expected_version != row['version']:
                raise HTTPException(409, 'A ordem foi alterada. Recarregue antes de continuar.')
            allowed = {'start': {'assigned','waiting'}, 'wait': {'in_progress'}, 'resolve': {'in_progress'},
                       'close': {'resolved'}, 'reopen': {'resolved','closed'}, 'cancel': ACTIVE_STATES | {'resolved'}}
            if row['state'] not in allowed[data.action]:
                raise HTTPException(409, 'Esta transição não é permitida no estado atual.')
            if data.action in ('wait','cancel','reopen') and len(data.note) < 10:
                raise HTTPException(422, 'Descreva o motivo com pelo menos dez caracteres.')
            if data.action in ('start','resolve','reopen'):
                if not row['assignee_id']:
                    raise HTTPException(409, 'Atribua um responsável antes de executar.')
                person(company, row['unit_id'], row['assignee_id'], technician=True)
            if data.action == 'resolve' and (len(data.solution) < 10 or len(data.evidence) < 10):
                raise HTTPException(422, 'Descreva a solução e a evidência textual com pelo menos dez caracteres cada.')
            if data.action == 'close':
                reports = db.execute('SELECT outcome FROM occurrences WHERE company_id=:company AND order_id=:order', {'company': company, 'order': row['id']}).fetchall()
                if any(item['outcome'] == 'contested' for item in reports):
                    raise HTTPException(409, 'Há contestação pendente. Reabra o atendimento.')
                if any(item['outcome'] != 'confirmed' for item in reports) and len(data.note) < 10:
                    raise HTTPException(422, 'Há confirmações pendentes. Registre a justificativa da revisão autorizada.')
            target = {'start':'in_progress','wait':'waiting','resolve':'resolved','close':'closed','reopen':'in_progress','cancel':'cancelled'}[data.action]
            current_cycle = row['cycle'] + (1 if data.action == 'reopen' else 0)
            values = {'state': target, 'cycle': current_cycle, 'time': now(), 'id': row['id'], 'company': company,
                      'solution': data.solution if data.action == 'resolve' else row['solution'], 'evidence': data.evidence if data.action == 'resolve' else row['evidence'],
                      'resolved': now() if data.action == 'resolve' else None if data.action == 'reopen' else row['resolved_at'],
                      'closed': now() if data.action == 'close' else None if data.action == 'reopen' else row['closed_at']}
            db.execute('UPDATE work_orders SET state=:state,cycle=:cycle,updated_at=:time,solution=:solution,evidence=:evidence,resolved_at=:resolved,closed_at=:closed,version=version+1 WHERE id=:id AND company_id=:company', values)
            if data.action in ('resolve','reopen','cancel'):
                outcome = 'cancelled' if data.action == 'cancel' else 'linked'
                db.execute('UPDATE occurrences SET outcome=:outcome,confirmation_note=\'\',version=version+1 WHERE company_id=:company AND order_id=:order', {'outcome': outcome, 'company': company, 'order': row['id']})
            updated = dict(row) | {'cycle': current_cycle}
            note = data.note
            if data.action == 'resolve':
                note = 'Solução: ' + data.solution + '\nEvidência: ' + data.evidence
            event(db, user, updated, 'order.' + data.action, note)
            notify(db, user, company, row['unit_id'], 'Atualização no andamento de uma ordem de serviço.', row['id'])
            return {'message': 'Atendimento atualizado.', 'state': target}

    @app.post('/api/v1/operations/companies/{company_id}/orders/{order_id}/messages', status_code=201)
    def message(company_id: UUID, order_id: UUID, data: MessageInput, user=Depends(actor)):
        company = scope(user, company_id); write(user)
        with storage.scoped(user, company) as db:
            db.execute('BEGIN IMMEDIATE')
            row = get_order(db, user, company, order_id)
            if row['state'] in ('closed','cancelled'):
                raise HTTPException(409, 'Reabra o atendimento para adicionar mensagens.')
            if data.visibility == 'internal' and not internal(user, row):
                raise HTTPException(403, 'Seu perfil não permite registrar notas internas neste atendimento.')
            db.execute('INSERT INTO order_messages(id,company_id,unit_id,order_id,actor_name,visibility,created_at,body) VALUES(:id,:company,:unit,:order,:actor,:visibility,:time,:body)', {
                'id': str(uuid4()), 'company': company, 'unit': row['unit_id'], 'order': row['id'], 'actor': user.get('name', 'Administração Nexus'),
                'visibility': data.visibility, 'time': now(), 'body': data.body,
            })
            record_audit(db, user, 'order.message_added', company, row['id'], row['unit_id'])
            notify(db, user, company, row['unit_id'], 'Nova nota interna no atendimento.' if data.visibility == 'internal' else 'Nova mensagem no atendimento.', row['id'], private=data.visibility == 'internal')
            return {'message': 'Mensagem registrada.'}

    @app.post('/api/v1/operations/companies/{company_id}/occurrences/{occurrence_id}/confirmation')
    def confirm(company_id: UUID, occurrence_id: UUID, data: ConfirmationInput, user=Depends(actor)):
        company = scope(user, company_id); write(user)
        with storage.scoped(user, company) as db:
            db.execute('BEGIN IMMEDIATE')
            occurrence = get_occurrence(db, user, company, occurrence_id)
            if occurrence['requester_id'] != user.get('id'):
                raise HTTPException(403, 'A confirmação pertence ao solicitante deste relato.')
            if not occurrence['order_id'] or occurrence['order_state'] not in ('resolved','closed') or occurrence['version'] != data.expected_version:
                raise HTTPException(409, 'A solução não está disponível para confirmação ou o relato foi alterado.')
            if data.outcome == 'contested' and len(data.note) < 10:
                raise HTTPException(422, 'Descreva a contestação com pelo menos dez caracteres.')
            row = get_order(db, user, company, occurrence['order_id'])
            if data.outcome == 'contested':
                db.execute("UPDATE work_orders SET state='in_progress',cycle=cycle+1,resolved_at=NULL,closed_at=NULL,updated_at=:time,version=version+1 WHERE company_id=:company AND id=:id", {'time': now(), 'company': company, 'id': row['id']})
                # Os demais solicitantes confirmam novamente após a nova resolução.
                # O solicitante só pode atualizar seu relato pelo papel da aplicação.
                # Confirmações anteriores não autorizam fechar o novo ciclo (ver close).
                row = dict(row) | {'cycle': row['cycle'] + 1}
            db.execute('UPDATE occurrences SET outcome=:outcome,confirmation_note=:note,version=version+1 WHERE id=:id AND company_id=:company', {'outcome': data.outcome, 'note': data.note, 'id': occurrence['id'], 'company': company})
            event(db, user, row, 'occurrence.' + data.outcome, data.note or 'Solução confirmada pelo solicitante.')
            notify(db, user, company, row['unit_id'], 'Solução contestada; atendimento reaberto.' if data.outcome == 'contested' else 'Solução confirmada pelo solicitante.', row['id'])
            return {'message': 'Atendimento reaberto para revisão.' if data.outcome == 'contested' else 'Confirmação registrada.'}

    @app.get('/api/v1/operations/companies/{company_id}/notifications')
    def notifications(company_id: UUID, user=Depends(actor)):
        company = scope(user, company_id)
        if not user.get('id'):
            return []
        with storage.scoped(user, company) as db:
            rows = db.execute('SELECT * FROM notifications WHERE company_id=:company AND user_id=:user ORDER BY created_at DESC,id DESC LIMIT 100', {'company': company, 'user': user['id']}).fetchall()
        return [dict(row) for row in rows if unit_allowed(user, row['unit_id'])]

    @app.post('/api/v1/operations/companies/{company_id}/notifications/{notification_id}/read')
    def read_notification(company_id: UUID, notification_id: UUID, user=Depends(actor)):
        company = scope(user, company_id)
        with storage.scoped(user, company) as db:
            row = db.execute('SELECT unit_id FROM notifications WHERE company_id=:company AND id=:id AND user_id=:user', {'company': company, 'id': str(notification_id), 'user': user.get('id', '')}).fetchone()
            if not row or not unit_allowed(user, row['unit_id']):
                raise HTTPException(404, 'Notificação não encontrada.')
            db.execute('UPDATE notifications SET read_at=COALESCE(read_at,:time) WHERE company_id=:company AND id=:id AND user_id=:user', {'time': now(), 'company': company, 'id': str(notification_id), 'user': user.get('id', '')})
        return {'message': 'Notificação marcada como lida.'}
