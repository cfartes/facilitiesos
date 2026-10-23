"""SQLAlchemy, transações explícitas e escopo RLS por transação."""
import json
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import bindparam, create_engine, event, text


class Record(dict):
    def __getitem__(self, key):
        return tuple(self.values())[key] if isinstance(key, int) else super().__getitem__(key)


class Result:
    def __init__(self, result):
        self.result = result
        self.rowcount = result.rowcount

    def fetchone(self):
        value = self.result.mappings().fetchone()
        return Record(value) if value is not None else None

    def fetchall(self):
        return [Record(value) for value in self.result.mappings().all()]


class Connection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, statement, values=None):
        if statement == 'BEGIN IMMEDIATE':
            if self.connection.dialect.name == 'postgresql':
                return Result(self.connection.execute(text('SELECT pg_advisory_xact_lock(741001)')))
            return Result(self.connection.exec_driver_sql(statement))
        if isinstance(values, tuple):
            parts = statement.split('?')
            if len(parts) - 1 != len(values):
                raise ValueError('Invalid parameter count')
            statement = ''.join(part + (f':p{index}' if index < len(values) else '') for index, part in enumerate(parts))
            values = {f'p{index}': value for index, value in enumerate(values)}
        return Result(self.connection.execute(text(statement), values or {}))


class Database:
    def __init__(self, path=None, platform_url=None, tenant_url=None):
        self.postgres = bool(platform_url)
        if platform_url:
            if not tenant_url:
                raise RuntimeError('Configure FACILITIES_DATABASE_URL e FACILITIES_PLATFORM_DATABASE_URL.')
            self.platform = create_engine(platform_url, pool_pre_ping=True, hide_parameters=True)
            self.tenant = create_engine(tenant_url, pool_pre_ping=True, hide_parameters=True)
            for engine, expected in [(self.platform, 'facilities_platform'), (self.tenant, 'facilities_app')]:
                with engine.connect() as connection:
                    row = connection.execute(text('SELECT rolname,rolsuper,rolbypassrls,rolcreatedb,rolcreaterole FROM pg_roles WHERE rolname=current_user')).mappings().one()
                    if row['rolname'] != expected or any(row[key] for key in ('rolsuper', 'rolbypassrls', 'rolcreatedb', 'rolcreaterole')):
                        raise RuntimeError('Papel de runtime inválido: use facilities_app/platform sem privilégios administrativos ou BYPASSRLS.')
                    if connection.execute(text("SELECT count(*) FROM schema_versions WHERE version IN ('0001','0002','0003','0004','0005')")).scalar_one() != 5:
                        raise RuntimeError('Execute python -m backend.migrate antes de iniciar a API.')
                    from backend.operation_schema import OP_TABLES
                    tables = ('configuration','sessions','audit','rate_limits','companies','users','auth_accounts','invitations','locations') + OP_TABLES
                    protected = connection.execute(text("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN :tables AND c.relrowsecurity AND c.relforcerowsecurity").bindparams(bindparam('tables', expanding=True)), {'tables': tables}).scalar_one()
                    if protected != len(tables):
                        raise RuntimeError('As políticas RLS/FORCE RLS da fundação não estão completas.')
        else:
            target = Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            self.platform = self.tenant = create_engine('sqlite:///' + str(target), connect_args={'timeout': 10, 'check_same_thread': False}, hide_parameters=True)

            @event.listens_for(self.platform, 'connect')
            def sqlite_options(connection, record):
                connection.execute('PRAGMA foreign_keys=ON')
                connection.execute('PRAGMA journal_mode=WAL')

            from backend.schema import migrate_schema
            migrate_schema(self.platform)

    @contextmanager
    def connect(self):
        with self.platform.begin() as connection:
            yield Connection(connection)

    @contextmanager
    def scoped(self, actor, company_id):
        engine = self.platform if actor['role'] == 'superadmin' else self.tenant
        with engine.begin() as connection:
            if self.postgres and actor['role'] != 'superadmin':
                connection.execute(text("SELECT set_config('app.company_id', :company, true), set_config('app.all_units', :all_units, true), set_config('app.unit_ids', :units, true)"), {
                    'company': company_id, 'all_units': 'true' if actor['all_units'] else 'false',
                    'units': ','.join(actor['unit_ids']),
                })
                roles = set(actor.get('roles', []))
                connection.execute(text("SELECT set_config('app.user_id', :user_id, true), set_config('app.manage_operations', :manage, true), set_config('app.review_operations', :review, true)"), {
                    'user_id': actor.get('id', ''), 'manage': 'true' if roles & {'company_admin','supervisor'} else 'false',
                    'review': 'true' if roles & {'manager','auditor'} else 'false',
                })
            yield Connection(connection)

    def dispose(self):
        self.platform.dispose()
        if self.tenant is not self.platform:
            self.tenant.dispose()
