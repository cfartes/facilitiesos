"""Convites transacionais; corpo cifrado, lease e retentativas dentro da janela de idempotência."""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from cryptography.fernet import InvalidToken
from fastapi import HTTPException

from backend import providers
from backend.security import digest

ACTIVE = "('queued','sending','retrying')"
MAX_ATTEMPTS = 5
RETRY_DELAYS = (60, 300, 900, 3600)
# Resend conserva a chave por 24h; a margem impede repetir envio fora dessa janela.
RETRY_WINDOW = 23 * 3600


class EmailOutbox:
    def __init__(self, storage, cipher, origin, clock=None):
        self.storage, self.cipher, self.origin = storage, cipher, origin
        self.clock = clock or time.time

    def timestamp(self):
        return datetime.fromtimestamp(self.clock(), timezone.utc).isoformat()

    def audit(self, db, company, user_id, action):
        db.execute('INSERT INTO audit(actor,action,created_at,company_id,entity_id) VALUES(:actor,:action,:time,:company,:user)', {
            'actor': 'system:invitation-email', 'action': action, 'time': self.timestamp(), 'company': company, 'user': user_id,
        })

    def settings(self, db):
        row = db.execute('SELECT invitation_email_enabled,resend_key,email_from FROM configuration WHERE id=1').fetchone()
        return {'enabled': bool(row['invitation_email_enabled'] and row['resend_key'] and row['email_from'])}

    def cancel(self, db, user_id, reason):
        db.execute(f"UPDATE email_outbox SET status='cancelled',payload='',lease=NULL,lease_until=NULL,last_error=:reason,updated_at=:time WHERE user_id=:user AND status IN {ACTIVE}", {
            'user': user_id, 'reason': reason, 'time': self.timestamp(),
        })

    def enqueue(self, db, user, token, expires):
        config = db.execute('SELECT * FROM configuration WHERE id=1').fetchone()
        if not config['invitation_email_enabled'] or not config['resend_key'] or not config['email_from']:
            raise HTTPException(409, 'O envio de convites por e-mail está desativado. Gere o link manual ou solicite a configuração ao Superadmin.')
        try:
            key = self.cipher.decrypt(config['resend_key'].encode()).decode()
        except (InvalidToken, ValueError):
            raise HTTPException(503, 'Não foi possível abrir a configuração de e-mail. Procure o Superadmin.') from None
        company = db.execute('SELECT name,is_active FROM companies WHERE id=:id', {'id': user['company_id']}).fetchone()
        if not company['is_active']:
            raise HTTPException(409, 'Ative a empresa antes de enviar convites por e-mail.')
        payload = {'from': 'Nexus Facilities OS <' + config['email_from'] + '>', 'to': [user['email']],
                   'subject': 'Convite de acesso — Nexus Facilities OS',
                   'text': f"Olá, {user['name']}.\n\nVocê recebeu um convite para {company['name']} no Nexus Facilities OS.\n\n"
                           f"Defina sua senha pelo link: {self.origin}/convite#token={token}\n\n"
                           'O convite tem validade de 48 horas a partir da geração, é individual e de uso único. '
                           'Se você não esperava este convite, ignore a mensagem. Não compartilhe este link.'}
        identifier = str(uuid4())
        db.execute('''INSERT INTO email_outbox(id,company_id,user_id,invitation_hash,payload,credential_hash,status,expires,next_attempt_at,created_at,updated_at)
            VALUES(:id,:company,:user,:hash,:payload,:credential,'queued',:expires,:next,:time,:time)''', {
            'id': identifier, 'company': user['company_id'], 'user': user['id'], 'hash': digest(token),
            'payload': self.cipher.encrypt(json.dumps(payload).encode()).decode(), 'credential': digest(key),
            'expires': expires, 'next': self.clock(), 'time': self.timestamp(),
        })
        self.audit(db, user['company_id'], user['id'], 'invitation_email.queued')

    def statuses(self, db, company):
        rows = db.execute('''SELECT user_id,status,attempts,last_error,updated_at FROM (
            SELECT user_id,status,attempts,last_error,updated_at,ROW_NUMBER() OVER(PARTITION BY user_id ORDER BY created_at DESC,id DESC) AS position
            FROM email_outbox WHERE company_id=:company) ranked WHERE position=1''', {'company': company}).fetchall()
        return {row['user_id']: {key: row[key] for key in ('status','attempts','last_error','updated_at')} for row in rows}

    def _finish(self, db, row, state, message='', provider_id=None, next_attempt=None):
        db.execute('''UPDATE email_outbox SET status=:status,last_error=:error,provider_id=:provider,lease=NULL,lease_until=NULL,
            payload=CASE WHEN :keep=1 THEN payload ELSE '' END,next_attempt_at=:next,updated_at=:time
            WHERE id=:id''', {'status': state, 'error': message, 'provider': provider_id,
                             'keep': int(state == 'retrying'), 'next': next_attempt or self.clock(), 'time': self.timestamp(), 'id': row['id']})
        self.audit(db, row['company_id'], row['user_id'], 'invitation_email.' + state)

    def _claim(self):
        current = self.clock()
        with self.storage.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            # Cancelar também enquanto o envio estiver desabilitado, limpando tokens inválidos.
            db.execute(f'''UPDATE email_outbox SET status='cancelled',payload='',lease=NULL,lease_until=NULL,
                last_error='Convite expirado, utilizado ou revogado.',updated_at=:time WHERE status IN {ACTIVE} AND (
                expires<=:now OR NOT EXISTS(SELECT 1 FROM invitations i JOIN users u ON u.id=i.user_id JOIN companies c ON c.id=u.company_id
                    JOIN auth_accounts a ON a.user_id=u.id WHERE i.token_hash=email_outbox.invitation_hash AND i.user_id=email_outbox.user_id
                    AND i.used_at IS NULL AND i.expires>:now AND u.is_active=1 AND c.is_active=1 AND a.password_hash IS NULL))''', {'now': current, 'time': self.timestamp()})
            if not self.settings(db)['enabled']:
                return None
            row = db.execute("""SELECT * FROM email_outbox WHERE (status IN ('queued','retrying') AND next_attempt_at<=:now)
                OR (status='sending' AND lease_until<=:now) ORDER BY next_attempt_at,id LIMIT 1""", {'now': current}).fetchone()
            if not row:
                return None
            if row['attempts'] >= MAX_ATTEMPTS or (row['first_attempt_at'] is not None and current >= row['first_attempt_at'] + RETRY_WINDOW):
                self._finish(db, row, 'failed', 'Limite ou janela segura de tentativas atingido. Gere novo convite se necessário.')
                return False
            config = db.execute('SELECT resend_key FROM configuration WHERE id=1').fetchone()
            try:
                key = self.cipher.decrypt(config['resend_key'].encode()).decode()
                payload = json.loads(self.cipher.decrypt(row['payload'].encode()))
                if digest(key) != row['credential_hash']:
                    raise ValueError('credentials changed')
            except (InvalidToken, ValueError, UnicodeError):
                self._finish(db, row, 'failed', 'Configuração ou conteúdo do envio alterado/indisponível. Gere novo convite após revisar a integração.')
                return False
            lease = str(uuid4())
            db.execute("UPDATE email_outbox SET status='sending',attempts=attempts+1,first_attempt_at=COALESCE(first_attempt_at,:now),lease=:lease,lease_until=:until,updated_at=:time WHERE id=:id", {
                'now': current, 'lease': lease, 'until': current + 120, 'time': self.timestamp(), 'id': row['id'],
            })
            return row | {'lease': lease, 'attempts': row['attempts'] + 1, 'first_attempt_at': row['first_attempt_at'] if row['first_attempt_at'] is not None else current}, key, payload

    def process_one(self):
        claimed = self._claim()
        if claimed is None:
            return False
        if claimed is False:
            return True
        row, key, payload = claimed
        provider_id, failure = None, None
        try:
            provider_id = providers.resend_invitation(key, payload, 'facilities-invite/' + row['id'])
        except providers.InvitationSendError as error:
            failure = error
        except Exception:
            failure = providers.InvitationSendError('Falha interna no envio. Revise a configuração antes de gerar novo convite.')
        with self.storage.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            fresh = db.execute('SELECT status,lease FROM email_outbox WHERE id=:id', {'id': row['id']}).fetchone()
            if fresh['status'] != 'sending' or fresh['lease'] != row['lease']:
                return True
            if failure is None:
                self._finish(db, row, 'accepted', provider_id=provider_id)
            else:
                delay = max(RETRY_DELAYS[min(row['attempts'] - 1, len(RETRY_DELAYS) - 1)], failure.retry_after)
                next_attempt = self.clock() + delay
                retry = failure.retryable and row['attempts'] < MAX_ATTEMPTS and next_attempt < min(row['expires'], row['first_attempt_at'] + RETRY_WINDOW)
                message = str(failure) if retry or not failure.retryable else 'Limite ou janela segura de tentativas atingido. O resultado do envio não está confirmado; revise antes de gerar novo convite.'
                self._finish(db, row, 'retrying' if retry else 'failed', message, next_attempt=next_attempt)
        return True

    async def run(self, stop):
        while not stop.is_set():
            try:
                await asyncio.to_thread(self.process_one)
            except Exception:
                logging.getLogger(__name__).warning('Processamento de convites indisponível; nova verificação será feita.')
            try:
                await asyncio.wait_for(stop.wait(), timeout=2)
            except TimeoutError:
                pass
