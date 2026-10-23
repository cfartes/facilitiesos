"""Estrutura do atendimento, com referências compostas por empresa e unidade."""
from sqlalchemy import CheckConstraint, Column, ForeignKeyConstraint, Index, Integer, String, Table, Text, UniqueConstraint

OP_TABLES = ('service_categories', 'assets', 'occurrences', 'work_orders', 'order_participants',
             'order_messages', 'order_events', 'notifications', 'attachments')


def register_tables(metadata):
    def identity():
        return [Column('id', String(36), primary_key=True), Column('company_id', String(36), nullable=False)]

    def unit():
        return Column('unit_id', String(36), nullable=False)

    def company_fk():
        return ForeignKeyConstraint(['company_id'], ['companies.id'])

    def unit_fk():
        return ForeignKeyConstraint(['company_id','unit_id'], ['locations.company_id','locations.id'])

    def order_fk():
        return ForeignKeyConstraint(['company_id','unit_id','order_id'], ['work_orders.company_id','work_orders.unit_id','work_orders.id'])

    Table('service_categories', metadata, *identity(), Column('name', String(120), nullable=False),
          Column('is_active', Integer, nullable=False, server_default='1'), Column('version', Integer, nullable=False, server_default='1'),
          UniqueConstraint('company_id','id'), UniqueConstraint('company_id','name'), company_fk())
    Table('assets', metadata, *identity(), unit(), Column('location_id', String(36), nullable=False),
          Column('code', String(40), nullable=False), Column('name', String(160), nullable=False),
          Column('category', String(100), nullable=False), Column('criticality', String(20), nullable=False),
          Column('status', String(30), nullable=False, server_default='active'),
          Column('version', Integer, nullable=False, server_default='1'), Column('created_at', Text, nullable=False),
          UniqueConstraint('company_id','unit_id','id'), UniqueConstraint('company_id','code'), company_fk(), unit_fk(),
          ForeignKeyConstraint(['company_id','unit_id','location_id'], ['locations.company_id','locations.unit_id','locations.id']))
    Table('work_orders', metadata, *identity(), unit(), Column('location_id', String(36), nullable=False),
          Column('category_id', String(36), nullable=False), Column('asset_id', String(36)), Column('assignee_id', String(36)),
          Column('code', String(30), nullable=False), Column('title', String(180), nullable=False), Column('description', Text, nullable=False),
          Column('state', String(30), nullable=False, server_default='triage'), Column('impact', Integer, nullable=False),
          Column('urgency', Integer, nullable=False), Column('priority', String(20), nullable=False),
          Column('solution', Text, nullable=False, server_default=''), Column('evidence', Text, nullable=False, server_default=''),
          Column('cycle', Integer, nullable=False, server_default='1'), Column('version', Integer, nullable=False, server_default='1'),
          Column('created_at', Text, nullable=False), Column('updated_at', Text, nullable=False), Column('resolved_at', Text), Column('closed_at', Text),
          UniqueConstraint('company_id','unit_id','id'), UniqueConstraint('company_id','code'), company_fk(), unit_fk(),
          ForeignKeyConstraint(['company_id','unit_id','location_id'], ['locations.company_id','locations.unit_id','locations.id']),
          ForeignKeyConstraint(['company_id','category_id'], ['service_categories.company_id','service_categories.id']),
          ForeignKeyConstraint(['company_id','unit_id','asset_id'], ['assets.company_id','assets.unit_id','assets.id']),
          ForeignKeyConstraint(['company_id','assignee_id'], ['users.company_id','users.id']))
    Table('occurrences', metadata, *identity(), unit(), Column('location_id', String(36), nullable=False),
          Column('category_id', String(36), nullable=False), Column('asset_id', String(36)), Column('order_id', String(36)),
          Column('requester_id', String(36), nullable=False), Column('client_request_id', String(36), nullable=False),
          Column('request_hash', String(64), nullable=False), Column('code', String(30), nullable=False),
          Column('title', String(180), nullable=False), Column('description', Text, nullable=False),
          Column('outcome', String(30), nullable=False, server_default='open'), Column('version', Integer, nullable=False, server_default='1'),
          Column('created_at', Text, nullable=False), Column('first_response_at', Text), Column('confirmation_note', Text, nullable=False, server_default=''),
          UniqueConstraint('company_id','requester_id','client_request_id'), UniqueConstraint('company_id','code'),
          company_fk(), unit_fk(), order_fk(),
          ForeignKeyConstraint(['company_id','requester_id'], ['users.company_id','users.id']),
          ForeignKeyConstraint(['company_id','unit_id','location_id'], ['locations.company_id','locations.unit_id','locations.id']),
          ForeignKeyConstraint(['company_id','category_id'], ['service_categories.company_id','service_categories.id']),
          ForeignKeyConstraint(['company_id','unit_id','asset_id'], ['assets.company_id','assets.unit_id','assets.id']))
    Table('order_participants', metadata, Column('company_id', String(36), primary_key=True), unit(),
          Column('order_id', String(36), primary_key=True), Column('user_id', String(36), primary_key=True), order_fk(),
          ForeignKeyConstraint(['company_id','user_id'], ['users.company_id','users.id']))
    for table in ('order_messages','order_events'):
        fields = [*identity(), unit(), Column('order_id', String(36), nullable=False), Column('actor_name', String(160), nullable=False),
                  Column('visibility', String(20), nullable=False, server_default='shared'), Column('created_at', Text, nullable=False)]
        if table == 'order_messages':
            fields += [Column('body', Text, nullable=False)]
        else:
            fields += [Column('action', String(60), nullable=False), Column('note', Text, nullable=False, server_default=''),
                       Column('cycle', Integer, nullable=False)]
        Table(table, metadata, *fields, order_fk())
    Table('notifications', metadata, *identity(), unit(), Column('user_id', String(36), nullable=False),
          Column('order_id', String(36)), Column('occurrence_id', String(36)), Column('title', String(180), nullable=False),
          Column('created_at', Text, nullable=False), Column('read_at', Text), company_fk(), unit_fk(),
          ForeignKeyConstraint(['company_id','user_id'], ['users.company_id','users.id']), order_fk())
    occurrences = metadata.tables['occurrences']
    Index('uq_occurrences_company_unit_id', occurrences.c.company_id, occurrences.c.unit_id, occurrences.c.id, unique=True)
    # shortcut: imagens no banco com cota de piloto; migrar para objetos privados antes de ampliar a escala.
    Table('attachments', metadata, *identity(), unit(), Column('order_id', String(36)), Column('occurrence_id', String(36)),
          Column('uploader_id', String(36)), Column('uploader_name', String(160), nullable=False),
          Column('filename', String(120), nullable=False), Column('content_type', String(30), nullable=False),
          Column('byte_size', Integer, nullable=False), Column('sha256', String(64), nullable=False),
          Column('ciphertext', Text, nullable=False), Column('visibility', String(20), nullable=False), Column('created_at', Text, nullable=False),
          CheckConstraint('(order_id IS NULL) <> (occurrence_id IS NULL)'),
          CheckConstraint("visibility IN ('shared','internal') AND (occurrence_id IS NULL OR visibility='shared')"),
          CheckConstraint('byte_size > 0 AND byte_size <= 5242880'), company_fk(), unit_fk(), order_fk(),
          ForeignKeyConstraint(['company_id','unit_id','occurrence_id'], ['occurrences.company_id','occurrences.unit_id','occurrences.id']),
          ForeignKeyConstraint(['company_id','uploader_id'], ['users.company_id','users.id']))


def apply_operation_policies(connection):
    from sqlalchemy import text
    scope = "company_id=current_setting('app.company_id',true)"
    unit_scope = scope + " AND (current_setting('app.all_units',true)='true' OR unit_id=ANY(string_to_array(current_setting('app.unit_ids',true),',')))"
    manage = "current_setting('app.manage_operations',true)='true'"
    review = "current_setting('app.review_operations',true)='true'"
    uid = "current_setting('app.user_id',true)"
    participant = f"EXISTS(SELECT 1 FROM order_participants p WHERE p.company_id=work_orders.company_id AND p.order_id=work_orders.id AND p.user_id={uid})"
    order_access = f"({manage} OR {review} OR assignee_id={uid} OR {participant})"
    view_order = 'EXISTS(SELECT 1 FROM work_orders w WHERE w.id=order_id AND w.company_id=company_id)'
    internal = f"({manage} OR {review} OR EXISTS(SELECT 1 FROM work_orders w WHERE w.id=order_id AND w.company_id=company_id AND w.assignee_id={uid}))"
    conditions = {
        'service_categories': scope,
        'assets': unit_scope,
        'occurrences': f"{unit_scope} AND ({manage} OR {review} OR requester_id={uid} OR EXISTS(SELECT 1 FROM work_orders w WHERE w.id=occurrences.order_id AND w.company_id=occurrences.company_id AND w.assignee_id={uid}))",
        'work_orders': f'{unit_scope} AND {order_access}',
        'order_participants': f'{unit_scope} AND ({manage} OR {review} OR user_id={uid})',
        'order_messages': f"{unit_scope} AND {view_order} AND (visibility='shared' OR {internal})",
        'order_events': f"{unit_scope} AND {view_order} AND (visibility='shared' OR {internal})",
        'notifications': f'{unit_scope} AND user_id={uid}',
        'attachments': f"""{unit_scope} AND (
            (occurrence_id IS NOT NULL AND EXISTS(SELECT 1 FROM occurrences o WHERE o.id=attachments.occurrence_id AND o.company_id=attachments.company_id AND ({manage} OR {review} OR o.requester_id={uid})))
            OR (order_id IS NOT NULL AND EXISTS(SELECT 1 FROM work_orders w WHERE w.id=attachments.order_id AND w.company_id=attachments.company_id)
                AND (visibility='shared' OR {manage} OR {review} OR EXISTS(SELECT 1 FROM work_orders w WHERE w.id=attachments.order_id AND w.company_id=attachments.company_id AND w.assignee_id={uid}))))""",
    }
    for table, condition in conditions.items():
        if table in ('order_messages', 'order_events'):
            condition = condition.replace('w.id=order_id', f'w.id={table}.order_id').replace('w.company_id=company_id', f'w.company_id={table}.company_id')
        connection.execute(text(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY'))
        connection.execute(text(f'ALTER TABLE {table} FORCE ROW LEVEL SECURITY'))
        connection.execute(text(f'DROP POLICY IF EXISTS platform_access ON {table}'))
        connection.execute(text(f'CREATE POLICY platform_access ON {table} TO facilities_platform USING(true) WITH CHECK(true)'))
        connection.execute(text(f'GRANT SELECT,INSERT,UPDATE ON {table} TO facilities_platform'))
        connection.execute(text(f'GRANT SELECT ON {table} TO facilities_app'))
        connection.execute(text(f'DROP POLICY IF EXISTS tenant_scope ON {table}'))
        connection.execute(text(f'CREATE POLICY tenant_scope ON {table} TO facilities_app USING({condition}) WITH CHECK({condition})'))
        connection.execute(text(f'GRANT INSERT ON {table} TO facilities_app'))
        if table not in ('order_messages','order_events','order_participants','attachments'):
            connection.execute(text(f'GRANT UPDATE ON {table} TO facilities_app'))
    # Permite entregar avisos a outros participantes, mantendo a leitura individual.
    connection.execute(text('DROP POLICY IF EXISTS notification_delivery ON notifications'))
    connection.execute(text(f'CREATE POLICY notification_delivery ON notifications FOR INSERT TO facilities_app WITH CHECK({unit_scope})'))
    connection.execute(text('GRANT DELETE ON attachments TO facilities_app,facilities_platform'))
    connection.execute(text('REVOKE UPDATE ON attachments FROM facilities_app,facilities_platform'))
    connection.execute(text('DROP POLICY IF EXISTS attachment_removal ON attachments'))
    connection.execute(text(f'''CREATE POLICY attachment_removal ON attachments AS RESTRICTIVE FOR DELETE TO facilities_app
        USING (({manage} OR uploader_id={uid}) AND (
            (order_id IS NOT NULL AND EXISTS(SELECT 1 FROM work_orders w WHERE w.id=attachments.order_id AND w.company_id=attachments.company_id AND w.state NOT IN ('closed','cancelled')))
            OR (occurrence_id IS NOT NULL AND EXISTS(SELECT 1 FROM occurrences o WHERE o.id=attachments.occurrence_id AND o.company_id=attachments.company_id AND
                (o.order_id IS NULL OR EXISTS(SELECT 1 FROM work_orders w WHERE w.id=o.order_id AND w.company_id=o.company_id AND w.state NOT IN ('closed','cancelled')))))))'''))
