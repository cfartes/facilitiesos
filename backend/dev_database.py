"""Provisiona somente o PostgreSQL local deste projeto, com segredos exclusivos."""
import secrets
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    target = root / '.env.database'
    if not target.exists():
        owner, app, platform = [secrets.token_urlsafe(36) for _ in range(3)]
        content = (
            f'POSTGRES_PASSWORD={owner}\nAPP_DB_PASSWORD={app}\nPLATFORM_DB_PASSWORD={platform}\n'
            f'FACILITIES_MIGRATION_DATABASE_URL=postgresql+psycopg://facilities_owner:{owner}@127.0.0.1:5452/facilities\n'
            f'FACILITIES_DATABASE_URL=postgresql+psycopg://facilities_app:{app}@127.0.0.1:5452/facilities\n'
            f'FACILITIES_PLATFORM_DATABASE_URL=postgresql+psycopg://facilities_platform:{platform}@127.0.0.1:5452/facilities\n'
        )
        with target.open('x', encoding='utf-8') as stream:
            stream.write(content)
        print('Credenciais exclusivas geradas em .env.database. Não compartilhe este arquivo.')
    subprocess.run(['docker', 'compose', '--env-file', str(target), 'up', '-d', '--wait', 'db'], cwd=root, check=True)
    from backend.migrate import main as migrate
    migrate()


if __name__ == '__main__':
    main()
