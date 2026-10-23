import sqlite3

import pytest
from sqlalchemy import create_engine, text

from backend import providers
from backend.schema import migrate_schema
from backend.tests.test_foundation import foundation, company, company_data, company_update, login, PASSWORD


def test_full_registration_and_initial_administrator(foundation):
    client, storage = foundation
    row = company(client)
    assert row['name'] == row['trade_name'] == 'Empresa Alpha'
    assert row['corporate_name'] == 'Empresa Alpha LTDA'
    assert row['cnpj'] == '11222333000181'
    assert row['contact_phone'] == '+5511999999999'
    assert row['postal_code'] == '01001000'
    assert row['address_complement'] == ''
    assert 'plan_id' not in row and PASSWORD not in str(row)
    with storage.connect() as db:
        account = db.execute('SELECT password_hash FROM auth_accounts').fetchone()
        assert account['password_hash'] != PASSWORD
        assert PASSWORD not in str(db.execute('SELECT * FROM audit').fetchall())
    principal = login(client, 'owneralpha@example.com')
    assert principal['roles'] == ['company_admin'] and principal['all_units'] is True
    assert principal['company_id'] == row['id']


def test_duplicate_admin_rolls_back_entire_company(foundation):
    client, storage = foundation
    company(client)
    payload = company_data('Empresa Beta', 'beta')
    payload['admin']['email'] = 'owneralpha@example.com'
    result = client.post('/api/v1/foundation/companies', json=payload)
    assert result.status_code == 409
    with storage.connect() as db:
        assert len(db.execute('SELECT id FROM companies').fetchall()) == 1
        assert len(db.execute('SELECT user_id FROM auth_accounts').fetchall()) == 1


def test_invalid_document_contact_address_slug_and_plan(foundation):
    client, storage = foundation
    for changes in [
        {'cnpj': '11.222.333/0001-00'}, {'cnpj': '111.111.111-11'},
        {'contact_phone': '123'}, {'postal_code': '1234567x'}, {'state': 'ZZ'},
        {'slug': 'nova-empresa'}, {'operational_profile': 'tourism'}, {'plan_id': 'unused'},
        {'address': ''}, {'corporate_name': ''},
    ]:
        result = client.post('/api/v1/foundation/companies', json=company_data() | changes)
        assert result.status_code == 422, (changes, result.text)
        assert PASSWORD not in result.text
    payload = company_data()
    payload['admin']['password'] = 'all-lowercase-password'
    assert client.post('/api/v1/foundation/companies', json=payload).status_code == 422
    with storage.connect() as db:
        assert db.execute('SELECT id FROM companies').fetchone() is None


def test_edit_persists_details_without_changing_admin(foundation):
    client, _ = foundation
    row = company(client)
    payload = company_update(row, corporate_name='Nova Razão Social LTDA', slug='alphanova', address_complement='Sala 02')
    result = client.put(f"/api/v1/foundation/companies/{row['id']}", json=payload)
    assert result.status_code == 200
    assert result.json()['corporate_name'] == payload['corporate_name']
    assert result.json()['address_complement'] == 'Sala 02'
    assert result.json()['slug'] == 'alphanova'
    principal = login(client, 'owneralpha@example.com')
    assert principal['roles'] == ['company_admin']


def test_requester_does_not_receive_registration_documents(foundation):
    from backend.tests.test_foundation import member, accept
    client, _ = foundation
    row = company(client)
    invited = member(client, row['id'])
    accept(client, invited)
    login(client, 'member@example.com')
    response = client.get('/api/v1/foundation/companies')
    assert response.status_code == 200
    assert 'cnpj' not in response.json()[0]
    assert 'contact_phone' not in response.json()[0]
    assert row['cnpj'] not in response.text


def test_postal_lookup_is_backend_only_and_can_fail_safely(foundation, monkeypatch):
    client, _ = foundation
    calls = []
    def lookup(url, headers):
        calls.append(url)
        assert url == 'https://viacep.com.br/ws/01001000/json/'
        assert headers == {}
        return {'logradouro': 'Praça da Sé', 'bairro': 'Sé', 'localidade': 'São Paulo', 'uf': 'SP'}
    monkeypatch.setattr(providers, 'request_provider', lookup)
    assert client.get('/api/v1/foundation/postal-code/invalid').status_code == 422
    assert not calls
    result = client.get('/api/v1/foundation/postal-code/01001000')
    assert result.json()['city'] == 'São Paulo'
    assert len(calls) == 1
    monkeypatch.setattr(providers, 'request_provider', lambda *args: {'erro': True})
    assert client.get('/api/v1/foundation/postal-code/01001000').status_code == 404


def test_migration_0003_preserves_legacy_company(tmp_path):
    path = tmp_path / 'legacy-company.db'
    with sqlite3.connect(path) as db:
        db.executescript('''CREATE TABLE companies (
            id VARCHAR(36) PRIMARY KEY,name VARCHAR(160) NOT NULL,slug VARCHAR(60) NOT NULL UNIQUE,
            is_active INTEGER NOT NULL DEFAULT 1,version INTEGER NOT NULL DEFAULT 1,created_at TEXT NOT NULL);
            INSERT INTO companies(id,name,slug,version,created_at) VALUES('legacy','Empresa Anterior','empresa-anterior',7,'2026-10-23');''')
    engine = create_engine('sqlite:///' + str(path))
    try:
        migrate_schema(engine)
        with engine.connect() as db:
            row = db.execute(text('SELECT * FROM companies')).mappings().one()
            assert row['name'] == row['corporate_name'] == 'Empresa Anterior'
            assert row['slug'] == 'empresa-anterior' and row['version'] == 7
            assert row['cnpj'] is None and row['contact_phone'] is None
    finally:
        engine.dispose()
