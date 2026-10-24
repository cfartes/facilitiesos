"""Diagnóstico somente de leitura; exibe apenas configurações de mídia permitidas."""
import json
import subprocess
import sys

FIELDS = ('MEDIA_DOWNLOAD_ENABLED', 'MEDIA_DOWNLOAD_MAX_BYTES', 'CHAT_MEDIA_ARCHIVE_ENABLED',
          'WEBHOOK_MEDIA_INLINE_MAX_BYTES', 'WEBHOOK_MAX_PAYLOAD_BYTES')


def media_settings(environment):
    values = dict(item.split('=', 1) for item in environment if '=' in item)
    return {key: values.get(key, '(não definido; usa o padrão da versão)') for key in FIELDS}


def main():
    names = subprocess.check_output(['docker', 'ps', '--format', '{{.Names}}'], text=True).split()
    matches = [name for name in names if 'openwa' in name.lower()]
    name = sys.argv[1] if len(sys.argv) > 1 else matches[0] if len(matches) == 1 else None
    if not name or name not in names:
        raise SystemExit('Informe o container em execução: python3 scripts/check_openwa_media.py NOME_DO_CONTAINER')
    raw = subprocess.check_output(['docker', 'inspect', name], text=True)
    container = json.loads(raw)[0]
    print('Container:', container['Name'].lstrip('/'))
    print('Imagem:', container['Config']['Image'])
    for key, value in media_settings(container['Config'].get('Env') or []).items():
        print(key + '=' + value)
    print('Nenhuma configuração foi alterada. Se o download estiver desativado ou abaixo de 5242880 bytes, revise o Compose do OpenWA. Se os valores estiverem corretos, verifique os erros de download nos logs do provedor.')


if __name__ == '__main__':
    main()
