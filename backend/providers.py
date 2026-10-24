"""Endpoints fixos: chaves nunca são enviadas a URLs fornecidas pelo navegador."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fastapi import HTTPException

OPENWA_BASE = 'https://openwa.187-77-58-10.sslip.io/api'
RESEND_BASE = 'https://api.resend.com'


def openwa_image(key, session, chat, message):
    from urllib.parse import quote
    from backend.attachments import MAX_BYTES
    # IDs autenticados do evento, nunca uma URL de download enviada pelo remetente.
    url = OPENWA_BASE + '/sessions/' + quote(session, safe='') + '/messages/' + quote(chat, safe='') + '/' + quote(message, safe='') + '/media'
    request = Request(url, headers={'X-API-Key': key, 'User-Agent': 'NexusFacilitiesOS/0.1'})
    try:
        with build_opener(NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise HTTPException(413, 'A foto ultrapassa 5 MiB. Reduza o tamanho e envie novamente.')
            return raw, response.headers.get_content_type()
    except HTTPError as error:
        if error.code == 404:
            raise HTTPException(502, 'O OpenWA recebeu a mensagem, mas não disponibilizou o arquivo da foto. O administrador precisa conferir o download de mídia e os logs do OpenWA. Depois, envie uma nova foto.') from None
        if error.code in (401, 403):
            raise HTTPException(502, 'O OpenWA recusou o acesso ao arquivo da foto. Solicite ao administrador a revisão das permissões da integração.') from None
        raise HTTPException(502, 'O OpenWA não concluiu o download da foto. Tente novamente mais tarde ou digite 0 para seguir sem ela.') from None
    except (URLError, OSError, ValueError):
        raise HTTPException(502, 'Não foi possível obter a foto no OpenWA. Envie novamente ou digite 0 para seguir sem ela.') from None


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_provider(url: str, headers: dict, payload=None):
    request = Request(url, headers=headers | {'Content-Type': 'application/json', 'User-Agent': 'NexusFacilitiesOS/0.1'},
                      data=json.dumps(payload).encode() if payload is not None else None,
                      method='POST' if payload is not None else 'GET')
    try:
        with build_opener(NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError('response limit')
            return json.loads(raw)
    except HTTPError as error:
        detail = {
            401: 'O provedor recusou a API Key. Confira a chave cadastrada.',
            403: 'O provedor recusou a operação. Confira permissões, remetente e domínio verificado.',
            404: 'O recurso não foi encontrado no provedor.',
            422: 'O provedor recusou os dados. Confira remetente e destinatário.',
            429: 'Limite do provedor atingido. Aguarde antes de tentar novamente.',
        }.get(error.code, 'O provedor não concluiu a operação. Tente novamente mais tarde.')
        raise HTTPException(502, detail) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise HTTPException(502, 'Não foi possível confirmar a resposta do provedor. Em testes de e-mail, verifique o recebimento antes de repetir.') from None


def openwa_sessions(key: str):
    data = request_provider(OPENWA_BASE + '/sessions', {'X-API-Key': key})
    if isinstance(data, dict):
        data = data.get('sessions', data.get('data'))
        if isinstance(data, dict):
            data = data.get('sessions')
    if not isinstance(data, list):
        raise HTTPException(502, 'O OpenWA retornou um formato de sessões não reconhecido.')
    # Não repassar chats, telefones, QR Codes ou respostas brutas do gateway.
    return [{'id': str(item.get('id', ''))[:80],
             'name': str(item.get('name', 'Sessão'))[:120],
             'status': str(item.get('status', 'UNKNOWN'))[:40]}
            for item in data if isinstance(item, dict)]


def resend_test(key: str, sender: str, recipient: str):
    data = request_provider(RESEND_BASE + '/emails', {'Authorization': f'Bearer {key}'}, {
        'from': f'Nexus Facilities OS <{sender}>', 'to': [recipient],
        'subject': 'Teste de configuração • Nexus Facilities OS',
        'text': 'Este é um e-mail de teste solicitado pelo Superadmin do Nexus Facilities OS. A integração com o Resend aceitou esta solicitação de envio.',
    })
    if not isinstance(data, dict) or not isinstance(data.get('id'), str):
        raise HTTPException(502, 'O Resend retornou uma resposta não reconhecida. Verifique o recebimento antes de repetir.')
    return {'message': 'Envio aceito pelo Resend. Confira a caixa de entrada e o spam; o aceite não confirma a entrega.'}


class InvitationSendError(Exception):
    def __init__(self, message, retryable=False, retry_after=0):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


def resend_invitation(key, payload, idempotency_key):
    request = Request(RESEND_BASE + '/emails', data=json.dumps(payload).encode(), method='POST', headers={
        'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json',
        'User-Agent': 'NexusFacilitiesOS/0.1', 'Idempotency-Key': idempotency_key,
    })
    try:
        with build_opener(NoRedirect()).open(request, timeout=15) as response:
            raw = response.read(100_001)
            if len(raw) > 100_000:
                raise ValueError('response limit')
            data = json.loads(raw)
            if not isinstance(data, dict) or not isinstance(data.get('id'), str) or not 1 <= len(data['id']) <= 200:
                raise ValueError('invalid response')
            return data['id']
    except HTTPError as error:
        retryable = error.code in (408, 409, 429) or error.code >= 500
        wait = error.headers.get('Retry-After', '') if error.headers else ''
        wait = min(int(wait), 3600) if wait.isascii() and wait.isdigit() and len(wait) <= 8 else 0
        raise InvitationSendError('Falha temporária no provedor; haverá nova tentativa.' if retryable else
                                  'Envio recusado pelo provedor. Confira chave, remetente e destinatário antes de gerar novo convite.', retryable, wait) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise InvitationSendError('Resposta do provedor não confirmada; nova tentativa usará a mesma chave de envio.', True) from None
