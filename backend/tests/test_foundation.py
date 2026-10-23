import json
import os
import sqlite3
import time
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from backend.main import create_app
from backend.schema import migrate_schema
from backend.security import password_hash

ORIGIN = 'http://127.0.0.1:5180'
PASSWORD = 'Valid-test-password-123!'


@pytest.fixture(params=['sqlite', 'postgres'])
def foundation(request, tmp_path, monkeypatch):
    owner = os.getenv('FACILITIES_MIGRATION_DATABASE_URL')
    if request.param == 'postgres' and not owner:
        pytest.skip('PostgreSQL indisponível: execute python -m backend.dev_database.')
    cleanup_engine = None
    test_db = None
    if request.param == 'postgres':
        test_db = 'facilities_test_' + uuid4().hex
        cleanup_engine = create_engine(owner, isolation_level='AUTOCOMMIT', hide_parameters=True)
        with cleanup_engine.connect() as db:
            db.execute(text(f'CREATE DATABASE {test_db}'))
        migration_url = make_url(owner).set(database=test_db)
        migration_engine = create_engine(migration_url, hide_parameters=True)
        migrate_schema(migration_engine)
        migration_engine.dispose()
        for name in ('FACILITIES_PLATFORM_DATABASE_URL','FACILITIES_DATABASE_URL'):
            monkeypatch.setenv(name, make_url(os.environ[name]).set(database=test_db).render_as_string(hide_password=False))
        app = create_app(admin_email='admin@example.com', admin_hash=password_hash(PASSWORD), encryption_key=Fernet.generate_key(), origin=ORIGIN)
    else:
        app = create_app(tmp_path / 'foundation.db', 'admin@example.com', password_hash(PASSWORD), Fernet.generate_key(), ORIGIN)
    try:
        with TestClient(app, base_url=ORIGIN, headers={'Origin': ORIGIN}) as client:
            login(client, 'admin@example.com')
            yield client, app.state.storage
    finally:
        if cleanup_engine:
            # Somente o banco aleatório criado por este fixture; nunca o banco facilities.
            assert test_db and test_db.startswith('facilities_test_') and len(test_db) == 48
            with cleanup_engine.connect() as db:
                db.execute(text(f'DROP DATABASE {test_db} WITH (FORCE)'))
            cleanup_engine.dispose()


def login(client, email, password=PASSWORD):
    result = client.post('/api/v1/auth/login', json={'email': email, 'password': password})
    assert result.status_code == 200, result.text
    client.headers['X-CSRF-Token'] = client.cookies.get('facilities_csrf')
    return result.json()


def company_data(name='Empresa Alpha', slug='alpha'):
    return {'trade_name': name, 'corporate_name': name + ' LTDA', 'slug': slug,
            'cnpj': '11.222.333/0001-81', 'contact_phone': '(11) 99999-9999',
            'address': 'Rua de Testes', 'address_number': '100', 'address_complement': '',
            'neighborhood': 'Centro', 'city': 'São Paulo', 'state': 'SP', 'postal_code': '01001-000',
            'operational_profile': 'office', 'admin': {'full_name': 'Administrador Inicial',
            'email': 'owner' + slug.replace('-', '') + '@example.com', 'password': PASSWORD}}


def company_update(row, **changes):
    fields = ('trade_name','corporate_name','slug','cnpj','contact_phone','address','address_number','address_complement','neighborhood','city','state','postal_code','operational_profile')
    return {field: row[field] for field in fields} | {'is_active': bool(row['is_active']), 'expected_version': row['version']} | changes


def company(client, name='Empresa Alpha', slug='alpha'):
    result = client.post('/api/v1/foundation/companies', json=company_data(name, slug))
    assert result.status_code == 201, result.text
    return result.json()


def location(client, company_id, name='Unidade Matriz', kind='unit', parent=None):
    result = client.post(f'/api/v1/foundation/companies/{company_id}/locations', json={'name': name, 'kind': kind, 'parent_id': parent})
    assert result.status_code == 201, result.text
    return result.json()


def member(client, company_id, email='member@example.com', roles=None, unit_ids=None, all_units=True):
    result = client.post(f'/api/v1/foundation/companies/{company_id}/users', json={
        'name': 'Pessoa Convidada', 'email': email, 'roles': roles or ['requester'],
        'all_units': all_units, 'unit_ids': unit_ids or [],
    })
    assert result.status_code == 201, result.text
    return result.json()


def accept(client, invited):
    token = parse_qs(urlsplit(invited['invitation']['url']).fragment)['token'][0]
    result = client.post('/api/v1/public/invitations/accept', json={'token': token, 'password': PASSWORD})
    assert result.status_code == 200, result.text
    return token


def test_company_lifecycle_and_version_conflict(foundation):
    client, _ = foundation
    row = company(client)
    duplicate = client.post('/api/v1/foundation/companies', json=company_data('Duplicada', 'alpha'))
    assert duplicate.status_code == 409
    path = f"/api/v1/foundation/companies/{row['id']}"
    payload = company_update(row, trade_name='Empresa Atualizada', is_active=False)
    assert client.put(path, json=payload).status_code == 200
    assert client.put(path, json=payload).status_code == 409
    assert client.get('/api/v1/foundation/companies').json()[0]['is_active'] is False


def test_hierarchy_and_cross_company_parent(foundation):
    client, _ = foundation
    alpha, beta = company(client), company(client, 'Empresa Beta', 'beta')
    unit = location(client, alpha['id'])
    building = location(client, alpha['id'], 'Prédio Principal', 'building', unit['id'])
    floor = location(client, alpha['id'], 'Primeiro Andar', 'floor', building['id'])
    room = location(client, alpha['id'], 'Sala de Reunião', 'environment', floor['id'])
    assert room['unit_id'] == unit['id']
    assert room['timezone'] == 'America/Sao_Paulo'
    invalid = client.post(f"/api/v1/foundation/companies/{beta['id']}/locations", json={'name': 'Prédio Cruzado', 'kind': 'building', 'parent_id': unit['id']})
    assert invalid.status_code == 404
    wrong_level = client.post(f"/api/v1/foundation/companies/{alpha['id']}/locations", json={'name': 'Sala Inválida', 'kind': 'environment', 'parent_id': unit['id']})
    assert wrong_level.status_code == 422
    update = client.put(f"/api/v1/foundation/companies/{alpha['id']}/locations/{unit['id']}", json={'name': unit['name'], 'criticality': 'medium', 'is_active': False, 'expected_version': 1})
    assert update.status_code == 409


def test_invitation_single_use_and_login(foundation):
    client, storage = foundation
    row = company(client)
    invited = member(client, row['id'])
    token = accept(client, invited)
    replay = client.post('/api/v1/public/invitations/accept', json={'token': token, 'password': PASSWORD})
    assert replay.status_code == 400
    with storage.connect() as db:
        stored = db.execute('SELECT token_hash FROM invitations').fetchone()['token_hash']
        assert stored != token
        assert token not in str(db.execute('SELECT * FROM audit').fetchall())
    principal = login(client, 'member@example.com')
    assert principal['company_id'] == row['id']
    assert principal['roles'] == ['requester']
    assert 'password_hash' not in principal
    assert client.get('/api/v1/nexus/integrations').status_code == 403
    assert client.post('/api/v1/foundation/companies', json=company_data('Intrusa', 'intrusa')).status_code == 403


def test_unit_and_tenant_isolation(foundation):
    client, _ = foundation
    alpha, beta = company(client), company(client, 'Empresa Beta', 'beta')
    unit_a = location(client, alpha['id'], 'Unidade Autorizada')
    unit_b = location(client, alpha['id'], 'Unidade Restrita')
    location(client, beta['id'], 'Unidade de Outra Empresa')
    location(client, alpha['id'], 'Prédio Autorizado', 'building', unit_a['id'])
    invited = member(client, alpha['id'], unit_ids=[unit_a['id']], all_units=False)
    accept(client, invited)
    login(client, 'member@example.com')
    assert len(client.get('/api/v1/foundation/companies').json()) == 1
    visible = client.get(f"/api/v1/foundation/companies/{alpha['id']}/locations").json()
    assert len(visible) == 2
    assert all(item['unit_id'] == unit_a['id'] for item in visible)
    assert client.get(f"/api/v1/foundation/companies/{beta['id']}/locations").status_code == 404
    assert client.get(f"/api/v1/foundation/companies/{alpha['id']}/users").status_code == 403
    assert client.post(f"/api/v1/foundation/companies/{alpha['id']}/locations", json={'name': 'Invasão', 'kind': 'unit'}).status_code == 403


def test_company_admin_can_manage_only_own_company(foundation):
    client, _ = foundation
    alpha, beta = company(client), company(client, 'Empresa Beta', 'beta')
    invited = member(client, alpha['id'], roles=['company_admin'])
    accept(client, invited)
    initial = next(item for item in client.get(f"/api/v1/foundation/companies/{alpha['id']}/users").json() if item['email'] == 'owneralpha@example.com')
    assert client.put(f"/api/v1/foundation/companies/{alpha['id']}/users/{initial['id']}", json={'name': initial['name'], 'roles': ['requester'], 'all_units': True, 'unit_ids': [], 'is_active': False, 'expected_version': 1}).status_code == 200
    login(client, 'member@example.com')
    assert client.get(f"/api/v1/foundation/companies/{alpha['id']}/users").status_code == 200
    assert client.get(f"/api/v1/foundation/companies/{beta['id']}/users").status_code == 404
    own = location(client, alpha['id'])
    assert own['company_id'] == alpha['id']
    path = f"/api/v1/foundation/companies/{alpha['id']}/users/{invited['user']['id']}"
    result = client.put(path, json={'name': 'Administrador', 'roles': ['requester'], 'all_units': True, 'unit_ids': [], 'is_active': True, 'expected_version': 1})
    assert result.status_code == 409


def test_suspension_revokes_access_and_preserves_data(foundation):
    client, storage = foundation
    row = company(client)
    invited = member(client, row['id'])
    accept(client, invited)
    login(client, 'member@example.com')
    token = client.cookies.get('facilities_session')
    login(client, 'admin@example.com')
    result = client.put(f"/api/v1/foundation/companies/{row['id']}", json=company_update(row, is_active=False))
    assert result.status_code == 200
    client.cookies.set('facilities_session', token)
    assert client.get('/api/v1/auth/me').status_code == 401
    assert client.post('/api/v1/auth/login', json={'email': 'member@example.com', 'password': PASSWORD}).status_code == 401
    with storage.connect() as db:
        assert db.execute('SELECT id FROM users').fetchone() is not None


def test_reissued_invitation_invalidates_old_and_expiry(foundation):
    client, storage = foundation
    row = company(client)
    invited = member(client, row['id'])
    old = parse_qs(urlsplit(invited['invitation']['url']).fragment)['token'][0]
    replacement = client.post(f"/api/v1/foundation/companies/{row['id']}/users/{invited['user']['id']}/invitation")
    assert replacement.status_code == 200
    new = parse_qs(urlsplit(replacement.json()['url']).fragment)['token'][0]
    assert old != new
    assert client.post('/api/v1/public/invitations/accept', json={'token': old, 'password': PASSWORD}).status_code == 400
    with storage.connect() as db:
        db.execute('UPDATE invitations SET expires=:expires', {'expires': time.time() - 1})
    assert client.post('/api/v1/public/invitations/accept', json={'token': new, 'password': PASSWORD}).status_code == 400


def test_access_changes_invalidate_sessions(foundation):
    client, _ = foundation
    row = company(client)
    invited = member(client, row['id'])
    accept(client, invited)
    login(client, 'member@example.com')
    token = client.cookies.get('facilities_session')
    login(client, 'admin@example.com')
    result = client.put(f"/api/v1/foundation/companies/{row['id']}/users/{invited['user']['id']}", json={'name': 'Pessoa Atualizada', 'roles': ['auditor'], 'all_units': True, 'unit_ids': [], 'is_active': True, 'expected_version': 1})
    assert result.status_code == 200
    assert 'password_hash' not in result.json()
    client.cookies.set('facilities_session', token)
    assert client.get('/api/v1/auth/me').status_code == 401


def test_supervisor_can_manage_only_assigned_unit(foundation):
    client, _ = foundation
    row = company(client)
    allowed = location(client, row['id'], 'Permitida')
    denied = location(client, row['id'], 'Restrita')
    invited = member(client, row['id'], roles=['supervisor'], all_units=False, unit_ids=[allowed['id']])
    accept(client, invited)
    login(client, 'member@example.com')
    location(client, row['id'], 'Prédio Permitido', 'building', allowed['id'])
    assert client.post(f"/api/v1/foundation/companies/{row['id']}/locations", json={'name': 'Prédio Restrito', 'kind': 'building', 'parent_id': denied['id']}).status_code == 404
    assert client.post(f"/api/v1/foundation/companies/{row['id']}/locations", json={'name': 'Nova Unidade', 'kind': 'unit'}).status_code == 403


def test_units_and_roles_validation(foundation):
    client, _ = foundation
    row = company(client)
    other = company(client, 'Outra Empresa', 'outra')
    unit = location(client, other['id'])
    base = {'name': 'Pessoa', 'email': 'person@example.com', 'roles': ['requester'], 'all_units': False, 'unit_ids': [unit['id']]}
    path = f"/api/v1/foundation/companies/{row['id']}/users"
    assert client.post(path, json=base).status_code == 422
    assert client.post(path, json=base | {'roles': ['superadmin']}).status_code == 422
    assert client.post(path, json=base | {'roles': ['company_admin']}).status_code == 422


def test_audit_scope_and_no_secret_material(foundation):
    client, _ = foundation
    row = company(client)
    unit = location(client, row['id'])
    other_unit = location(client, row['id'], 'Outra Unidade')
    invited = member(client, row['id'], roles=['auditor'], all_units=False, unit_ids=[unit['id']])
    token = accept(client, invited)
    login(client, 'member@example.com')
    response = client.get(f"/api/v1/foundation/companies/{row['id']}/audit")
    assert response.status_code == 200
    assert token not in response.text and PASSWORD not in response.text
    assert all(item['unit_id'] != other_unit['id'] for item in response.json())


def test_postgres_policies_deny_unscoped_and_cross_tenant_sql(foundation):
    client, storage = foundation
    if not storage.postgres:
        pytest.skip('Políticas RLS são verificadas no PostgreSQL real.')
    alpha, beta = company(client), company(client, 'Empresa Beta', 'beta')
    unit_a, unit_b = location(client, alpha['id']), location(client, beta['id'])
    principal = {'role': 'company_user', 'company_id': alpha['id'], 'all_units': True, 'unit_ids': []}
    with storage.tenant.begin() as db:
        assert db.execute(text('SELECT * FROM companies')).fetchall() == []
        assert db.execute(text('SELECT * FROM locations')).fetchall() == []
    with storage.scoped(principal, alpha['id']) as db:
        rows = db.execute('SELECT * FROM locations').fetchall()
        assert [item['id'] for item in rows] == [unit_a['id']]
    # Nova transação em conexão reutilizada não herda o escopo anterior.
    with storage.tenant.begin() as db:
        assert db.execute(text('SELECT * FROM locations')).fetchall() == []
    with pytest.raises(DBAPIError):
        with storage.scoped(principal, alpha['id']) as db:
            db.execute('INSERT INTO locations(id,company_id,unit_id,kind,name,criticality,timezone,created_at) VALUES(:id,:company,:unit,:kind,:name,:criticality,:timezone,:created)', {
                'id': str(uuid4()), 'company': beta['id'], 'unit': unit_b['id'], 'kind': 'building', 'name': 'Intrusa', 'criticality': 'medium', 'timezone': 'America/Sao_Paulo', 'created': '2026-10-23',
            })
    with pytest.raises(DBAPIError):
        with storage.tenant.begin() as db:
            db.execute(text('SELECT * FROM configuration'))
    with storage.platform.begin() as db:
        protected = db.execute(text("SELECT count(*) FROM pg_class WHERE relname IN ('configuration','sessions','audit','rate_limits','companies','users','auth_accounts','invitations','locations') AND relrowsecurity AND relforcerowsecurity")).scalar_one()
        assert protected == 9


def test_reapplying_migrations_preserves_existing_records(foundation):
    client, storage = foundation
    row = company(client)
    place = location(client, row['id'])
    if storage.postgres:
        owner = make_url(os.environ['FACILITIES_MIGRATION_DATABASE_URL']).set(database=storage.platform.url.database)
        engine = create_engine(owner, hide_parameters=True)
    else:
        engine = storage.platform
    try:
        migrate_schema(engine)
        result = client.get(f"/api/v1/foundation/companies/{row['id']}/locations")
        assert result.status_code == 200
        assert [item['id'] for item in result.json()] == [place['id']]
    finally:
        if engine is not storage.platform:
            engine.dispose()


def test_legacy_sqlite_upgrade_preserves_settings_and_audit(tmp_path):
    path = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(path) as db:
        db.executescript('''
            CREATE TABLE configuration(id INTEGER PRIMARY KEY,version INTEGER NOT NULL DEFAULT 0,
                openwa_key TEXT NOT NULL DEFAULT '',resend_key TEXT NOT NULL DEFAULT '',
                email_from TEXT NOT NULL DEFAULT '',updated_at TEXT);
            INSERT INTO configuration(id,version,email_from) VALUES(1,7,'existing@example.com');
            CREATE TABLE audit(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,action TEXT NOT NULL,created_at TEXT NOT NULL);
            INSERT INTO audit(actor,action,created_at) VALUES('existing@example.com','integrations.updated','2026-10-23');
        ''')
    engine = create_engine('sqlite:///' + str(path), hide_parameters=True)
    try:
        migrate_schema(engine)
        with engine.connect() as db:
            assert db.execute(text('SELECT email_from,version FROM configuration')).one() == ('existing@example.com', 7)
            assert db.execute(text('SELECT action,company_id FROM audit')).one() == ('integrations.updated', None)
            assert db.execute(text('SELECT count(*) FROM schema_versions')).scalar_one() == 5
    finally:
        engine.dispose()
