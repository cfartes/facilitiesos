"""Endpoints fixos: chaves nunca são enviadas a URLs fornecidas pelo navegador."""
import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from fastapi import HTTPException

OPENWA_BASE = 'https://openwa.187-77-58-10.sslip.io/api'
RESEND_BASE = 'https://api.resend.com'


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
