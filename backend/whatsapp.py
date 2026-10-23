"""Conexão por empresa: sessão gerada pelo servidor, QR transitório e chave privada."""
import base64
import json
from io import BytesIO
import time
from uuid import UUID, uuid4

from cryptography.fernet import InvalidToken
from fastapi import Depends, HTTPException
from PIL import Image

from backend import providers
from backend.foundation import record_audit


def body(result):
    value = result.get('data', result) if isinstance(result, dict) else None
    if not isinstance(value, dict):
        raise HTTPException(502, 'Resposta de conexão não reconhecida no OpenWA.')
    return value


def safe_qr(value):
    if value is None or value == '':
        return None
    try:
        if not isinstance(value, str) or len(value) > 800_000:
            raise ValueError()
        raw = base64.b64decode(value.removeprefix('data:image/png;base64,'), validate=True)
        with Image.open(BytesIO(raw)) as image:
            if image.format != 'PNG' or image.width > 2048 or image.height > 2048:
                raise ValueError()
            image.verify()
        return 'data:image/png;base64,' + base64.b64encode(raw).decode('ascii')
    except (ValueError, OSError, SyntaxError, Image.DecompressionBombError):
        raise HTTPException(502, 'O OpenWA não retornou uma imagem válida do QR Code.') from None


def register_whatsapp(app, storage, actor, rate_limit, cipher):
    def authorize(user):
        if user['role'] != 'company_user' or 'company_admin' not in user.get('roles', []):
            raise HTTPException(403, 'A conexão WhatsApp exige o administrador da empresa.')
        with storage.connect() as db:
            company = db.execute('SELECT is_active FROM companies WHERE id=:id', {'id': user['company_id']}).fetchone()
            account = db.execute('SELECT is_active,roles_json FROM users WHERE id=:id AND company_id=:company', {'id': user['id'], 'company': user['company_id']}).fetchone()
            config = db.execute('SELECT openwa_key FROM configuration WHERE id=1').fetchone()
        if not company or not company['is_active'] or not account or not account['is_active'] or 'company_admin' not in json.loads(account['roles_json']):
            raise HTTPException(403, 'Acesso da empresa indisponível.')
        return user['company_id'], config['openwa_key']

    def connection(user, connect=False):
        company, encrypted = authorize(user)
        rate_limit('whatsapp:' + company, 20, 60)
        if not encrypted:
            if connect:
                raise HTTPException(409, 'Solicite ao Superadmin a configuração da integração OpenWA.')
            return {'configured': False, 'status': 'not_configured', 'qr_code': None}
        try:
            key = cipher.decrypt(encrypted.encode()).decode()
        except InvalidToken:
            raise HTTPException(503, 'A configuração OpenWA precisa ser revisada pelo Superadmin.') from None
        lease = str(uuid4())
        with storage.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO company_whatsapp(company_id) VALUES(:company) ON CONFLICT(company_id) DO NOTHING', {'company': company})
            row = db.execute('SELECT * FROM company_whatsapp WHERE company_id=:company', {'company': company}).fetchone()
            if row['lease_until'] > time.time():
                raise HTTPException(409, 'Uma consulta de conexão está em andamento. Aguarde alguns segundos.')
            if not row['session_id'] and not connect:
                return {'configured': True, 'status': 'not_connected', 'qr_code': None}
            db.execute('UPDATE company_whatsapp SET lease=:lease,lease_until=:until WHERE company_id=:company',
                       {'lease': lease, 'until': time.time() + 120, 'company': company})
        name = 'facilities-' + company
        session = row['session_id']
        try:
            if not session:
                sessions = providers.openwa_sessions(key)
                matches = [item for item in sessions if item['name'] == name]
                if len(matches) > 1:
                    raise HTTPException(502, 'Há sessões duplicadas para a empresa. Solicite revisão da integração.')
                result = matches[0] if matches else body(providers.request_provider(providers.OPENWA_BASE + '/sessions', {'X-API-Key': key}, {'name': name}))
                if result.get('name') != name:
                    raise HTTPException(502, 'O OpenWA não confirmou a sessão exclusiva da empresa.')
                try:
                    session = str(UUID(str(result.get('id'))))
                except (ValueError, TypeError):
                    raise HTTPException(502, 'O OpenWA não confirmou a sessão da empresa.') from None
                with storage.connect() as db:
                    # O vínculo é persistido antes de iniciar; uma falha posterior não cria outra sessão.
                    other = db.execute('SELECT company_id FROM company_whatsapp WHERE session_id=:session AND company_id<>:company', {'session': session, 'company': company}).fetchone()
                    if other:
                        raise HTTPException(409, 'Esta sessão já pertence a outra empresa.')
                    db.execute('UPDATE company_whatsapp SET session_id=:session WHERE company_id=:company AND lease=:lease', {'session': session, 'company': company, 'lease': lease})
            url = providers.OPENWA_BASE + '/sessions/' + session
            info = body(providers.request_provider(url, {'X-API-Key': key}))
            if info.get('name') != name:
                raise HTTPException(502, 'A sessão retornada não corresponde à empresa. Solicite revisão da integração.')
            state = str(info.get('status', '')).upper()
            if connect and state in ('CREATED', 'DISCONNECTED', 'STOPPED', 'FAILED'):
                providers.request_provider(url + '/start', {'X-API-Key': key}, {})
                state = 'STARTING'
            status = 'connected' if state in ('READY', 'CONNECTED') else 'qr_ready' if state == 'QR_READY' else 'disconnected' if state in ('DISCONNECTED','STOPPED','FAILED') else 'starting'
            qr = None
            if status == 'qr_ready':
                qr = safe_qr(body(providers.request_provider(url + '/qr', {'X-API-Key': key})).get('qrCode'))
            _, current_key = authorize(user)
            if current_key != encrypted:
                raise HTTPException(409, 'A configuração mudou. Consulte a conexão novamente.')
            with storage.connect() as db:
                result = db.execute('UPDATE company_whatsapp SET status=:status WHERE company_id=:company AND lease=:lease AND lease_until>:time', {'status': status, 'company': company, 'lease': lease, 'time': time.time()})
                if result.rowcount != 1:
                    raise HTTPException(409, 'A consulta expirou. Atualize a conexão.')
                if connect or row['status'] != status:
                    record_audit(db, user, 'whatsapp.connection_requested' if connect else 'whatsapp.' + status, company, company)
            return {'configured': True, 'status': status, 'qr_code': qr}
        finally:
            with storage.connect() as db:
                db.execute('UPDATE company_whatsapp SET lease=NULL,lease_until=0 WHERE company_id=:company AND lease=:lease', {'company': company, 'lease': lease})

    @app.get('/api/v1/company/whatsapp')
    def status(user=Depends(actor)):
        return connection(user)

    @app.post('/api/v1/company/whatsapp/connect')
    def connect(user=Depends(actor)):
        return connection(user, True)
