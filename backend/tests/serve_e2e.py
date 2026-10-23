"""API temporária para Playwright; conta e banco exclusivos dos testes."""
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet
import uvicorn

from backend.main import create_app
from backend.security import password_hash


def main():
    with TemporaryDirectory(prefix='facilities_e2e_') as directory:
        app = create_app(Path(directory) / 'e2e.sqlite3', 'e2e-admin@example.com',
                         password_hash('E2E-only-password-123!'), Fernet.generate_key(), 'http://127.0.0.1:5190')
        mailbox = []
        def fake_send(key, payload, identity):
            mailbox.append(payload)
            del mailbox[:-50]
            return 'e2e-provider-accepted'

        # Caixa sintética apenas desta API temporária; não é registrada em backend.main.
        @app.get('/api/v1/_test/mailbox')
        def read_mailbox(recipient: str):
            return [item for item in mailbox if recipient in item['to']]

        # Provedor simulado somente neste processo temporário; nunca enviar mensagens reais nos testes.
        with patch('backend.providers.resend_invitation', side_effect=fake_send):
            uvicorn.run(app, host='127.0.0.1', port=8011, access_log=False, proxy_headers=False)


if __name__ == '__main__':
    main()
