"""API da fundação Nexus: identidade, integrações e administração de empresas."""
import hmac
import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend import providers
from backend.database import Database
from backend.security import digest, verify_password

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')
load_dotenv(ROOT / '.env.database')


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Login(Input):
    email: EmailStr
    password: SecretStr = Field(max_length=1024)


class Configuration(Input):
    expected_version: int = Field(ge=0, strict=True)
    openwa_api_key: SecretStr | None = None
    resend_api_key: SecretStr | None = None
    email_from: EmailStr | None = None
    clear_openwa_key: bool = False
    clear_resend_key: bool = False

    @model_validator(mode='after')
    def check_keys(self):
        for key, clear in [(self.openwa_api_key, self.clear_openwa_key), (self.resend_api_key, self.clear_resend_key)]:
            raw = key.get_secret_value() if key else ''
            if raw and (len(raw) < 8 or len(raw) > 4096 or any(c.isspace() for c in raw) or not raw.isascii()):
                raise ValueError('Informe uma API Key válida, entre 8 e 4.096 caracteres, sem espaços.')
            if raw and clear:
                raise ValueError('Escolha entre substituir ou remover a chave.')
        return self


class EmailTest(Input):
    recipient: EmailStr


def create_app(database=None, admin_email=None, admin_hash=None, encryption_key=None, origin=None):
    platform_url = os.getenv('FACILITIES_PLATFORM_DATABASE_URL') if database is None else None
    tenant_url = os.getenv('FACILITIES_DATABASE_URL') if database is None else None
    environment = os.getenv('FACILITIES_ENV', 'development')
    if environment != 'development' and not platform_url:
        raise RuntimeError('Esta fundação local usa SQLite. Produção exige PostgreSQL, RLS e infraestrutura validada.')
    db_path = Path(database or os.getenv('FACILITIES_DB', str(ROOT / 'data/facilities.sqlite3')))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    email = admin_email or os.getenv('FACILITIES_ADMIN_EMAIL', '')
    hashed = admin_hash or os.getenv('FACILITIES_ADMIN_PASSWORD_HASH', '')
    key = encryption_key or os.getenv('FACILITIES_ENCRYPTION_KEY', '')
    allowed_origin = origin or os.getenv('FACILITIES_ORIGIN', 'http://127.0.0.1:5180')
    if environment != 'development' and not allowed_origin.startswith('https://'):
        raise RuntimeError('Ambientes externos exigem origem HTTPS.')
    if not email or not hashed or not key:
        raise RuntimeError('Execute python -m backend.bootstrap para configurar o Superadmin e a criptografia.')
    cipher = Fernet(key.encode() if isinstance(key, str) else key)
    secure_cookie = allowed_origin.startswith('https://')

    storage = Database(db_path, platform_url, tenant_url)
    connect = storage.connect

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            storage.dispose()

    app = FastAPI(title='Nexus Facilities OS', docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.storage = storage

    @app.get('/api/v1/health')
    def health():
        with connect() as db:
            db.execute('SELECT 1')
        return {'status': 'ok'}
    from urllib.parse import urlsplit
    host = urlsplit(allowed_origin).hostname
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list({host, '127.0.0.1', 'localhost', 'testserver'} if environment == 'development' else {host}))

    @app.middleware('http')
    async def security_headers(request: Request, call_next):
        if request.url.path.startswith('/api/') and request.method not in ('GET', 'HEAD', 'OPTIONS'):
            if request.headers.get('origin') != allowed_origin:
                response = JSONResponse({'detail': 'Origem não autorizada.'}, status_code=403)
            else:
                # Interrompe a leitura ao atingir o limite, inclusive sem Content-Length.
                body = b''
                async for chunk in request.stream():
                    body += chunk
                    if len(body) > 24000:
                        break
                request._body = body
                response = (JSONResponse({'detail': 'Requisição muito grande.'}, status_code=413)
                            if len(body) > 24000 else await call_next(request))
        else:
            response = await call_next(request)
        response.headers.update({
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY', 'Referrer-Policy': 'no-referrer',
            'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'; object-src 'none'",
            'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
        })
        if secure_cookie:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000'
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_input(request, error):
        # O erro padrão do Pydantic pode conter o valor original de um segredo.
        return JSONResponse({'detail': 'Dados inválidos. Confira os campos obrigatórios, formatos e permissões selecionadas.'}, status_code=422)

    def rate_limit(identity, limit, seconds):
        now = time.time()
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM rate_limits WHERE started < ?', (now - 86400,))
            row = db.execute('SELECT * FROM rate_limits WHERE identity=?', (identity,)).fetchone()
            if row and row['started'] > now - seconds:
                if row['attempts'] >= limit:
                    raise HTTPException(429, 'Muitas tentativas. Aguarde para tentar novamente.', headers={'Retry-After': str(max(1, int(row['started'] + seconds - now)))})
                db.execute('UPDATE rate_limits SET attempts=attempts+1 WHERE identity=?', (identity,))
            else:
                db.execute('INSERT INTO rate_limits(identity,started,attempts) VALUES(?,?,1) ON CONFLICT(identity) DO UPDATE SET started=excluded.started,attempts=1', (identity, now))

    def actor(request: Request):
        token = request.cookies.get('facilities_session', '')
        with connect() as db:
            db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
            user = db.execute('SELECT * FROM sessions WHERE token_hash=?', (digest(token),)).fetchone()
        if not user:
            raise HTTPException(401, 'Sua sessão expirou. Entre novamente.')
        user = dict(user)
        if user['role'] in ('superadmin', 'nexus_restricted'):
            if user['credential_hash'] != digest(hashed) or user['email'] != email:
                raise HTTPException(401, 'Sua sessão expirou. Entre novamente.')
            user.update(company_id=None, roles=[], unit_ids=[], all_units=True, name='Administração Nexus')
        elif user['role'] == 'company_user':
            from backend.foundation import hydrate_user
            with connect() as db:
                profile = hydrate_user(db, user['email'])
            if not profile or not profile['is_active'] or not profile['company_active'] or not profile['password_hash'] or user['credential_hash'] != digest(profile['password_hash']):
                raise HTTPException(401, 'Sua sessão expirou ou o acesso foi suspenso.')
            import json
            user.update(id=profile['id'], company_id=profile['company_id'], name=profile['name'],
                        roles=json.loads(profile['roles_json']), unit_ids=json.loads(profile['unit_ids_json']), all_units=bool(profile['all_units']))
        else:
            raise HTTPException(403, 'Perfil de acesso inválido.')
        if request.method not in ('GET', 'HEAD'):
            csrf = request.headers.get('x-csrf-token', '')
            cookie = request.cookies.get('facilities_csrf', '')
            if not csrf or not hmac.compare_digest(csrf.encode(), cookie.encode()) or not hmac.compare_digest(digest(csrf), user['csrf_hash']):
                raise HTTPException(403, 'Proteção da sessão inválida. Entre novamente.')
        return user

    def superadmin(user=Depends(actor)):
        if user['role'] != 'superadmin':
            raise HTTPException(403, 'Acesso exclusivo do Superadmin completo.')
        return user

    def public_user(user):
        return {key: user[key] for key in ('email', 'role', 'name', 'company_id', 'roles', 'unit_ids', 'all_units') if key in user}

    def audit(db, user, action):
        db.execute('INSERT INTO audit(actor,action,created_at) VALUES(?,?,?)',
                   (user, action, datetime.now(timezone.utc).isoformat()))

    def public(row):
        return {'version': row['version'], 'openwa_base_url': providers.OPENWA_BASE,
                'openwa_key_configured': bool(row['openwa_key']), 'resend_key_configured': bool(row['resend_key']),
                'email_from': row['email_from'], 'updated_at': row['updated_at']}

    def decrypt(value):
        if not value:
            raise HTTPException(409, 'Cadastre e salve a API Key antes de testar.')
        try:
            return cipher.decrypt(value.encode()).decode()
        except (InvalidToken, ValueError):
            raise HTTPException(503, 'Não foi possível abrir a credencial. Verifique a chave de criptografia do servidor.') from None

    @app.post('/api/v1/auth/login')
    def login(data: Login, request: Request, response: Response):
        rate_limit('login-ip:' + digest(request.client.host if request.client else 'local'), 10, 900)
        rate_limit('login-account:' + digest(str(data.email).lower()), 10, 900)
        account_email = str(data.email).lower()
        role, credential, active = 'superadmin', hashed, account_email == email.lower()
        if account_email != email.lower():
            from backend.foundation import hydrate_user
            with connect() as db:
                profile = hydrate_user(db, account_email)
            role = 'company_user'
            credential = profile['password_hash'] if profile and profile['password_hash'] else hashed
            active = bool(profile and profile['is_active'] and profile['company_active'] and profile['password_hash'])
        valid_password = verify_password(data.password.get_secret_value(), credential)
        if not active or not valid_password:
            raise HTTPException(401, 'E-mail ou senha inválidos.')
        token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        with connect() as db:
            db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
            db.execute('DELETE FROM sessions WHERE token_hash=?', (digest(request.cookies.get('facilities_session', '')),))
            db.execute('INSERT INTO sessions(token_hash,csrf_hash,email,role,expires,credential_hash) VALUES(?,?,?,?,?,?)', (digest(token), digest(csrf), account_email if role == 'company_user' else email, role, time.time() + 28800, digest(credential)))
            audit(db, account_email, 'auth.login')
        response.set_cookie('facilities_session', token, httponly=True, secure=secure_cookie, samesite='lax', max_age=28800)
        response.set_cookie('facilities_csrf', csrf, httponly=False, secure=secure_cookie, samesite='lax', max_age=28800)
        if role == 'superadmin':
            return {'email': email, 'role': role, 'name': 'Administração Nexus', 'company_id': None, 'roles': [], 'unit_ids': [], 'all_units': True}
        import json
        return {'email': account_email, 'role': role, 'name': profile['name'], 'company_id': profile['company_id'],
                'roles': json.loads(profile['roles_json']), 'unit_ids': json.loads(profile['unit_ids_json']), 'all_units': bool(profile['all_units'])}

    @app.get('/api/v1/auth/me')
    def me(user=Depends(actor)):
        return public_user(user)

    @app.post('/api/v1/auth/logout', status_code=204)
    def logout(response: Response, user=Depends(actor)):
        with connect() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?', (user['token_hash'],))
            audit(db, user['email'], 'auth.logout')
        response.delete_cookie('facilities_session', secure=secure_cookie, httponly=True, samesite='lax')
        response.delete_cookie('facilities_csrf', secure=secure_cookie, samesite='lax')

    @app.get('/api/v1/nexus/integrations')
    def get_configuration(user=Depends(superadmin)):
        with connect() as db:
            return public(db.execute('SELECT * FROM configuration WHERE id=1').fetchone())

    @app.put('/api/v1/nexus/integrations')
    def save_configuration(data: Configuration, user=Depends(superadmin)):
        rate_limit('save:' + digest(user['email']), 30, 60)
        with connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = dict(db.execute('SELECT * FROM configuration WHERE id=1').fetchone())
            if data.expected_version != row['version']:
                raise HTTPException(409, 'Outra alteração foi salva. Recarregue as configurações antes de continuar.')
            for field, secret, clear in [('openwa_key', data.openwa_api_key, data.clear_openwa_key), ('resend_key', data.resend_api_key, data.clear_resend_key)]:
                raw = secret.get_secret_value() if secret else ''
                if clear:
                    row[field] = ''
                elif raw:
                    row[field] = cipher.encrypt(raw.encode()).decode()
            if data.email_from is not None:
                row['email_from'] = str(data.email_from)
            if row['resend_key'] and not row['email_from']:
                raise HTTPException(422, 'Informe o e-mail remetente para configurar o Resend.')
            row['version'] += 1
            row['updated_at'] = datetime.now(timezone.utc).isoformat()
            db.execute('UPDATE configuration SET version=:version,openwa_key=:openwa_key,resend_key=:resend_key,email_from=:email_from,updated_at=:updated_at WHERE id=1', row)
            audit(db, user['email'], 'integrations.updated')
            return public(row)

    @app.post('/api/v1/nexus/integrations/test/openwa')
    def test_openwa(user=Depends(superadmin)):
        rate_limit('test-openwa:' + digest(user['email']), 5, 60)
        with connect() as db:
            key = decrypt(db.execute('SELECT openwa_key FROM configuration WHERE id=1').fetchone()[0])
            audit(db, user['email'], 'integrations.openwa.test_requested')
        sessions = providers.openwa_sessions(key)
        return {'message': 'Consulta de sessões concluída. Nenhuma mensagem foi enviada.', 'sessions': sessions}

    @app.post('/api/v1/nexus/integrations/test/resend')
    def test_resend(data: EmailTest, user=Depends(superadmin)):
        rate_limit('test-resend:' + digest(user['email']), 3, 60)
        with connect() as db:
            row = db.execute('SELECT * FROM configuration WHERE id=1').fetchone()
            key, sender = decrypt(row['resend_key']), row['email_from']
            if not sender:
                raise HTTPException(409, 'Cadastre o remetente antes de testar.')
            audit(db, user['email'], 'integrations.resend.test_requested')
        return providers.resend_test(key, sender, str(data.recipient))

    from backend.foundation import register_foundation
    register_foundation(app, storage, actor, superadmin, rate_limit, allowed_origin, email)
    return app
