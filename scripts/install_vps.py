"""Instala/atualiza somente o Facilities, usando o Docker/Traefik já existentes."""
import argparse
import base64
from datetime import datetime, timezone
import getpass
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.security import password_hash

PROJECT = 'nexus-facilities-production'
DOMAIN = 'facilities.nexusdataanalytics.tech'
IDENTIFIER = re.compile(r'[A-Za-z0-9_.-]{1,128}')
PRIVATE_KEYS = ('POSTGRES_PASSWORD', 'APP_DB_PASSWORD', 'PLATFORM_DB_PASSWORD',
                'FACILITIES_ADMIN_PASSWORD_HASH', 'FACILITIES_ENCRYPTION_KEY')


def redact(message, settings):
    for key in PRIVATE_KEYS:
        value = settings.get(key)
        if value:
            message = message.replace(value, '[protegido]')
    return message


def run(args, settings=None, output=None):
    result = subprocess.run(args, cwd=ROOT, env=os.environ | (settings or {}),
                            stdout=output or subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        detail = redact(result.stderr.decode(errors='replace'), settings or {})[-2000:]
        raise RuntimeError('Falha em ' + args[0] + ': ' + detail)
    return result.stdout.decode() if output is None else ''


def choose(label, candidates, explicit=None):
    candidates = sorted(set(candidates))
    if explicit:
        value = explicit
    elif len(candidates) == 1:
        value = candidates[0]
    elif sys.stdin.isatty():
        print(label + ': ' + (', '.join(candidates) or 'não detectado'))
        value = input('Informe ' + label + ': ').strip()
    else:
        raise ValueError('Informe ' + label + ' pelas opções do instalador; a detecção foi ambígua.')
    if not IDENTIFIER.fullmatch(value):
        raise ValueError('Valor inválido para ' + label + '.')
    return value


def detect_traefik(containers, args, existing):
    proxies = [item for item in containers if re.search(r'(^|/)traefik(?=[:@]|$)', item['image'])]
    requested = args.traefik_container
    if requested:
        proxies = [item for item in proxies if item['name'].lstrip('/') == requested]
    if len(proxies) != 1:
        raise ValueError('Informe --traefik-container com o nome do Traefik existente; não foi possível escolher um único container.')
    proxy = proxies[0]
    networks = proxy['networks']
    network = choose('rede Docker', [name for name in networks if name not in ('bridge','host','none')],
                     args.network or existing.get('TRAEFIK_NETWORK'))
    if network not in networks or network in ('bridge','host','none'):
        raise ValueError('A rede escolhida precisa ser uma rede própria já conectada ao Traefik.')
    entrypoints, resolvers = set(), set()
    for flag in proxy['args']:
        match = re.fullmatch(r'--entrypoints\.([^.]+)\.address=(?:[^:]*:)?443(?:/tcp)?', flag, re.IGNORECASE)
        if match:
            entrypoints.add(match.group(1))
        match = re.match(r'--certificatesresolvers\.([^.]+)\.', flag, re.IGNORECASE)
        if match:
            resolvers.add(match.group(1))
    for item in containers:
        for key, value in item['labels'].items():
            if key.startswith('traefik.http.routers.') and key.endswith('.tls.certresolver'):
                resolvers.add(value)
                entrypoints.update(filter(None, item['labels'].get(key.removesuffix('.tls.certresolver') + '.entrypoints', '').split(',')))
    entrypoint = choose('entrypoint HTTPS', entrypoints, args.entrypoint or existing.get('TRAEFIK_HTTPS_ENTRYPOINT'))
    resolver = choose('resolver TLS', resolvers, args.resolver or existing.get('TRAEFIK_CERTRESOLVER'))
    address = networks[network].get('IPAddress') or networks[network].get('GlobalIPv6Address')
    if not address:
        raise ValueError('O Traefik não tem IP na rede selecionada.')
    ipaddress.ip_address(address)
    return {'TRAEFIK_NETWORK': network, 'TRAEFIK_HTTPS_ENTRYPOINT': entrypoint,
            'TRAEFIK_CERTRESOLVER': resolver, 'TRAEFIK_TRUSTED_IPS': address}


def read_settings(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('O arquivo de configuração precisa ser um arquivo regular.')
    if os.name == 'posix' and path.stat().st_mode & 0o077:
        raise ValueError('Proteja ' + str(path) + ' com chmod 600 antes de continuar.')
    result = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r"([A-Z_]+)='([^'\r\n]*)'", line)
        if not match or match.group(1) in result:
            raise ValueError('Formato inválido no arquivo de configuração protegido.')
        result[match.group(1)] = match.group(2)
    if result.get('FACILITIES_INSTALL_FORMAT') != '1':
        raise ValueError('Configuração não reconhecida. Não será substituída.')
    for key in PRIVATE_KEYS[:3]:
        if not re.fullmatch(r'[0-9a-f]{64}', result.get(key, '')):
            raise ValueError('Configuração incompleta: ' + key)
    if not re.fullmatch(r'scrypt\$[0-9a-f]{32}\$[0-9a-f]{128}', result.get('FACILITIES_ADMIN_PASSWORD_HASH', '')):
        raise ValueError('Hash do Superadmin inválido.')
    try:
        if len(base64.b64decode(result['FACILITIES_ENCRYPTION_KEY'], altchars=b'-_', validate=True)) != 32:
            raise ValueError()
    except (KeyError, ValueError):
        raise ValueError('Chave de criptografia inválida; restaure a configuração original.') from None
    if not result.get('FACILITIES_ADMIN_EMAIL'):
        raise ValueError('E-mail do Superadmin ausente.')
    return result


def write_settings(path, settings):
    if path.is_symlink():
        raise ValueError('Não será substituído um link de configuração.')
    for key, value in settings.items():
        if not re.fullmatch(r'[A-Z_]+', key) or any(character in value for character in "'\r\n"):
            raise ValueError('Configuração não pode ser representada com segurança.')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, prefix=path.name + '.', delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            stream.write(''.join(key + "='" + value + "'\n" for key, value in settings.items()))
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def new_settings(email, password):
    if not re.fullmatch(r'[A-Za-z0-9_.+%-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', email) or len(email) > 254:
        raise ValueError('E-mail do Superadmin inválido.')
    if not 12 <= len(password) <= 128 or not any(c.isupper() for c in password) or not any(not c.isalnum() and not c.isspace() for c in password):
        raise ValueError('Use senha de 12 a 128 caracteres, com maiúscula e símbolo.')
    return {'FACILITIES_INSTALL_FORMAT': '1', 'FACILITIES_ADMIN_EMAIL': email,
            'FACILITIES_ADMIN_PASSWORD_HASH': password_hash(password),
            'FACILITIES_ENCRYPTION_KEY': base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
            **{key: secrets.token_hex(32) for key in PRIVATE_KEYS[:3]}}


def compose(settings, *args, output=None):
    return run(['docker', 'compose', '--project-name', PROJECT, '--env-file', str(ROOT / '.env.production'),
                '-f', str(ROOT / 'compose.production.yaml'), *args], settings, output)


def backup(settings, include_database):
    directory = ROOT / 'data' / 'backups'
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    write_settings(directory / (name + '.env.production'), settings)
    if include_database:
        target = directory / (name + '.dump')
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as output:
            compose(settings, 'exec', '-T', 'db', 'pg_dump', '-U', 'facilities_owner', '-d', 'facilities', '-Fc', output=output)
        if not target.stat().st_size:
            raise RuntimeError('O backup do banco ficou vazio. Atualização interrompida.')
        print('Backup criado em ' + str(target))


def install(args):
    if sys.platform != 'linux':
        raise ValueError('Execute este instalador na VPS Linux, dentro do checkout do Facilities.')
    if not shutil.which('docker') or not shutil.which('git'):
        raise ValueError('Docker com Compose e Git precisam estar instalados. O instalador não modifica o Docker/Traefik existente.')
    run(['docker', 'info', '--format', '{{.ServerVersion}}'])
    if '--wait' not in run(['docker', 'compose', 'up', '--help']):
        raise ValueError('Atualize o plugin Docker Compose para uma versão com suporte a --wait.')
    if run(['git', 'status', '--porcelain']).strip():
        raise ValueError('O checkout possui alterações locais. Revise-as antes de instalar; nenhum arquivo será descartado.')
    release = run(['git', 'rev-parse', '--short=12', 'HEAD']).strip()
    if not re.fullmatch(r'[0-9a-f]{12}', release):
        raise ValueError('Não foi possível identificar a versão do checkout.')
    path = ROOT / '.env.production'
    existing = read_settings(path) if path.exists() else {}
    ids = run(['docker', 'ps', '--quiet']).split()
    if not ids:
        raise ValueError('Nenhum container em execução. Inicie o Traefik existente antes de instalar.')
    template = '{"name":{{json .Name}},"image":{{json .Config.Image}},"args":{{json .Args}},"labels":{{json .Config.Labels}},"networks":{{json .NetworkSettings.Networks}}}'
    containers = [json.loads(line) for line in run(['docker', 'inspect', '--format', template, *ids]).splitlines()]
    for container in containers:
        container['labels'] = container['labels'] or {}
        container['args'] = container['args'] or []
        if container['labels'].get('com.docker.compose.project') == PROJECT and container['labels'].get('com.docker.compose.project.working_dir') != str(ROOT):
            raise ValueError('Já existe uma instalação Facilities em outro diretório. Use o checkout original e preserve sua configuração.')
    routing = detect_traefik(containers, args, existing)
    volumes = run(['docker', 'volume', 'ls', '--format', '{{.Name}}']).splitlines()
    has_database = PROJECT + '_facilities_data' in volumes
    if has_database and not existing:
        raise ValueError('Já existe volume de produção sem a configuração original. Restaure .env.production; novas chaves não serão geradas.')
    if existing:
        if args.password_file or (args.admin_email and args.admin_email != existing['FACILITIES_ADMIN_EMAIL']):
            raise ValueError('A reexecução preserva as credenciais. Alterações de acesso exigem procedimento próprio.')
        backup(existing, False)
        settings = existing.copy()
    else:
        if args.password_file:
            source = Path(args.password_file)
            if source.is_symlink() or not source.is_file() or (os.name == 'posix' and source.stat().st_mode & 0o077):
                raise ValueError('O arquivo de senha precisa ser regular e protegido com chmod 600.')
            password = source.read_text(encoding='utf-8').rstrip('\r\n')
        elif sys.stdin.isatty():
            password = getpass.getpass('Senha do Superadmin (use a senha já definida para o projeto): ')
            if password != getpass.getpass('Confirme a senha: '):
                raise ValueError('As senhas não coincidem.')
        else:
            raise ValueError('Execute em terminal interativo ou forneça --password-file protegido.')
        settings = new_settings(args.admin_email or 'admin@facilities.dev', password)
        del password
    settings.update(routing, RELEASE=release)
    write_settings(path, settings)
    model = json.loads(compose(settings, 'config', '--format', 'json'))
    # Compose escapa dólares no modelo exportado; isso não altera o valor no container.
    exported_hash = model['services']['api']['environment']['FACILITIES_ADMIN_PASSWORD_HASH']
    if exported_hash.replace('$$', '$') != settings['FACILITIES_ADMIN_PASSWORD_HASH']:
        raise ValueError('O Compose não preservou o hash da senha. Instalação interrompida.')
    print('Traefik: rede ' + routing['TRAEFIK_NETWORK'] + ', HTTPS ' + routing['TRAEFIK_HTTPS_ENTRYPOINT'] + ', TLS ' + routing['TRAEFIK_CERTRESOLVER'])
    print('Construindo imagens da versão ' + release + '...')
    compose(settings, 'build', '--pull', 'api', 'web')
    print('Preparando PostgreSQL privado...')
    compose(settings, 'up', '--wait', '--wait-timeout', '180', 'db')
    if has_database:
        compose(settings, 'stop', 'api')
        backup(settings, True)
    print('Aplicando migrações com credencial exclusiva...')
    compose(settings, 'run', '--rm', '--no-deps', 'migrate')
    print('Iniciando API e frontend do Facilities...')
    compose(settings, 'up', '--wait', '--wait-timeout', '180', 'api', 'web')
    print('Validando HTTPS e roteamento público...')
    for attempt in range(24):
        try:
            with urlopen('https://' + DOMAIN + '/api/v1/health', timeout=5) as response:
                if response.geturl() == 'https://' + DOMAIN + '/api/v1/health' and response.headers.get('X-Facilities-Release') == release and json.load(response) == {'status': 'ok'}:
                    print('Instalação validada: https://' + DOMAIN + '/nexus')
                    print('Superadmin: ' + settings['FACILITIES_ADMIN_EMAIL'] + ' — senha informada no terminal.')
                    return
        except (URLError, OSError, ValueError):
            pass
        if attempt < 23:
            time.sleep(5)
    raise RuntimeError('Containers iniciados, mas HTTPS/rota pública não foi validado. Confira DNS, portas 80/443, entrypoint e resolver TLS do Traefik. Nenhum volume foi removido.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--traefik-container')
    parser.add_argument('--network')
    parser.add_argument('--entrypoint')
    parser.add_argument('--resolver')
    parser.add_argument('--admin-email')
    parser.add_argument('--password-file')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.exit(1, 'Execute na VPS Linux.\n')
    import fcntl
    directory = ROOT / 'data'
    directory.mkdir(mode=0o700, exist_ok=True)
    with (directory / 'install.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            install(args)
        except (OSError, ValueError, RuntimeError) as error:
            parser.exit(1, str(error) + '\nConsulte infra/INSTALACAO_VPS.md. A stack dos outros apps não foi alterada.\n')


if __name__ == '__main__':
    main()
