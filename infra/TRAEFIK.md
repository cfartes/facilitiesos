# Facilities na VPS com Traefik existente

Domínio informado: `facilities.nexusdataanalytics.tech`. Este documento é uma referência de integração; não cria outro Traefik nem altera os apps existentes. A publicação na VPS e o pareamento real dos eventos ainda precisam ser validados.

## Aplicação

No ambiente **da API publicada**, configurar:

```dotenv
FACILITIES_ENV=production
FACILITIES_ORIGIN=https://facilities.nexusdataanalytics.tech
FACILITIES_WEBHOOK_ORIGIN=https://facilities.nexusdataanalytics.tech
```

Preservar os segredos próprios do Facilities e as conexões PostgreSQL com papéis separados. Executar `python -m backend.migrate` com a credencial de migração antes de iniciar a API. Não reutilizar segredos do RotaFY nem expor o banco pelo Traefik.

## Rotas

Adicionar ao Compose **de publicação do Facilities**, adaptando os nomes dos serviços, a porta interna da API e as variáveis da infraestrutura já instalada. O trecho abaixo contém somente redes/labels; não constitui um Compose de publicação completo.

```yaml
services:
  facilities-api:
    networks: [traefik]
    labels:
      traefik.enable: "true"
      traefik.docker.network: ${TRAEFIK_NETWORK:?Informe a rede existente}
      traefik.http.routers.facilities-api.rule: Host(`facilities.nexusdataanalytics.tech`) && PathPrefix(`/api/`)
      traefik.http.routers.facilities-api.priority: "100"
      traefik.http.routers.facilities-api.entrypoints: ${TRAEFIK_HTTPS_ENTRYPOINT:?Informe o entrypoint existente}
      traefik.http.routers.facilities-api.tls: "true"
      traefik.http.routers.facilities-api.tls.certresolver: ${TRAEFIK_CERTRESOLVER:?Informe o resolver existente}
      traefik.http.routers.facilities-api.service: facilities-api
      traefik.http.services.facilities-api.loadbalancer.server.port: "8000"
  facilities-web:
    networks: [traefik]
    labels:
      traefik.enable: "true"
      traefik.docker.network: ${TRAEFIK_NETWORK:?Informe a rede existente}
      traefik.http.routers.facilities-web.rule: Host(`facilities.nexusdataanalytics.tech`)
      traefik.http.routers.facilities-web.priority: "10"
      traefik.http.routers.facilities-web.entrypoints: ${TRAEFIK_HTTPS_ENTRYPOINT:?Informe o entrypoint existente}
      traefik.http.routers.facilities-web.tls: "true"
      traefik.http.routers.facilities-web.tls.certresolver: ${TRAEFIK_CERTRESOLVER:?Informe o resolver existente}
      traefik.http.routers.facilities-web.service: facilities-web
      traefik.http.services.facilities-web.loadbalancer.server.port: "80"
networks:
  traefik:
    external: true
    name: ${TRAEFIK_NETWORK:?Informe a rede existente}
```

Esse padrão acompanha o Compose de produção do RotaFY, com nomes de routers/services exclusivos do Facilities. Referência das labels: [documentação oficial do Traefik](https://doc.traefik.io/traefik/reference/routing-configuration/other-providers/docker/).

O frontend publicado deve servir os arquivos de `frontend/dist`, retornar `index.html` nas rotas do aplicativo e manter CSP compatível com as imagens PNG `data:` dos QR Codes. Vite de desenvolvimento/preview não é o servidor de produção.

Não remover `/api/` com `StripPrefix`. O webhook precisa receber o corpo original e `X-Openwa-Signature`. Não aplicar autenticação interativa/BasicAuth ao webhook; a API exige assinatura HMAC específica da empresa. Não registrar corpos de requisições no proxy. Ao usar cabeçalhos de proxy no Uvicorn, autorizar somente os IPs reais do Traefik com `--proxy-headers --forwarded-allow-ips=<IPs-do-Traefik>`; não confiar em qualquer remetente. Isso preserva os limites de login por IP atrás do proxy.

## Validação na VPS

1. Confirmar DNS do domínio, certificado e rede compartilhada com o Traefik.
2. Confirmar que `GET https://facilities.nexusdataanalytics.tech/api/v1/health` retorna JSON `{"status":"ok"}`, e não HTML do frontend.
3. Confirmar que um POST sem assinatura em `/api/v1/webhooks/openwa/<empresa>` recebe `403`; não deve exigir cookie, `Origin` ou login no proxy.
4. Entrar como administrador do cliente, conectar o WhatsApp e clicar em **Ativar solicitações pelo WhatsApp**. O servidor cadastra o webhook `message.received` na sessão exclusiva da empresa.
5. Enviar uma mensagem de outro número, completar o fluxo e conferir protocolo, ocorrência, aviso interno e contadores de respostas. Reentregar o mesmo evento assinado não pode criar novo contato/ocorrência/resposta.

No dev em `127.0.0.1`, a URL pública configurada não encaminha mensagens para o computador por si só. O backend publicado nesse domínio precisa executar esta mesma versão e acessar seu banco. Não apontar a sessão de uma empresa real para bancos de teste.
