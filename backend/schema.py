"""Migrações incrementais; não recria tabelas ou elimina dados existentes."""
from sqlalchemy import Column, Float, ForeignKey, ForeignKeyConstraint, Index, Integer, MetaData, String, Table, Text, UniqueConstraint, inspect, text

metadata = MetaData()
versions = Table('schema_versions', metadata, Column('version', String(20), primary_key=True))
configuration = Table('configuration', metadata,
    Column('id', Integer, primary_key=True), Column('version', Integer, nullable=False, server_default='0'),
    Column('openwa_key', Text, nullable=False, server_default=''), Column('resend_key', Text, nullable=False, server_default=''),
    Column('email_from', Text, nullable=False, server_default=''), Column('updated_at', Text),
    Column('invitation_email_enabled', Integer, nullable=False, server_default='0'),
    Column('password_reset_enabled', Integer, nullable=False, server_default='0'))
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
    Column('version', Integer, nullable=False, server_default='1'), Column('created_at', Text, nullable=False),
    Column('corporate_name', String(150)), Column('cnpj', String(14)), Column('contact_phone', String(20)),
    Column('address', String(250)), Column('address_number', String(30)), Column('address_complement', String(150)),
    Column('neighborhood', String(100)), Column('city', String(100)), Column('state', String(2)),
    Column('postal_code', String(8)), Column('operational_profile', String(20)))
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
Index('uq_locations_company_unit_id', locations.c.company_id, locations.c.unit_id, locations.c.id, unique=True)
password_resets = Table('password_resets', metadata,
    Column('user_id', String(36), primary_key=True), Column('company_id', String(36), nullable=False),
    Column('token_hash', String(64), nullable=False, unique=True), Column('credential_hash', String(64), nullable=False),
    Column('expires', Float, nullable=False), Column('used_at', Text),
    ForeignKeyConstraint(['company_id','user_id'], ['users.company_id','users.id']))
email_outbox = Table('email_outbox', metadata,
    # invitation_hash é o nome legado do identificador de token/evento; kind separa suas finalidades.
    Column('id', String(36), primary_key=True), Column('company_id', String(36), nullable=False),
    Column('user_id', String(36), nullable=False), Column('invitation_hash', String(64), nullable=False, unique=True),
    Column('kind', String(30), nullable=False, server_default='invitation'),
    Column('payload', Text, nullable=False), Column('credential_hash', String(64), nullable=False),
    Column('status', String(20), nullable=False), Column('attempts', Integer, nullable=False, server_default='0'),
    Column('expires', Float, nullable=False), Column('next_attempt_at', Float, nullable=False),
    Column('first_attempt_at', Float), Column('lease', String(36)), Column('lease_until', Float),
    Column('last_error', String(300), nullable=False, server_default=''), Column('provider_id', String(200)),
    Column('created_at', Text, nullable=False), Column('updated_at', Text, nullable=False),
    ForeignKeyConstraint(['company_id','user_id'], ['users.company_id','users.id']))
Index('ix_email_outbox_due', email_outbox.c.status, email_outbox.c.next_attempt_at)
Index('ix_email_outbox_user', email_outbox.c.company_id, email_outbox.c.user_id, email_outbox.c.created_at)
Index('uq_users_company_id', users.c.company_id, users.c.id, unique=True)
from backend.operation_schema import register_tables, apply_operation_policies
register_tables(metadata)


def migrate_schema(engine):
    with engine.begin() as connection:
        if engine.dialect.name == 'postgresql':
            connection.execute(text('SELECT pg_advisory_xact_lock(741000)'))
        # Índices das tabelas anteriores devem existir antes das novas FKs compostas.
        existing = set(inspect(connection).get_table_names())
        for table in (locations, users, metadata.tables['occurrences']):
            if table.name in existing:
                for index in table.indexes:
                    index.create(connection, checkfirst=True)
        metadata.create_all(connection)
        if 'invitation_email_enabled' not in {item['name'] for item in inspect(connection).get_columns('configuration')}:
            connection.execute(text('ALTER TABLE configuration ADD COLUMN invitation_email_enabled INTEGER NOT NULL DEFAULT 0'))
        if 'password_reset_enabled' not in {item['name'] for item in inspect(connection).get_columns('configuration')}:
            connection.execute(text('ALTER TABLE configuration ADD COLUMN password_reset_enabled INTEGER NOT NULL DEFAULT 0'))
        if 'kind' not in {item['name'] for item in inspect(connection).get_columns('email_outbox')}:
            connection.execute(text("ALTER TABLE email_outbox ADD COLUMN kind VARCHAR(30) NOT NULL DEFAULT 'invitation'"))
        columns = {item['name'] for item in inspect(connection).get_columns('audit')}
        for name in ('company_id', 'unit_id', 'entity_id'):
            if name not in columns:
                connection.execute(text(f'ALTER TABLE audit ADD COLUMN {name} VARCHAR(36)'))
        connection.execute(text('INSERT INTO configuration(id) VALUES(1) ON CONFLICT(id) DO NOTHING'))
        company_columns = {item['name'] for item in inspect(connection).get_columns('companies')}
        # Campos novos são anuláveis para preservar cadastros anteriores incompletos.
        from backend.company_details import DETAIL_FIELDS
        for name in DETAIL_FIELDS:
            if name not in company_columns:
                datatype = companies.c[name].type.compile(dialect=connection.dialect)
                connection.execute(text(f'ALTER TABLE companies ADD COLUMN {name} {datatype}'))
        connection.execute(text('UPDATE companies SET corporate_name=name WHERE corporate_name IS NULL'))
        for version in ('0001', '0002', '0003', '0004', '0005', '0006', '0007', '0008'):
            connection.execute(text('INSERT INTO schema_versions(version) VALUES(:version) ON CONFLICT(version) DO NOTHING'), {'version': version})
        if engine.dialect.name == 'postgresql':
            apply_policies(connection)
            apply_operation_policies(connection)


def apply_policies(connection):
    connection.execute(text('REVOKE CREATE ON SCHEMA public FROM PUBLIC'))
    platform_tables = ('configuration','sessions','rate_limits','auth_accounts','invitations','email_outbox','password_resets')
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
