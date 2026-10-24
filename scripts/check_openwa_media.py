"""Diagnóstico somente de leitura; exibe apenas configurações de mídia permitidas."""
import json
from pathlib import Path
import re
import subprocess
import sys

FIELDS = ('MEDIA_DOWNLOAD_ENABLED', 'MEDIA_DOWNLOAD_MAX_BYTES', 'CHAT_MEDIA_ARCHIVE_ENABLED',
          'WEBHOOK_MEDIA_INLINE_MAX_BYTES', 'WEBHOOK_MAX_PAYLOAD_BYTES', 'LOG_LEVEL', 'LOG_FORMAT')


def media_settings(environment):
    values = dict(item.split('=', 1) for item in environment if '=' in item)
    return {key: values.get(key, '(não definido; usa o padrão da versão)') for key in FIELDS}


def media_errors(path):
    with Path(path).open('rb') as stream:
        stream.seek(0, 2)
        stream.seek(max(0, stream.tell() - 262144))
        lines = stream.read(262144).decode(errors='replace').splitlines()
    errors = []
    for line in lines:
        try:
            line = json.loads(line).get('log', '')
        except (ValueError, AttributeError):
            continue
        if not re.search(r'media|download', line, re.I) or not re.search(r'fail|error|timeout|timed out|exceed|omitted', line, re.I):
            continue
        line = re.sub(r'\x1b\[[0-9;]*m', '', line)[:1200]
        line = re.sub(r'https?://\S+', '[url omitida]', line)
        line = re.sub(r'[A-Za-z0-9+/=_-]{40,}', '[identificador omitido]', line)
        line = re.sub(r'[0-9]{7,}', '[numero omitido]', line)
        errors.append(line)
    return errors[-8:]


def main():
    names = subprocess.check_output(['docker', 'ps', '--format', '{{.Names}}'], text=True, timeout=10).split()
    matches = [name for name in names if 'openwa' in name.lower()]
    name = sys.argv[1] if len(sys.argv) > 1 else matches[0] if len(matches) == 1 else None
    if not name or name not in names:
        raise SystemExit('Informe o container em execução: python3 scripts/check_openwa_media.py NOME_DO_CONTAINER')
    raw = subprocess.check_output(['docker', 'inspect', name], text=True, timeout=10)
    container = json.loads(raw)[0]
    print('Container:', container['Name'].lstrip('/'))
    print('Imagem:', container['Config']['Image'])
    print('Driver de logs:', container.get('HostConfig', {}).get('LogConfig', {}).get('Type') or '(padrão do Docker)')
    labels = container['Config'].get('Labels') or {}
    for key in ('com.docker.compose.project.config_files', 'com.docker.compose.service'):
        print(key + ':', labels.get(key) or '(sem vínculo Compose)')
    for key, value in media_settings(container['Config'].get('Env') or []).items():
        print(key + '=' + value)
    log_path = container.get('LogPath')
    if log_path and container.get('HostConfig', {}).get('LogConfig', {}).get('Type') == 'json-file':
        print('Erros de mídia no final do arquivo de logs:')
        try:
            errors = media_errors(log_path)
            print('\n'.join(errors) if errors else '(nenhum erro de mídia encontrado nos últimos 256 KiB)')
        except OSError:
            print('(arquivo de logs não acessível; execute o diagnóstico como root na VPS)')
    print('Nenhuma configuração foi alterada. Se o download estiver desativado ou abaixo de 5242880 bytes, revise o Compose do OpenWA. Se os valores estiverem corretos, verifique os erros de download nos logs do provedor.')


if __name__ == '__main__':
    main()
