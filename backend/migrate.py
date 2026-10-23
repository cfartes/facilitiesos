"""Executar com credencial exclusiva de migração, nunca com a credencial da API."""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine

from backend.schema import migrate_schema


def main():
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / '.env')
    load_dotenv(root / '.env.database')
    url = os.getenv('FACILITIES_MIGRATION_DATABASE_URL')
    if not url:
        raise SystemExit('Configure FACILITIES_MIGRATION_DATABASE_URL com o usuário proprietário do banco.')
    engine = create_engine(url, hide_parameters=True)
    try:
        migrate_schema(engine)
        print('Migrações até 0004 aplicadas. Dados existentes preservados.')
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
