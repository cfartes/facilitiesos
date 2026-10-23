"""Contatos sem login, conversa transitória e entrega transacional do WhatsApp."""
from contextlib import contextmanager

from sqlalchemy import Column, Float, ForeignKey, Index, Integer, MetaData, String, Table, Text, UniqueConstraint, inspect, text
from sqlalchemy.schema import CreateTable

PRIVATE_TABLES = ('whatsapp_contacts', 'whatsapp_conversations', 'whatsapp_events', 'whatsapp_outbox')


def register_tables(metadata):
    Table('whatsapp_contacts', metadata,
          Column('id', String(36), primary_key=True), Column('company_id', String(36), ForeignKey('companies.id'), nullable=False),
          Column('phone_hash', String(64), nullable=False), Column('phone', Text, nullable=False),
          Column('name', String(160), nullable=False), Column('created_at', Text, nullable=False),
          UniqueConstraint('company_id','phone_hash'), UniqueConstraint('company_id','id'))
    Table('whatsapp_conversations', metadata,
          Column('company_id', String(36), ForeignKey('companies.id'), primary_key=True), Column('phone_hash', String(64), primary_key=True),
          Column('draft', Text, nullable=False), Column('expires', Float, nullable=False), Column('last_event_at', Float, nullable=False))
    Table('whatsapp_events', metadata,
          Column('id', String(64), primary_key=True), Column('company_id', String(36), ForeignKey('companies.id'), nullable=False),
          Column('session_id', String(36), nullable=False), Column('created_at', Float, nullable=False))
    Table('whatsapp_outbox', metadata,
          Column('id', String(36), primary_key=True), Column('company_id', String(36), ForeignKey('companies.id'), nullable=False),
          Column('session_id', String(36), nullable=False), Column('phone_hash', String(64), nullable=False),
          Column('event_id', String(64), ForeignKey('whatsapp_events.id'), nullable=False, unique=True),
          Column('payload', Text, nullable=False), Column('credential_hash', String(64), nullable=False),
          Column('is_receipt', Integer, nullable=False, server_default='0'),
          Column('status', String(20), nullable=False), Column('created_at', Float, nullable=False), Column('lease_until', Float, nullable=False, server_default='0'))
    queue = metadata.tables['whatsapp_outbox']
    Index('ix_whatsapp_queue', queue.c.status, queue.c.created_at, queue.c.id)
    Index('ix_whatsapp_chat_delivery', queue.c.company_id, queue.c.phone_hash, queue.c.status)
    Index('ix_whatsapp_event_retention', metadata.tables['whatsapp_events'].c.created_at)


@contextmanager
def migration_connection(engine):
    with engine.connect() as connection:
        sqlite = engine.dialect.name == 'sqlite'
        if sqlite:
            connection.exec_driver_sql('PRAGMA foreign_keys=OFF')
            connection.commit()
        try:
            with connection.begin():
                yield connection
                if sqlite and connection.exec_driver_sql('PRAGMA foreign_key_check').fetchone():
                    raise RuntimeError('A migração encontrou referências inválidas; alterações revertidas.')
        finally:
            if sqlite:
                connection.exec_driver_sql('PRAGMA foreign_keys=ON')
                connection.commit()


def migrate(connection, metadata):
    for name in ('whatsapp_outbox', 'whatsapp_events'):
        for index in metadata.tables[name].indexes:
            index.create(connection, checkfirst=True)
    if 'is_receipt' not in {item['name'] for item in inspect(connection).get_columns('whatsapp_outbox')}:
        connection.execute(text('ALTER TABLE whatsapp_outbox ADD COLUMN is_receipt INTEGER NOT NULL DEFAULT 0'))
    columns = {item['name']: item for item in inspect(connection).get_columns('occurrences')}
    if 'requester_contact_id' not in columns:
        if connection.dialect.name == 'sqlite':
            # Reconstrução preserva referências filhas; não renomear a tabela antiga.
            copied = MetaData()
            for table in metadata.tables.values():
                table.to_metadata(copied)
            replacement = metadata.tables['occurrences'].to_metadata(copied, name='occurrences_0010')
            connection.execute(CreateTable(replacement))
            names = ','.join(columns)
            connection.execute(text(f'INSERT INTO occurrences_0010({names}) SELECT {names} FROM occurrences'))
            connection.execute(text('DROP TABLE occurrences'))
            connection.execute(text('ALTER TABLE occurrences_0010 RENAME TO occurrences'))
            for index in metadata.tables['occurrences'].indexes:
                index.create(connection)
        else:
            connection.execute(text('ALTER TABLE occurrences ALTER COLUMN requester_id DROP NOT NULL'))
            connection.execute(text('ALTER TABLE occurrences ADD COLUMN requester_contact_id VARCHAR(36)'))
            connection.execute(text('ALTER TABLE occurrences ADD CONSTRAINT occurrence_contact_fk FOREIGN KEY(company_id,requester_contact_id) REFERENCES whatsapp_contacts(company_id,id)'))
            connection.execute(text('ALTER TABLE occurrences ADD CONSTRAINT occurrence_requester_check CHECK((requester_id IS NULL) <> (requester_contact_id IS NULL))'))
    additions = {'webhook_secret': "TEXT NOT NULL DEFAULT ''", 'bot_enabled': 'INTEGER NOT NULL DEFAULT 0',
                 'enabled_since': 'FLOAT NOT NULL DEFAULT 0', 'hook_status': "VARCHAR(30) NOT NULL DEFAULT 'disabled'"}
    existing = {item['name'] for item in inspect(connection).get_columns('company_whatsapp')}
    for name, datatype in additions.items():
        if name not in existing:
            connection.execute(text(f'ALTER TABLE company_whatsapp ADD COLUMN {name} {datatype}'))


def policies(connection):
    for table in PRIVATE_TABLES:
        connection.execute(text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
        connection.execute(text(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'))
        connection.execute(text(f'DROP POLICY IF EXISTS platform_access ON {table}'))
        connection.execute(text(f'CREATE POLICY platform_access ON {table} TO facilities_platform USING(true) WITH CHECK(true)'))
        connection.execute(text(f'GRANT SELECT,INSERT,UPDATE,DELETE ON {table} TO facilities_platform'))
    connection.execute(text('GRANT SELECT(id,company_id,name) ON whatsapp_contacts TO facilities_app'))
    connection.execute(text('DROP POLICY IF EXISTS contact_name_access ON whatsapp_contacts'))
    connection.execute(text("""CREATE POLICY contact_name_access ON whatsapp_contacts FOR SELECT TO facilities_app USING(
        company_id=current_setting('app.company_id',true) AND EXISTS(SELECT 1 FROM occurrences o
        WHERE o.company_id=whatsapp_contacts.company_id AND o.requester_contact_id=whatsapp_contacts.id))"""))
