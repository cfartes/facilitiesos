"""Empresas, convites, permissões por unidade e estrutura física."""
import json
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator, model_validator
from sqlalchemy.exc import IntegrityError

from backend.security import digest, password_hash

Role = Literal['requester', 'technician', 'supervisor', 'manager', 'approver', 'auditor', 'company_admin']
Kind = Literal['unit', 'building', 'floor', 'environment']
Criticality = Literal['low', 'medium', 'high', 'critical']


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class CompanyCreate(Input):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(min_length=3, max_length=60, pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


class CompanyUpdate(Input):
    name: str = Field(min_length=2, max_length=160)
    is_active: bool = Field(strict=True)
    expected_version: int = Field(ge=1, strict=True)


class LocationCreate(Input):
    name: str = Field(min_length=2, max_length=160)
    kind: Kind
    parent_id: UUID | None = None
    criticality: Criticality = 'medium'
    timezone: str = Field(default='America/Sao_Paulo', max_length=60)

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('Fuso horário inválido.') from None
        return value


class LocationUpdate(Input):
    name: str = Field(min_length=2, max_length=160)
    criticality: Criticality
    is_active: bool = Field(strict=True)
    expected_version: int = Field(ge=1, strict=True)


class UserAccess(Input):
    name: str = Field(min_length=2, max_length=160)
    roles: list[Role] = Field(min_length=1, max_length=7)
    all_units: bool = Field(strict=True)
    unit_ids: list[UUID] = Field(default_factory=list, max_length=200)

    @model_validator(mode='after')
    def valid_scope(self):
        if len(set(self.roles)) != len(self.roles) or len(set(self.unit_ids)) != len(self.unit_ids):
            raise ValueError('Permissões duplicadas.')
        if 'company_admin' in self.roles and not self.all_units:
            raise ValueError('O administrador da empresa exige acesso a todas as unidades.')
        if self.all_units and self.unit_ids:
            raise ValueError('Selecione todas as unidades ou uma lista específica.')
        if not self.all_units and not self.unit_ids:
            raise ValueError('Selecione pelo menos uma unidade.')
        return self


class UserCreate(UserAccess):
    email: EmailStr


class UserUpdate(UserAccess):
    is_active: bool = Field(strict=True)
    expected_version: int = Field(ge=1, strict=True)


class AcceptInvitation(Input):
    token: SecretStr = Field(min_length=32, max_length=200)
    password: SecretStr = Field(min_length=12, max_length=1024)


def now():
    return datetime.now(timezone.utc).isoformat()


def hydrate_user(db, email):
    return db.execute('''SELECT u.*, a.password_hash, c.is_active AS company_active
        FROM users u JOIN auth_accounts a ON a.user_id=u.id JOIN companies c ON c.id=u.company_id
        WHERE u.email=:email''', {'email': email}).fetchone()


def record_audit(db, actor, action, company_id=None, entity_id=None, unit_id=None):
    db.execute('''INSERT INTO audit(actor,action,created_at,company_id,entity_id,unit_id)
        VALUES(:actor,:action,:created,:company,:entity,:unit)''', {
        'actor': actor['email'], 'action': action, 'created': now(), 'company': company_id, 'entity': entity_id, 'unit': unit_id,
    })


def user_public(row):
    return {key: row[key] for key in ('id','company_id','name','email','version','created_at')} | {
        'roles': json.loads(row['roles_json']), 'unit_ids': json.loads(row['unit_ids_json']),
        'all_units': bool(row['all_units']), 'is_active': bool(row['is_active']),
        'invitation_pending': not bool(row.get('password_hash')),
    }


def register_foundation(app, storage, actor, superadmin, rate_limit, origin, superadmin_email):
    def company_scope(user, company_id, manage=False, locations=False):
        company = str(company_id)
        if user['role'] != 'superadmin':
            if user.get('company_id') != company:
                raise HTTPException(404, 'Empresa não encontrada.')
            roles = set(user.get('roles', []))
            if manage and 'company_admin' not in roles and not (locations and 'supervisor' in roles):
                raise HTTPException(403, 'Seu perfil não permite esta operação.')
        with storage.connect() as db:
            row = db.execute('SELECT * FROM companies WHERE id=:id', {'id': company}).fetchone()
        if not row:
            raise HTTPException(404, 'Empresa não encontrada.')
        if not row['is_active'] and user['role'] != 'superadmin':
            raise HTTPException(403, 'Empresa suspensa.')
        return company

    def unit_allowed(user, unit_id):
        return user['role'] == 'superadmin' or user['all_units'] or unit_id in user['unit_ids']

    def validate_units(db, company_id, data):
        for unit in data.unit_ids:
            row = db.execute("SELECT id FROM locations WHERE id=:id AND company_id=:company AND kind='unit' AND is_active=1", {'id': str(unit), 'company': company_id}).fetchone()
            if not row:
                raise HTTPException(422, 'Selecione unidades ativas pertencentes à empresa.')

    def invite(db, user_id):
        token = secrets.token_urlsafe(48)
        db.execute('DELETE FROM invitations WHERE user_id=:id', {'id': user_id})
        db.execute('INSERT INTO invitations(token_hash,user_id,expires) VALUES(:token,:user,:expires)', {
            'token': digest(token), 'user': user_id, 'expires': time.time() + 48 * 3600,
        })
        return {'url': origin + '/convite#token=' + token, 'expires_in_hours': 48}

    @app.get('/api/v1/foundation/companies')
    def list_companies(user=Depends(actor)):
        if user['role'] == 'superadmin':
            with storage.connect() as db:
                rows = db.execute('SELECT * FROM companies ORDER BY name,id LIMIT 500').fetchall()
        elif user.get('company_id'):
            with storage.scoped(user, user['company_id']) as db:
                rows = db.execute('SELECT * FROM companies WHERE id=:id', {'id': user['company_id']}).fetchall()
        else:
            raise HTTPException(403, 'Acesso não autorizado.')
        return [dict(row) | {'is_active': bool(row['is_active'])} for row in rows]

    @app.post('/api/v1/foundation/companies', status_code=201)
    def create_company(data: CompanyCreate, user=Depends(superadmin)):
        rate_limit('company-create:' + digest(user['email']), 30, 60)
        values = {'id': str(uuid4()), 'name': data.name, 'slug': data.slug, 'created': now()}
        try:
            with storage.connect() as db:
                db.execute('INSERT INTO companies(id,name,slug,created_at) VALUES(:id,:name,:slug,:created)', values)
                record_audit(db, user, 'company.created', values['id'], values['id'])
                return dict(db.execute('SELECT * FROM companies WHERE id=:id', {'id': values['id']}).fetchone())
        except IntegrityError:
            raise HTTPException(409, 'Identificador de empresa já utilizado.') from None

    @app.put('/api/v1/foundation/companies/{company_id}')
    def update_company(company_id: UUID, data: CompanyUpdate, user=Depends(superadmin)):
        company = company_scope(user, company_id)
        with storage.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            result = db.execute('UPDATE companies SET name=:name,is_active=:active,version=version+1 WHERE id=:id AND version=:version',
                                {'name': data.name, 'active': int(data.is_active), 'id': company, 'version': data.expected_version})
            if result.rowcount != 1:
                raise HTTPException(409, 'A empresa foi alterada. Recarregue antes de salvar.')
            if not data.is_active:
                db.execute('DELETE FROM sessions WHERE email IN (SELECT email FROM users WHERE company_id=:id)', {'id': company})
            record_audit(db, user, 'company.updated' if data.is_active else 'company.suspended', company, company)
            return dict(db.execute('SELECT * FROM companies WHERE id=:id', {'id': company}).fetchone())

    @app.get('/api/v1/foundation/companies/{company_id}/locations')
    def list_locations(company_id: UUID, user=Depends(actor)):
        company = company_scope(user, company_id)
        with storage.scoped(user, company) as db:
            rows = db.execute('SELECT * FROM locations WHERE company_id=:company ORDER BY created_at,id LIMIT 5000', {'company': company}).fetchall()
        return [dict(row) | {'is_active': bool(row['is_active'])} for row in rows if unit_allowed(user, row['unit_id'])]

    @app.post('/api/v1/foundation/companies/{company_id}/locations', status_code=201)
    def create_location(company_id: UUID, data: LocationCreate, user=Depends(actor)):
        company = company_scope(user, company_id, manage=True, locations=True)
        identifier = str(uuid4())
        with storage.scoped(user, company) as db:
            db.execute('BEGIN IMMEDIATE')
            parent = None
            if data.kind == 'unit':
                if data.parent_id:
                    raise HTTPException(422, 'Uma unidade não pode ter local superior.')
                if not unit_allowed(user, identifier):
                    raise HTTPException(403, 'Criar unidades exige acesso a todas as unidades.')
                unit_id, location_timezone = identifier, data.timezone
            else:
                parent = db.execute('SELECT * FROM locations WHERE company_id=:company AND id=:id', {'company': company, 'id': str(data.parent_id)}).fetchone()
                if not parent or not unit_allowed(user, parent['unit_id']):
                    raise HTTPException(404, 'Local superior não encontrado.')
                expected = {'building': 'unit', 'floor': 'building', 'environment': 'floor'}[data.kind]
                if parent['kind'] != expected:
                    raise HTTPException(422, 'Hierarquia inválida. Use unidade → prédio → andar → ambiente.')
                if not parent['is_active']:
                    raise HTTPException(409, 'O local superior está inativo.')
                unit_id, location_timezone = parent['unit_id'], parent['timezone']
            values = {'id': identifier, 'company': company, 'unit': unit_id, 'parent': parent['id'] if parent else None,
                      'name': data.name, 'kind': data.kind, 'criticality': data.criticality, 'timezone': location_timezone, 'created': now()}
            db.execute('''INSERT INTO locations(id,company_id,unit_id,parent_id,name,kind,criticality,timezone,created_at)
                VALUES(:id,:company,:unit,:parent,:name,:kind,:criticality,:timezone,:created)''', values)
            record_audit(db, user, 'location.created', company, identifier, unit_id)
            return dict(db.execute('SELECT * FROM locations WHERE id=:id AND company_id=:company', {'id': identifier, 'company': company}).fetchone())

    @app.put('/api/v1/foundation/companies/{company_id}/locations/{location_id}')
    def update_location(company_id: UUID, location_id: UUID, data: LocationUpdate, user=Depends(actor)):
        company = company_scope(user, company_id, manage=True, locations=True)
        with storage.scoped(user, company) as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM locations WHERE company_id=:company AND id=:id', {'company': company, 'id': str(location_id)}).fetchone()
            if not row or not unit_allowed(user, row['unit_id']):
                raise HTTPException(404, 'Local não encontrado.')
            if not data.is_active and db.execute('SELECT id FROM locations WHERE company_id=:company AND parent_id=:parent AND is_active=1 LIMIT 1', {'company': company, 'parent': row['id']}).fetchone():
                raise HTTPException(409, 'Inative os locais filhos antes de inativar este local.')
            if data.is_active and row['parent_id']:
                parent = db.execute('SELECT is_active FROM locations WHERE company_id=:company AND id=:id', {'company': company, 'id': row['parent_id']}).fetchone()
                if not parent or not parent['is_active']:
                    raise HTTPException(409, 'Ative o local superior primeiro.')
            result = db.execute('''UPDATE locations SET name=:name,criticality=:criticality,is_active=:active,version=version+1
                WHERE company_id=:company AND id=:id AND version=:version''', {
                'name': data.name, 'criticality': data.criticality, 'active': int(data.is_active),
                'company': company, 'id': str(location_id), 'version': data.expected_version,
            })
            if result.rowcount != 1:
                raise HTTPException(409, 'O local foi alterado. Recarregue antes de salvar.')
            record_audit(db, user, 'location.updated', company, row['id'], row['unit_id'])
            return dict(db.execute('SELECT * FROM locations WHERE id=:id AND company_id=:company', {'id': row['id'], 'company': company}).fetchone())

    @app.get('/api/v1/foundation/companies/{company_id}/users')
    def list_users(company_id: UUID, user=Depends(actor)):
        company = company_scope(user, company_id, manage=True)
        with storage.connect() as db:
            rows = db.execute('''SELECT u.*, a.password_hash FROM users u JOIN auth_accounts a ON a.user_id=u.id
                WHERE u.company_id=:company ORDER BY u.name,u.id LIMIT 1000''', {'company': company}).fetchall()
        return [user_public(row) for row in rows]

    @app.post('/api/v1/foundation/companies/{company_id}/users', status_code=201)
    def create_user(company_id: UUID, data: UserCreate, user=Depends(actor)):
        company = company_scope(user, company_id, manage=True)
        rate_limit('user-create:' + digest(user['email']), 30, 60)
        account_email = str(data.email).lower()
        if account_email == superadmin_email.lower():
            raise HTTPException(409, 'Este e-mail não está disponível para cadastro.')
        identifier = str(uuid4())
        try:
            with storage.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                validate_units(db, company, data)
                db.execute('''INSERT INTO users(id,company_id,name,email,roles_json,unit_ids_json,all_units,created_at)
                    VALUES(:id,:company,:name,:email,:roles,:units,:all_units,:created)''', {
                    'id': identifier, 'company': company, 'name': data.name, 'email': account_email,
                    'roles': json.dumps(data.roles), 'units': json.dumps([str(unit) for unit in data.unit_ids]),
                    'all_units': int(data.all_units), 'created': now(),
                })
                db.execute('INSERT INTO auth_accounts(user_id) VALUES(:id)', {'id': identifier})
                invitation = invite(db, identifier)
                record_audit(db, user, 'user.invited', company, identifier)
                row = hydrate_user(db, account_email)
                return {'user': user_public(row), 'invitation': invitation}
        except IntegrityError:
            raise HTTPException(409, 'Este e-mail não está disponível para cadastro.') from None

    @app.put('/api/v1/foundation/companies/{company_id}/users/{user_id}')
    def update_user(company_id: UUID, user_id: UUID, data: UserUpdate, user=Depends(actor)):
        company = company_scope(user, company_id, manage=True)
        with storage.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT u.*, a.password_hash FROM users u JOIN auth_accounts a ON a.user_id=u.id WHERE u.company_id=:company AND u.id=:id', {'company': company, 'id': str(user_id)}).fetchone()
            if not row:
                raise HTTPException(404, 'Usuário não encontrado.')
            validate_units(db, company, data)
            removing_admin = row['is_active'] and row['password_hash'] and 'company_admin' in json.loads(row['roles_json']) and (not data.is_active or 'company_admin' not in data.roles)
            if removing_admin:
                peers = db.execute('SELECT u.roles_json FROM users u JOIN auth_accounts a ON a.user_id=u.id WHERE u.company_id=:company AND u.id<>:id AND u.is_active=1 AND a.password_hash IS NOT NULL', {'company': company, 'id': row['id']}).fetchall()
                if not any('company_admin' in json.loads(peer['roles_json']) for peer in peers):
                    raise HTTPException(409, 'Mantenha pelo menos um administrador ativo com convite aceito.')
            result = db.execute('''UPDATE users SET name=:name,roles_json=:roles,unit_ids_json=:units,all_units=:all_units,is_active=:active,version=version+1
                WHERE company_id=:company AND id=:id AND version=:version''', {
                'name': data.name, 'roles': json.dumps(data.roles), 'units': json.dumps([str(unit) for unit in data.unit_ids]),
                'all_units': int(data.all_units), 'active': int(data.is_active), 'company': company, 'id': row['id'], 'version': data.expected_version,
            })
            if result.rowcount != 1:
                raise HTTPException(409, 'O usuário foi alterado. Recarregue antes de salvar.')
            # Revoga sessões em qualquer alteração de acesso, inclusive redução de escopo.
            db.execute('DELETE FROM sessions WHERE email=:email', {'email': row['email']})
            if not data.is_active:
                db.execute('DELETE FROM invitations WHERE user_id=:id', {'id': row['id']})
            record_audit(db, user, 'user.access_updated', company, row['id'])
            return user_public(hydrate_user(db, row['email']))

    @app.post('/api/v1/foundation/companies/{company_id}/users/{user_id}/invitation')
    def reissue_invitation(company_id: UUID, user_id: UUID, user=Depends(actor)):
        company = company_scope(user, company_id, manage=True)
        rate_limit('invite:' + digest(user['email']), 10, 60)
        with storage.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT u.id,a.password_hash FROM users u JOIN auth_accounts a ON a.user_id=u.id WHERE u.id=:id AND u.company_id=:company AND u.is_active=1', {'id': str(user_id), 'company': company}).fetchone()
            if not row:
                raise HTTPException(404, 'Usuário ativo não encontrado.')
            if row['password_hash']:
                raise HTTPException(409, 'O convite deste usuário já foi aceito.')
            invitation = invite(db, row['id'])
            record_audit(db, user, 'user.invitation_reissued', company, row['id'])
            return invitation

    @app.post('/api/v1/public/invitations/accept')
    def accept_invitation(data: AcceptInvitation, request: Request):
        rate_limit('accept-ip:' + digest(request.client.host if request.client else 'local'), 10, 900)
        token_hash = digest(data.token.get_secret_value())
        rate_limit('accept-token:' + token_hash, 5, 900)
        hashed = password_hash(data.password.get_secret_value())
        with storage.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('''SELECT i.*,u.email,u.company_id,u.is_active,c.is_active AS company_active,a.password_hash
                FROM invitations i JOIN users u ON u.id=i.user_id JOIN companies c ON c.id=u.company_id
                JOIN auth_accounts a ON a.user_id=u.id WHERE i.token_hash=:token''', {'token': token_hash}).fetchone()
            if not row or row['used_at'] or row['expires'] < time.time() or not row['is_active'] or not row['company_active'] or row['password_hash']:
                raise HTTPException(400, 'Convite inválido, expirado ou já utilizado. Solicite um novo convite ao administrador.')
            db.execute('UPDATE invitations SET used_at=:used WHERE token_hash=:token', {'used': now(), 'token': token_hash})
            db.execute('UPDATE auth_accounts SET password_hash=:password WHERE user_id=:id', {'password': hashed, 'id': row['user_id']})
            record_audit(db, {'email': row['email']}, 'user.invitation_accepted', row['company_id'], row['user_id'])
        return {'message': 'Acesso ativado. Entre com o e-mail do convite e sua nova senha.'}

    @app.get('/api/v1/foundation/companies/{company_id}/audit')
    def list_audit(company_id: UUID, user=Depends(actor)):
        company = company_scope(user, company_id)
        if user['role'] != 'superadmin' and not set(user['roles']).intersection({'company_admin','auditor','manager'}):
            raise HTTPException(403, 'Seu perfil não permite consultar a auditoria.')
        with storage.scoped(user, company) as db:
            rows = db.execute('SELECT * FROM audit WHERE company_id=:company ORDER BY id DESC LIMIT 100', {'company': company}).fetchall()
        return [dict(row) for row in rows if not row['unit_id'] or unit_allowed(user, row['unit_id'])]
