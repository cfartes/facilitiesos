"""Migrações incrementais; não recria tabelas ou elimina dados existentes."""
from sqlalchemy import Column, Float, ForeignKey, ForeignKeyConstraint, Integer, MetaData, String, Table, Text, UniqueConstraint, inspect, text

metadata = MetaData()
versions = Table('schema_versions', metadata, Column('version', String(20), primary_key=True))
configuration = Table('configuration', metadata,
    Column('id', Integer, primary_key=True), Column('version', Integer, nullable=False, server_default='0'),
    Column('openwa_key', Text, nullable=False, server_default=''), Column('resend_key', Text, nullable=False, server_default=''),
    Column('email_from', Text, nullable=False, server_default=''), Column('updated_at', Text))
sessions = Table('sessions', metadata,
    Column('token_hash', Text, primary_key=True), Column('csrf_hash', Text, nullable=False),
    Column('email', Text, nullable=False), Column('role', Text, nullable=False), Column('expires', Float, nullable=False),
    Column('credential_hash', Text, nullable=False))
audit = Table('audit', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True), Column('actor', Text, nullable=False),
    Column('action', Text, nullable=False), Column('created_at', Text, nullable=False),
    Column('company_id', String(36)), Column('unit_id', String(36)), Column('entity_id', String(36)))
rate_limits = Table('rate_limits', metadata,
    Column('identity', Text, primary_key=True), Column('started', Float, nullable=False), Column('attempts', Integer, nullable=False))
companies = Table('companies', metadata,
    Column('id', String(36), primary_key=True), Column('name', String(160), nullable=False),
    Column('slug', String(60), unique=True, nullable=False), Column('is_active', Integer, nullable=False, server_default='1'),
    Column('version', Integer, nullable=False, server_default='1'), Column('created_at', Text, nullable=False))
locations = Table('locations', metadata,
    Column('id', String(36), primary_key=True), Column('company_id', String(36), ForeignKey('companies.id'), nullable=False),
    Column('unit_id', String(36), nullable=False), Column('parent_id', String(36)),
    Column('kind', String(20), nullable=False), Column('name', String(160), nullable=False),
    Column('criticality', String(20), nullable=False), Column('timezone', String(60), nullable=False, server_default='America/Sao_Paulo'),
    Column('is_active', Integer, nullable=False, server_default='1'), Column('version', Integer, nullable=False, server_default='1'),
    Column('created_at', Text, nullable=False), UniqueConstraint('company_id', 'id'),
    ForeignKeyConstraint(['company_id','parent_id'], ['locations.company_id','locations.id']),
    ForeignKeyConstraint(['company_id','unit_id'], ['locations.company_id','locations.id']))
users = Table('users', metadata,
    Column('id', String(36), primary_key=True), Column('company_id', String(36), ForeignKey('companies.id'), nullable=False),
    Column('name', String(160), nullable=False), Column('email', String(254), unique=True, nullable=False),
    Column('roles_json', Text, nullable=False), Column('unit_ids_json', Text, nullable=False),
    Column('all_units', Integer, nullable=False), Column('is_active', Integer, nullable=False, server_default='1'),
    Column('version', Integer, nullable=False, server_default='1'), Column('created_at', Text, nullable=False))
accounts = Table('auth_accounts', metadata, Column('user_id', String(36), ForeignKey('users.id'), primary_key=True), Column('password_hash', Text))
invitations = Table('invitations', metadata,
    Column('token_hash', Text, primary_key=True), Column('user_id', String(36), ForeignKey('users.id'), nullable=False),
    Column('expires', Float, nullable=False), Column('used_at', Text))


def migrate_schema(engine):
    with engine.begin() as connection:
        if engine.dialect.name == 'postgresql':
            connection.execute(text('SELECT pg_advisory_xact_lock(741000)'))
        metadata.create_all(connection)
        columns = {item['name'] for item in inspect(connection).get_columns('audit')}
        for name in ('company_id', 'unit_id', 'entity_id'):
            if name not in columns:
                connection.execute(text(f'ALTER TABLE audit ADD COLUMN {name} VARCHAR(36)'))
        connection.execute(text('INSERT INTO configuration(id) VALUES(1) ON CONFLICT(id) DO NOTHING'))
        for version in ('0001', '0002'):
            connection.execute(text('INSERT INTO schema_versions(version) VALUES(:version) ON CONFLICT(version) DO NOTHING'), {'version': version})
        if engine.dialect.name == 'postgresql':
            apply_policies(connection)


def apply_policies(connection):
    connection.execute(text('REVOKE CREATE ON SCHEMA public FROM PUBLIC'))
    platform_tables = ('configuration','sessions','rate_limits','auth_accounts','invitations')
    tenant_tables = ('companies','users','locations','audit')
    connection.execute(text('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC'))
    connection.execute(text('GRANT USAGE ON SCHEMA public TO facilities_app,facilities_platform'))
    connection.execute(text('GRANT SELECT ON schema_versions TO facilities_app,facilities_platform'))
    for table in platform_tables + tenant_tables:
        connection.execute(text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
        connection.execute(text(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'))
        connection.execute(text(f'DROP POLICY IF EXISTS platform_access ON {table}'))
        connection.execute(text(f'CREATE POLICY platform_access ON {table} TO facilities_platform USING (true) WITH CHECK (true)'))
        connection.execute(text(f'GRANT SELECT,INSERT,UPDATE,DELETE ON {table} TO facilities_platform'))
    for table in tenant_tables:
        scope = "id = current_setting('app.company_id', true)" if table == 'companies' else "company_id = current_setting('app.company_id', true)"
        if table in ('locations', 'audit'):
            scope += " AND (unit_id IS NULL OR current_setting('app.all_units', true) = 'true' OR unit_id = ANY(string_to_array(current_setting('app.unit_ids', true), ',')))"
        connection.execute(text(f'DROP POLICY IF EXISTS tenant_scope ON {table}'))
        connection.execute(text(f'CREATE POLICY tenant_scope ON {table} TO facilities_app USING ({scope}) WITH CHECK ({scope})'))
    connection.execute(text('GRANT SELECT ON companies,users,locations,audit TO facilities_app'))
    connection.execute(text('GRANT INSERT,UPDATE ON locations TO facilities_app'))
    connection.execute(text('GRANT INSERT ON audit TO facilities_app'))
    connection.execute(text('GRANT USAGE ON SEQUENCE audit_id_seq TO facilities_app,facilities_platform'))
