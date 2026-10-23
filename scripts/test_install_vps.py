import argparse
from io import BytesIO
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet
import pytest

from backend.security import verify_password
from scripts import install_vps as install

PASSWORD = 'Installer-test-password-123!'


def arguments():
    return argparse.Namespace(traefik_container=None, network=None, entrypoint=None, resolver=None,
                              admin_email=None, password_file=None)


def containers():
    return [
        {'name': '/traefik', 'image': 'traefik:v3', 'args': ['--entrypoints.websecure.address=:443'],
         'labels': {}, 'networks': {'proxy_public': {'IPAddress': '172.25.0.2'}}},
        {'name': '/another-app', 'image': 'other-app:latest', 'args': [], 'networks': {},
         'labels': {'traefik.http.routers.other.tls.certresolver': 'letsencrypt',
                    'traefik.http.routers.other.entrypoints': 'websecure'}},
    ]


def test_secret_roundtrip_and_redaction(tmp_path):
    settings = install.new_settings('admin@facilities.dev', PASSWORD)
    path = tmp_path / '.env.production'
    install.write_settings(path, settings)
    saved = install.read_settings(path)
    assert saved == settings
    assert PASSWORD not in path.read_text()
    assert verify_password(PASSWORD, saved['FACILITIES_ADMIN_PASSWORD_HASH'])
    Fernet(saved['FACILITIES_ENCRYPTION_KEY'].encode())
    assert install.redact('postgres://u:' + saved['POSTGRES_PASSWORD'] + '@db', saved) == 'postgres://u:[protegido]@db'
    if os.name == 'posix':
        assert path.stat().st_mode & 0o077 == 0


def test_traefik_detection_reuses_existing_network():
    routing = install.detect_traefik(containers(), arguments(), {})
    assert routing == {'TRAEFIK_NETWORK': 'proxy_public', 'TRAEFIK_TRUSTED_IPS': '172.25.0.2',
                       'TRAEFIK_HTTPS_ENTRYPOINT': 'websecure', 'TRAEFIK_CERTRESOLVER': 'letsencrypt'}
    options = arguments(); options.network = 'not_attached'
    with pytest.raises(ValueError, match='rede'):
        install.detect_traefik(containers(), options, {})
    with pytest.raises(ValueError, match='único'):
        install.detect_traefik(containers() + containers()[:1], arguments(), {})


def simulated_docker(monkeypatch, tmp_path, has_volume=False, escaped_hash=False):
    monkeypatch.setattr(install, 'ROOT', tmp_path)
    monkeypatch.setattr(install.sys, 'platform', 'linux')
    monkeypatch.setattr(install.shutil, 'which', lambda name: name)
    monkeypatch.setattr(install.sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr(install.getpass, 'getpass', lambda prompt: PASSWORD)
    calls, backups = [], []
    def run(args, settings=None, output=None):
        calls.append(args)
        assert PASSWORD not in str(args)
        if args[:3] == ['docker', 'inspect', '--format']:
            return '\n'.join(json.dumps(item) for item in containers())
        if args[:2] == ['docker', 'ps']:
            return 'fake-container-id'
        if args[:3] == ['docker', 'volume', 'ls']:
            return install.PROJECT + '_facilities_data' if has_volume else ''
        if args[:3] == ['git', 'status', '--porcelain']:
            return ''
        if args[:2] == ['git', 'rev-parse']:
            return 'abcdef123456'
        if args[-2:] == ['up', '--help']:
            return '--wait --wait-timeout'
        if args[-3:] == ['config', '--format', 'json']:
            value = settings['FACILITIES_ADMIN_PASSWORD_HASH']
            if escaped_hash:
                value = value.replace('$', '$$')
            return json.dumps({'services': {'api': {'environment': {'FACILITIES_ADMIN_PASSWORD_HASH': value}}}})
        return ''
    monkeypatch.setattr(install, 'run', run)
    monkeypatch.setattr(install, 'backup', lambda settings, include_database: backups.append(include_database))
    class Response(BytesIO):
        headers = {'X-Facilities-Release': 'abcdef123456'}
        def geturl(self):
            return 'https://' + install.DOMAIN + '/api/v1/health'
    monkeypatch.setattr(install, 'urlopen', lambda *args, **kwargs: Response(b'{"status":"ok"}'))
    return calls, backups


@pytest.mark.parametrize('escaped_hash', [False, True])
def test_install_then_upgrade_preserves_keys_and_credentials(monkeypatch, tmp_path, escaped_hash):
    calls, _ = simulated_docker(monkeypatch, tmp_path, escaped_hash=escaped_hash)
    install.install(arguments())
    path = tmp_path / '.env.production'
    original = install.read_settings(path)
    assert verify_password(PASSWORD, original['FACILITIES_ADMIN_PASSWORD_HASH'])
    migration = next(index for index, cmd in enumerate(calls) if 'migrate' in cmd)
    api_up = next(index for index, cmd in enumerate(calls) if cmd[-2:] == ['api', 'web'] and 'up' in cmd)
    assert migration < api_up
    calls, backups = simulated_docker(monkeypatch, tmp_path, has_volume=True, escaped_hash=escaped_hash)
    monkeypatch.setattr(install.getpass, 'getpass', lambda _: pytest.fail('Credenciais não devem ser solicitadas novamente.'))
    install.install(arguments())
    assert install.read_settings(path) == original
    assert backups == [False, True]
    assert any(cmd[-2:] == ['stop', 'api'] for cmd in calls)
    assert not any('prune' in cmd or 'down' in cmd for cmd in calls)
    for cmd in calls:
        if cmd[:2] == ['docker', 'compose'] and '--help' not in cmd:
            assert cmd[cmd.index('--project-name') + 1] == install.PROJECT


def test_existing_volume_without_settings_aborts(monkeypatch, tmp_path):
    calls, _ = simulated_docker(monkeypatch, tmp_path, has_volume=True)
    with pytest.raises(ValueError, match='volume'):
        install.install(arguments())
    assert not (tmp_path / '.env.production').exists()
    assert not any(('build' in cmd or 'up' in cmd) and '--help' not in cmd for cmd in calls)


def test_database_backup_is_created_before_migration(monkeypatch, tmp_path):
    monkeypatch.setattr(install, 'ROOT', tmp_path)
    settings = install.new_settings('admin@facilities.dev', PASSWORD)
    def compose(settings, *args, output=None):
        assert args[:4] == ('exec', '-T', 'db', 'pg_dump')
        output.write(b'PGDMP-test-backup')
    monkeypatch.setattr(install, 'compose', compose)
    install.backup(settings, True)
    files = list((tmp_path / 'data' / 'backups').iterdir())
    assert len(files) == 2
    assert next(path for path in files if path.suffix == '.dump').read_bytes().startswith(b'PGDMP')
