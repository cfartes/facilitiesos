"""Webhook autenticado e fila persistente; nenhum envio ocorre na transação de entrada."""
import asyncio
import base64
from datetime import datetime
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import time
from urllib.parse import urlsplit, quote
from uuid import UUID, uuid4

from cryptography.fernet import InvalidToken
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from backend import providers
from backend.foundation import now, record_audit
from backend.security import digest
from backend.whatsapp_dialogue import handle

CATEGORY = 'Solicitações via WhatsApp'


class BotInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool = Field(strict=True)


class WhatsAppIntake:
    def __init__(self, storage, cipher, rate_limit, lookup_key):
        self.storage, self.cipher, self.rate_limit = storage, cipher, rate_limit
        self.next_cleanup = 0
        self.lookup_key = hashlib.sha256((lookup_key.encode() if isinstance(lookup_key, str) else lookup_key) + b'whatsapp-phone-lookup').digest()

    def encode(self, value):
        return self.cipher.encrypt(json.dumps(value, ensure_ascii=False).encode()).decode()

    def decode(self, value):
        return json.loads(self.cipher.decrypt(value.encode()))

    def admin(self, user):
        if user['role'] != 'company_user' or 'company_admin' not in user.get('roles', []):
            raise HTTPException(403, 'Esta ação exige o administrador da empresa.')
        with self.storage.connect() as db:
            row = db.execute('''SELECT c.is_active,u.is_active AS user_active,u.roles_json FROM companies c
                JOIN users u ON u.company_id=c.id AND u.id=:user WHERE c.id=:company''', {'company': user['company_id'], 'user': user['id']}).fetchone()
        if not row or not row['is_active'] or not row['user_active'] or 'company_admin' not in json.loads(row['roles_json']):
            raise HTTPException(403, 'Empresa indisponível.')
        return user['company_id']

    def status(self, user):
        company = self.admin(user)
        with self.storage.connect() as db:
            row = db.execute('SELECT bot_enabled,hook_status FROM company_whatsapp WHERE company_id=:company', {'company': company}).fetchone()
            counts = db.execute('SELECT status,count(*) AS total FROM whatsapp_outbox WHERE company_id=:company GROUP BY status', {'company': company}).fetchall()
        return {'enabled': bool(row and row['bot_enabled']), 'hook_status': row['hook_status'] if row else 'disabled',
                'public_url_configured': bool(os.getenv('FACILITIES_WEBHOOK_ORIGIN')), 'replies': {item['status']: item['total'] for item in counts}}

    def configure(self, user, enabled):
        company = self.admin(user)
        self.rate_limit('whatsapp-bot-config:' + company, 5, 60)
        if not enabled:
            with self.storage.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                db.execute("UPDATE company_whatsapp SET bot_enabled=0,hook_status='disabled',lease=NULL,lease_until=0 WHERE company_id=:company", {'company': company})
                db.execute('DELETE FROM whatsapp_conversations WHERE company_id=:company', {'company': company})
                db.execute("UPDATE whatsapp_outbox SET status='cancelled',payload='' WHERE company_id=:company AND status='queued'", {'company': company})
                record_audit(db, user, 'whatsapp.intake_disabled', company, company)
            return self.status(user)
        origin = os.getenv('FACILITIES_WEBHOOK_ORIGIN', '').rstrip('/')
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.hostname in ('localhost','127.0.0.1','::1') or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
            raise HTTPException(409, 'Solicite ao responsável pela instalação a configuração do endereço público HTTPS para receber mensagens.')
        with self.storage.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM company_whatsapp WHERE company_id=:company', {'company': company}).fetchone()
            config = db.execute('SELECT openwa_key FROM configuration WHERE id=1').fetchone()
            if not row or not row['session_id'] or row['status'] != 'connected' or not config['openwa_key']:
                raise HTTPException(409, 'Conecte o WhatsApp da empresa antes de ativar as solicitações.')
            if row['lease_until'] > time.time():
                raise HTTPException(409, 'Uma operação da conexão está em andamento. Aguarde.')
            secret = row['webhook_secret'] or self.encode(secrets.token_urlsafe(48))
            lease = str(uuid4())
            db.execute("UPDATE company_whatsapp SET webhook_secret=:secret,hook_status='configuring',lease=:lease,lease_until=:until WHERE company_id=:company", {'secret': secret, 'lease': lease, 'until': time.time() + 120, 'company': company})
        success = False
        conflict = False
        try:
            key = self.cipher.decrypt(config['openwa_key'].encode()).decode()
            url = origin + '/api/v1/webhooks/openwa/' + company
            path = providers.OPENWA_BASE + '/sessions/' + row['session_id'] + '/webhooks'
            hooks = providers.request_provider(path + '?limit=100', {'X-API-Key': key})
            if not isinstance(hooks, list):
                raise HTTPException(502, 'O OpenWA não confirmou a lista de webhooks.')
            matches = [item for item in hooks if isinstance(item, dict) and item.get('url') == url]
            if matches:
                if not row['webhook_secret']:
                    conflict = True
                    raise HTTPException(409, 'Já existe um webhook para este endereço sem vínculo com a instalação. Revise somente esse webhook no OpenWA antes de ativar.')
                if not any(item.get('active') is True and 'message.received' in (item.get('events') or []) for item in matches):
                    raise HTTPException(502, 'O webhook existente está inativo ou incompatível. Revise-o no OpenWA.')
            else:
                providers.request_provider(path, {'X-API-Key': key}, {'url': url, 'events': ['message.received'], 'secret': self.decode(secret)})
            self.admin(user)
            with self.storage.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                fresh = db.execute('SELECT * FROM company_whatsapp WHERE company_id=:company', {'company': company}).fetchone()
                current_key = db.execute('SELECT openwa_key FROM configuration WHERE id=1').fetchone()['openwa_key']
                if fresh['lease'] != lease or fresh['lease_until'] < time.time() or fresh['session_id'] != row['session_id'] or current_key != config['openwa_key']:
                    raise HTTPException(409, 'A configuração mudou. Ative novamente após atualizar a conexão.')
                category = db.execute('SELECT id,is_active FROM service_categories WHERE company_id=:company AND name=:name', {'company': company, 'name': CATEGORY}).fetchone()
                if category and not category['is_active']:
                    raise HTTPException(409, 'Ative a categoria Solicitações via WhatsApp antes de continuar.')
                if not category:
                    db.execute('INSERT INTO service_categories(id,company_id,name) VALUES(:id,:company,:name)', {'id': str(uuid4()), 'company': company, 'name': CATEGORY})
                db.execute("UPDATE company_whatsapp SET bot_enabled=1,hook_status='active',enabled_since=CASE WHEN bot_enabled=1 THEN enabled_since ELSE :time END WHERE company_id=:company", {'time': time.time(), 'company': company})
                record_audit(db, user, 'whatsapp.intake_enabled', company, company)
            success = True
        except InvalidToken:
            raise HTTPException(503, 'Revise os segredos da integração com o responsável pela instalação.') from None
        finally:
            with self.storage.connect() as db:
                db.execute("UPDATE company_whatsapp SET lease=NULL,lease_until=0,webhook_secret=CASE WHEN :conflict=1 THEN '' ELSE webhook_secret END,hook_status=CASE WHEN :success=1 THEN hook_status ELSE 'error' END WHERE company_id=:company AND lease=:lease", {'success': int(success), 'conflict': int(conflict), 'company': company, 'lease': lease})
        return self.status(user)

    def receive(self, company, raw, signature):
        resolved = self.resolve_private_sender(company, raw, signature)
        prepared = self.prepare_photo(company, raw, signature, resolved)
        with self.storage.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            config = db.execute('''SELECT w.*,c.is_active,k.openwa_key FROM company_whatsapp w
                JOIN companies c ON c.id=w.company_id CROSS JOIN configuration k WHERE w.company_id=:company AND k.id=1''', {'company': company}).fetchone()
            if not config or not config['webhook_secret']:
                raise HTTPException(403, 'Evento não autorizado.')
            try:
                expected = 'sha256=' + hmac.new(self.decode(config['webhook_secret']).encode(), raw, hashlib.sha256).hexdigest()
            except InvalidToken:
                raise HTTPException(403, 'Evento não autorizado.') from None
            if not re.fullmatch(r'sha256=[0-9a-f]{64}', signature) or not hmac.compare_digest(expected, signature):
                raise HTTPException(403, 'Evento não autorizado.')
            try:
                event = json.loads(raw)
            except ValueError:
                raise HTTPException(400, 'Evento inválido.') from None
            if not isinstance(event, dict) or event.get('event') != 'message.received' or not config['bot_enabled'] or not config['is_active'] or not config['openwa_key'] or event.get('sessionId') != config['session_id']:
                return
            data = event.get('data')
            if not isinstance(data, dict) or data.get('fromMe') is not False or data.get('isGroup'):
                return
            chat, identifier = data.get('from'), data.get('id')
            recipient = chat
            if resolved:
                if resolved['session'] != config['session_id'] or resolved['key'] != config['openwa_key'] or resolved['sender'] != chat:
                    raise HTTPException(503, 'A conexão mudou durante a identificação do remetente. Reenvie o evento.')
                chat = resolved['phone'] + '@c.us'
            if not isinstance(chat, str) or not re.fullmatch(r'[1-9][0-9]{7,14}@(c\.us|s\.whatsapp\.net)', chat) or not isinstance(identifier, str) or not 1 <= len(identifier) <= 250:
                return
            chat = chat.split('@')[0] + '@c.us'
            recipient = recipient.replace('@s.whatsapp.net', '@c.us')
            try:
                timestamp = datetime.fromisoformat(str(event.get('timestamp', '')).replace('Z','+00:00'))
                if timestamp.tzinfo is None:
                    return
                occurred = timestamp.timestamp()
            except ValueError:
                return
            current = time.time()
            if not max(config['enabled_since'] - 1, current - 1800) <= occurred <= current + 300:
                return
            event_id = digest(company + ':' + config['session_id'] + ':' + identifier)
            if db.execute('SELECT id FROM whatsapp_events WHERE id=:id', {'id': event_id}).fetchone():
                return
            phone = hmac.new(self.lookup_key, (company + ':' + chat).encode(), hashlib.sha256).hexdigest()
            identity = 'whatsapp-in:' + phone
            throttle = db.execute('SELECT started,attempts FROM rate_limits WHERE identity=:id', {'id': identity}).fetchone()
            if throttle and throttle['started'] > current - 60 and throttle['attempts'] >= 30:
                raise HTTPException(429, 'Aguarde antes de enviar outra mensagem.')
            db.execute('''INSERT INTO rate_limits(identity,started,attempts) VALUES(:id,:time,1)
                ON CONFLICT(identity) DO UPDATE SET started=:time,attempts=:count''', {
                'id': identity, 'time': throttle['started'] if throttle and throttle['started'] > current - 60 else current,
                'count': throttle['attempts'] + 1 if throttle and throttle['started'] > current - 60 else 1})
            db.execute('INSERT INTO whatsapp_events(id,company_id,session_id,created_at) VALUES(:id,:company,:session,:time)', {'id': event_id, 'company': company, 'session': config['session_id'], 'time': current})
            conversation = db.execute('SELECT * FROM whatsapp_conversations WHERE company_id=:company AND phone_hash=:phone', {'company': company, 'phone': phone}).fetchone()
            if conversation and occurred < conversation['last_event_at']:
                return
            draft = self.decode(conversation['draft']) if conversation and conversation['expires'] > current else {}
            text = data.get('body')
            category = db.execute('SELECT id FROM service_categories WHERE company_id=:company AND name=:name AND is_active=1', {'company': company, 'name': CATEGORY}).fetchone()
            if not category:
                reply = 'O recebimento de solicitações está temporariamente indisponível. Contate o administrador da empresa.'
            elif data.get('type') == 'image':
                if not prepared or prepared['session'] != config['session_id'] or prepared['key'] != config['openwa_key'] or not conversation or prepared['last_event_at'] != conversation['last_event_at'] or draft.get('stage') != 'photos':
                    reply = 'Envie fotos somente quando o atendimento solicitar, depois da descrição do problema. Para usar a etiqueta QR, leia com a câmera do celular e envie a mensagem preenchida. Digite MENU para começar.'
                elif prepared.get('error'):
                    reply = prepared['error']
                else:
                    reply = handle(db, self.cipher, company, phone, chat, draft, '', category['id'], photo=prepared['photo'])
            elif not isinstance(text, str) or not text.strip() or len(text) > 4000 or data.get('type') not in (None, 'chat', 'text'):
                reply = 'Envie a descrição em texto. Na etapa de fotos, use JPEG/PNG pelo clipe ou câmera do WhatsApp. Para identificar o equipamento, leia a etiqueta com a câmera do celular e envie a mensagem preenchida.'
            else:
                reply = handle(db, self.cipher, company, phone, chat, draft, text.strip(), category['id'])
            if data.get('type') in (None, 'chat', 'text') and isinstance(text, str) and text.strip().casefold() in ('menu','cancelar'):
                db.execute("UPDATE whatsapp_outbox SET status='cancelled',payload='' WHERE company_id=:company AND phone_hash=:phone AND status='queued' AND is_receipt=0", {'company': company, 'phone': phone})
            db.execute('''INSERT INTO whatsapp_conversations(company_id,phone_hash,draft,expires,last_event_at) VALUES(:company,:phone,:draft,:expires,:time)
                ON CONFLICT(company_id,phone_hash) DO UPDATE SET draft=:draft,expires=:expires,last_event_at=:time''', {'company': company, 'phone': phone, 'draft': self.encode(draft), 'expires': current + 86400, 'time': occurred})
            db.execute('''INSERT INTO whatsapp_outbox(id,company_id,session_id,phone_hash,event_id,payload,credential_hash,is_receipt,status,created_at)
                VALUES(:id,:company,:session,:phone,:event,:payload,:hash,:receipt,'queued',:time)''', {'id': str(uuid4()), 'company': company, 'session': config['session_id'], 'phone': phone, 'event': event_id,
                'payload': self.encode({'chatId': recipient, 'text': reply}), 'hash': digest(config['openwa_key']), 'receipt': int(reply.startswith('Solicitação registrada! Protocolo:')), 'time': current})

    def prepare_photo(self, company, raw, signature, resolved):
        from backend.attachments import normalize_image
        try:
            event = json.loads(raw)
        except ValueError:
            return None
        data = event.get('data') if isinstance(event, dict) else None
        if not isinstance(data, dict) or data.get('type') != 'image':
            return None
        sender, identifier = data.get('from'), data.get('id')
        if not isinstance(sender, str) or not re.fullmatch(r'(?:[1-9][0-9]{7,14}@(c\.us|s\.whatsapp\.net)|[0-9]{5,30}@lid)', sender) or not isinstance(identifier, str) or not 1 <= len(identifier) <= 250:
            return None
        with self.storage.connect() as db:
            config = db.execute('''SELECT w.*,c.is_active,k.openwa_key FROM company_whatsapp w
                JOIN companies c ON c.id=w.company_id CROSS JOIN configuration k WHERE w.company_id=:company AND k.id=1''', {'company': company}).fetchone()
            if not config or not config['webhook_secret'] or not re.fullmatch(r'sha256=[0-9a-f]{64}', signature):
                raise HTTPException(403, 'Evento não autorizado.')
            try:
                expected = 'sha256=' + hmac.new(self.decode(config['webhook_secret']).encode(), raw, hashlib.sha256).hexdigest()
            except InvalidToken:
                raise HTTPException(403, 'Evento não autorizado.') from None
            if not hmac.compare_digest(expected, signature):
                raise HTTPException(403, 'Evento não autorizado.')
            if event.get('event') != 'message.received' or event.get('sessionId') != config['session_id'] or not config['bot_enabled'] or not config['is_active'] or not config['openwa_key'] or data.get('fromMe') is not False or data.get('isGroup'):
                return None
            if resolved and (resolved['session'] != config['session_id'] or resolved['key'] != config['openwa_key'] or resolved['sender'] != sender):
                return None
            if sender.endswith('@lid') and not resolved:
                return None
            chat = (resolved['phone'] if resolved else sender.split('@')[0]) + '@c.us'
            phone = hmac.new(self.lookup_key, (company + ':' + chat).encode(), hashlib.sha256).hexdigest()
            conversation = db.execute('SELECT * FROM whatsapp_conversations WHERE company_id=:company AND phone_hash=:phone', {'company': company, 'phone': phone}).fetchone()
            if not conversation or conversation['expires'] <= time.time() or self.decode(conversation['draft']).get('stage') != 'photos':
                return None
            if db.execute('SELECT id FROM whatsapp_events WHERE id=:id', {'id': digest(company + ':' + config['session_id'] + ':' + identifier)}).fetchone():
                return None
        try:
            timestamp = datetime.fromisoformat(str(event.get('timestamp', '')).replace('Z', '+00:00'))
            if timestamp.tzinfo is None or not max(config['enabled_since'] - 1, time.time() - 1800, conversation['last_event_at']) <= timestamp.timestamp() <= time.time() + 300:
                return None
        except ValueError:
            return None
        self.rate_limit('whatsapp-photo:' + phone, 10, 60)
        prepared = {'session': config['session_id'], 'key': config['openwa_key'], 'last_event_at': conversation['last_event_at']}
        try:
            key = self.cipher.decrypt(config['openwa_key'].encode()).decode()
            raw_image, content_type = providers.openwa_image(key, config['session_id'], sender, identifier)
            filename = 'foto.png' if content_type == 'image/png' else 'foto.jpg'
            _, image, fingerprint = normalize_image(raw_image, filename, content_type)
            prepared['photo'] = {'data': base64.b64encode(image).decode(), 'sha256': fingerprint, 'byte_size': len(image), 'content_type': content_type}
        except HTTPException as error:
            prepared['error'] = str(error.detail) + '\nEnvie outra foto ou digite 0 para seguir.'
        return prepared

    def resolve_private_sender(self, company, raw, signature):
        # A resolução é somente leitura e ocorre fora da transação de gravação.
        try:
            event = json.loads(raw)
        except ValueError:
            return None
        data = event.get('data') if isinstance(event, dict) else None
        sender = data.get('from') if isinstance(data, dict) else None
        if not isinstance(sender, str) or not re.fullmatch(r'[0-9]{5,30}@lid', sender):
            return None
        with self.storage.connect() as db:
            config = db.execute('''SELECT w.*,c.is_active,k.openwa_key FROM company_whatsapp w
                JOIN companies c ON c.id=w.company_id CROSS JOIN configuration k WHERE w.company_id=:company AND k.id=1''', {'company': company}).fetchone()
            if not config or not config['webhook_secret'] or not re.fullmatch(r'sha256=[0-9a-f]{64}', signature):
                raise HTTPException(403, 'Evento não autorizado.')
            try:
                expected = 'sha256=' + hmac.new(self.decode(config['webhook_secret']).encode(), raw, hashlib.sha256).hexdigest()
            except InvalidToken:
                raise HTTPException(403, 'Evento não autorizado.') from None
            if not hmac.compare_digest(expected, signature):
                raise HTTPException(403, 'Evento não autorizado.')
            if event.get('event') != 'message.received' or event.get('sessionId') != config['session_id'] or not config['is_active'] or not config['bot_enabled'] or not config['openwa_key'] or data.get('fromMe') is not False or data.get('isGroup'):
                return None
            identifier = data.get('id')
            if not isinstance(identifier, str) or not 1 <= len(identifier) <= 250:
                return None
            if db.execute('SELECT id FROM whatsapp_events WHERE id=:id', {'id': digest(company + ':' + config['session_id'] + ':' + identifier)}).fetchone():
                return None
        try:
            timestamp = datetime.fromisoformat(str(event.get('timestamp', '')).replace('Z','+00:00'))
            if timestamp.tzinfo is None or not max(config['enabled_since'] - 1, time.time() - 1800) <= timestamp.timestamp() <= time.time() + 300:
                return None
        except ValueError:
            return None
        self.rate_limit('whatsapp-resolve:' + company, 120, 60)
        key = self.cipher.decrypt(config['openwa_key'].encode()).decode()
        result = providers.request_provider(providers.OPENWA_BASE + '/sessions/' + config['session_id'] + '/contacts/' + quote(sender, safe='') + '/phone', {'X-API-Key': key})
        phone = result.get('phone') if isinstance(result, dict) else None
        if not isinstance(phone, str) or not re.fullmatch(r'[1-9][0-9]{7,14}', phone):
            raise HTTPException(503, 'O provedor não confirmou o telefone do remetente.')
        return {'sender': sender, 'phone': phone, 'session': config['session_id'], 'key': config['openwa_key']}

    def process_one(self):
        with self.storage.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = time.time()
            if current >= self.next_cleanup:
                db.execute('DELETE FROM whatsapp_conversations WHERE expires<:time', {'time': current})
                db.execute("UPDATE whatsapp_outbox SET status='cancelled',payload='' WHERE status='queued' AND created_at<:time", {'time': current - 3600})
                db.execute("DELETE FROM whatsapp_outbox WHERE status<>'sending' AND created_at<:time", {'time': current - 30 * 86400})
                db.execute('DELETE FROM whatsapp_events WHERE created_at<:time AND NOT EXISTS(SELECT 1 FROM whatsapp_outbox o WHERE o.event_id=whatsapp_events.id)', {'time': current - 30 * 86400})
                self.next_cleanup = current + 60
            db.execute("UPDATE whatsapp_outbox SET status='uncertain',payload='' WHERE status='sending' AND lease_until<:time", {'time': current})
            row = db.execute('''SELECT o.*,w.bot_enabled,w.session_id AS bound_session,c.is_active,k.openwa_key
                FROM whatsapp_outbox o JOIN company_whatsapp w ON w.company_id=o.company_id JOIN companies c ON c.id=o.company_id CROSS JOIN configuration k
                WHERE o.status='queued' AND k.id=1 AND NOT EXISTS(SELECT 1 FROM whatsapp_outbox p WHERE p.company_id=o.company_id AND p.phone_hash=o.phone_hash AND p.status='sending')
                ORDER BY o.created_at,o.id LIMIT 1''').fetchone()
            if not row:
                return False
            if not row['bot_enabled'] or not row['is_active'] or row['bound_session'] != row['session_id'] or digest(row['openwa_key']) != row['credential_hash'] or current - row['created_at'] > 3600:
                db.execute("UPDATE whatsapp_outbox SET status='cancelled',payload='' WHERE id=:id", {'id': row['id']})
                return True
            db.execute("UPDATE whatsapp_outbox SET status='sending',lease_until=:until WHERE id=:id", {'until': current + 60, 'id': row['id']})
        status = 'uncertain'
        try:
            key = self.cipher.decrypt(row['openwa_key'].encode()).decode()
            result = providers.request_provider(providers.OPENWA_BASE + '/sessions/' + row['session_id'] + '/messages/send-text', {'X-API-Key': key}, self.decode(row['payload']))
            # O contrato não garante idempotência de envio; resposta ambígua nunca é repetida automaticamente.
            value = result.get('data', result) if isinstance(result, dict) else None
            if isinstance(value, dict) and result.get('success') is not False and value.get('success') is not False and (
                    result.get('success') is True or value.get('success') is True or
                    any(isinstance(value.get(field), str) and bool(value[field].strip()) for field in ('id', 'messageId'))):
                status = 'accepted'
        except (HTTPException, InvalidToken, ValueError, OSError):
            pass
        with self.storage.connect() as db:
            db.execute("UPDATE whatsapp_outbox SET status=:status,payload='' WHERE id=:id AND status='sending'", {'id': row['id'], 'status': status})
        return True

    async def run(self, stop):
        while not stop.is_set():
            try:
                await asyncio.to_thread(self.process_one)
            except Exception:
                logging.getLogger(__name__).warning('Fila WhatsApp indisponível; processamento será verificado novamente.')
            try:
                await asyncio.wait_for(stop.wait(), 1)
            except TimeoutError:
                pass


def register_intake(app, service, actor):
    @app.get('/api/v1/company/whatsapp/intake')
    def settings(user=Depends(actor)):
        return service.status(user)

    @app.post('/api/v1/company/whatsapp/intake')
    def configure(data: BotInput, user=Depends(actor)):
        return service.configure(user, data.enabled)

    @app.post('/api/v1/webhooks/openwa/{company_id}', status_code=202)
    async def webhook(company_id: UUID, request: Request):
        await asyncio.to_thread(service.receive, str(company_id), await request.body(), request.headers.get('x-openwa-signature', ''))
        return {'received': True}
