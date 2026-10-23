"""Cria credenciais locais sem copiar segredos de outros projetos."""
import getpass
from pathlib import Path

from cryptography.fernet import Fernet
from email_validator import validate_email

from backend.security import password_hash


def main():
    target = Path(__file__).resolve().parents[1] / '.env'
    if target.exists():
        raise SystemExit('.env já existe. Preserve a chave de criptografia e configure-o manualmente.')
    email = validate_email(input('E-mail do Superadmin: ').strip(), check_deliverability=False).normalized
    password = getpass.getpass('Senha (mínimo 12 caracteres): ')
    if len(password) < 12 or password != getpass.getpass('Confirme a senha: '):
        raise SystemExit('Senha curta ou confirmação diferente. Nenhum arquivo criado.')
    content = (
        'FACILITIES_ENV=development\n'
        'FACILITIES_ORIGIN=http://127.0.0.1:5180\n'
        f'FACILITIES_ADMIN_EMAIL={email}\n'
        f'FACILITIES_ADMIN_PASSWORD_HASH={password_hash(password)}\n'
        f'FACILITIES_ENCRYPTION_KEY={Fernet.generate_key().decode()}\n'
        'FACILITIES_DB=data/facilities.sqlite3\n'
    )
    with target.open('x', encoding='utf-8') as stream:
        stream.write(content)
    print('Superadmin configurado no .env local. Não compartilhe esse arquivo.')


if __name__ == '__main__':
    main()
