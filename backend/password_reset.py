"""Recuperação de contas de empresas; tokens nunca retornam no endpoint público."""
import hmac
import secrets
import time

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from backend.company_details import InitialAdmin
from backend.foundation import hydrate_user, now, record_audit
from backend.security import digest, password_hash, verify_password

REQUEST_MESSAGE = 'Se houver uma conta elegível e o envio estiver disponível, você receberá um link de recuperação. Verifique o spam ou contate o administrador da sua empresa.'
INVALID_LINK = 'Link inválido, expirado ou já utilizado. Solicite a recuperação novamente ou contate o administrador.'
RESET_LIFETIME = 30 * 60


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    email: EmailStr = Field(max_length=254)


class ResetConfirmation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    token: SecretStr = Field(min_length=32, max_length=200)
    password: SecretStr = Field(min_length=12, max_length=128)

    @field_validator('password')
    @classmethod
    def valid_password(cls, value):
        return InitialAdmin.valid_password(value)


def register_password_reset(app, storage, outbox, rate_limit, secure_cookie):
    @app.post('/api/v1/public/password-reset/request', status_code=202)
    def request_reset(data: ResetRequest, request: Request):
        started = time.perf_counter()
        rate_limit('reset-request-ip:' + digest(request.client.host if request.client else 'local'), 10, 900)
        email = str(data.email).lower()
        try:
            try:
                rate_limit('reset-request-email:' + digest(email), 3, 3600)
            except HTTPException as error:
                if error.status_code != 429:
                    raise
                return {'message': REQUEST_MESSAGE}
            # Mesmo trabalho criptográfico para contas existentes e inexistentes.
            password_hash(secrets.token_urlsafe(32))
            with storage.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                user = hydrate_user(db, email)
                if not user or not user['is_active'] or not user['company_active'] or not user['password_hash'] or not outbox.settings(db, 'password_reset')['enabled']:
                    return {'message': REQUEST_MESSAGE}
                current = db.execute('SELECT * FROM password_resets WHERE user_id=:id', {'id': user['id']}).fetchone()
                if current and not current['used_at'] and current['expires'] > time.time() and hmac.compare_digest(current['credential_hash'], digest(user['password_hash'])):
                    return {'message': REQUEST_MESSAGE}
                token, expires = secrets.token_urlsafe(48), time.time() + RESET_LIFETIME
                outbox.cancel(db, user['id'], 'Pedido de recuperação substituído.', kind='password_reset')
                db.execute('DELETE FROM password_resets WHERE user_id=:id', {'id': user['id']})
                db.execute('INSERT INTO password_resets(user_id,company_id,token_hash,credential_hash,expires) VALUES(:user,:company,:token,:credential,:expires)', {
                    'user': user['id'], 'company': user['company_id'], 'token': digest(token), 'credential': digest(user['password_hash']), 'expires': expires,
                })
                try:
                    outbox.enqueue(db, user, token, expires, kind='password_reset')
                except HTTPException:
                    # Configuração indisponível não deve revelar se a conta existe.
                    db.execute('DELETE FROM password_resets WHERE user_id=:id', {'id': user['id']})
                    return {'message': REQUEST_MESSAGE}
                record_audit(db, {'email': user['email']}, 'password_reset.requested', user['company_id'], user['id'])
            return {'message': REQUEST_MESSAGE}
        finally:
            # Normalizar respostas curtas, sem prometer eliminar todo canal lateral de tempo.
            time.sleep(max(0, 0.25 + secrets.randbelow(51) / 1000 - (time.perf_counter() - started)))

    @app.post('/api/v1/public/password-reset/confirm')
    def confirm_reset(data: ResetConfirmation, request: Request, response: Response):
        rate_limit('reset-confirm-ip:' + digest(request.client.host if request.client else 'local'), 10, 900)
        token_hash = digest(data.token.get_secret_value())
        rate_limit('reset-confirm-token:' + token_hash, 5, 900)
        raw_password = data.password.get_secret_value()
        hashed = password_hash(raw_password)
        with storage.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('''SELECT r.*,u.email,u.name,u.is_active,c.is_active AS company_active,a.password_hash
                FROM password_resets r JOIN users u ON u.id=r.user_id JOIN companies c ON c.id=r.company_id
                JOIN auth_accounts a ON a.user_id=u.id WHERE r.token_hash=:token''', {'token': token_hash}).fetchone()
            if (not row or row['used_at'] or row['expires'] <= time.time() or not row['is_active'] or not row['company_active']
                    or not row['password_hash'] or not hmac.compare_digest(row['credential_hash'], digest(row['password_hash']))
                    or not outbox.settings(db, 'password_reset')['enabled']):
                raise HTTPException(400, INVALID_LINK)
            if verify_password(raw_password, row['password_hash']):
                raise HTTPException(422, 'Escolha uma senha diferente da atual.')
            db.execute('UPDATE auth_accounts SET password_hash=:password WHERE user_id=:user', {'password': hashed, 'user': row['user_id']})
            db.execute('UPDATE password_resets SET used_at=:time WHERE user_id=:user', {'time': now(), 'user': row['user_id']})
            db.execute('DELETE FROM sessions WHERE email=:email', {'email': row['email']})
            db.execute('DELETE FROM invitations WHERE user_id=:user', {'user': row['user_id']})
            outbox.cancel(db, row['user_id'], 'Credencial da conta alterada.')
            record_audit(db, {'email': row['email']}, 'password_reset.completed', row['company_id'], row['user_id'])
            try:
                outbox.enqueue(db, {'id': row['user_id'], 'company_id': row['company_id'], 'name': row['name'], 'email': row['email']},
                               secrets.token_urlsafe(48), time.time() + 23 * 3600, kind='password_changed')
            except HTTPException:
                record_audit(db, {'email': row['email']}, 'password_reset.notice_unavailable', row['company_id'], row['user_id'])
        response.delete_cookie('facilities_session', secure=secure_cookie, httponly=True, samesite='lax')
        response.delete_cookie('facilities_csrf', secure=secure_cookie, samesite='lax')
        return {'message': 'Senha alterada. As sessões anteriores foram encerradas. Entre novamente com sua nova senha.'}
