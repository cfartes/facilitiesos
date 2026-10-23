# Instalação do Facilities na VPS

Destino: **https://facilities.nexusdataanalytics.tech/nexus**. O instalador usa o Traefik existente e cria somente a stack `nexus-facilities-production`, com PostgreSQL privado, migrações, API e frontend. Não instala outro proxy, não publica portas do banco e não altera as stacks dos demais apps.

## Pré-requisitos

- VPS Linux com Python **3.10+**, Git, Docker e plugin Docker Compose com suporte a `up --wait`. Não é necessário instalar Node.js ou dependências Python no host: o build ocorre nos containers.
- Traefik em container, com **provider Docker**, rede Docker própria compartilhável, entrypoint HTTPS e resolver de certificados já configurados. Instalações exclusivamente Swarm precisam de adaptação antes de executar este Compose.
- DNS do domínio apontando para a VPS e portas 80/443 acessíveis no Traefik, conforme o desafio TLS utilizado. O instalador não modifica DNS, firewall ou configuração estática do proxy.
- Acesso ao Docker e permissão de escrita no checkout. Use o mesmo usuário para clonar, atualizar e instalar; os exemplos abaixo usam `sudo`.

## Primeira instalação

```bash
sudo git clone --branch feat/foundation https://github.com/cfartes/facilitiesos.git /opt/nexus-facilities
cd /opt/nexus-facilities
sudo bash scripts/install_vps.sh
```

O Superadmin usa **admin@facilities.dev**. Quando solicitado, informe e confirme **a mesma senha já definida para o projeto**. Ela não aparece no terminal, no histórico ou no repositório; somente seu hash é persistido. O instalador exige 12 a 128 caracteres, incluindo maiúscula e símbolo. A conta de produção não depende da cópia do banco de desenvolvimento.

A detecção procura o container do Traefik, sua rede e os nomes do entrypoint HTTPS e do resolver TLS. Quando houver mais de uma opção, escolha o valor usado na VPS. Se necessário, informe explicitamente, substituindo os nomes do exemplo pelos reais:

```bash
sudo bash scripts/install_vps.sh \
  --traefik-container traefik \
  --network proxy_public \
  --entrypoint websecure \
  --resolver letsencrypt
```

`--admin-email` permite definir outro e-mail somente na primeira instalação. Para automação sem terminal, `--password-file /caminho/privado/senha` aceita um arquivo regular com permissão `600`; não envie esse arquivo ao Git e remova-o quando não for mais necessário. O fluxo interativo é suficiente para esta instalação.

## O que acontece

1. Verifica Docker, Compose, checkout sem alterações locais e configuração existente. Uma instalação em outro diretório ou volume sem os segredos originais interrompe o processo.
2. Gera três senhas independentes do banco e uma chave de criptografia exclusiva; grava `.env.production` com permissão `600`. Aspas simples preservam o hash com `$` na leitura do Compose.
3. Constrói API e frontend com imagens-base fixadas por digest. A API roda com usuário sem privilégios; os builds excluem arquivos locais de segredos e dados.
4. Inicia PostgreSQL em rede interna e aplica as migrações com a credencial proprietária. A API recebe somente as credenciais de execução, com papéis separados e RLS.
5. Inicia API e frontend e adiciona seus routers ao provider Docker do Traefik. O banco não é roteado pelo proxy e nenhum serviço publica portas no host.
6. Confere saúde dos containers e o HTTPS público, incluindo o identificador da versão em `X-Facilities-Release`. Só informa instalação validada se a resposta vier desta versão do Facilities com certificado válido.

O instalador confia em cabeçalhos de proxy somente do IP detectado do Traefik na rede selecionada. Se o Traefik for recriado com outro IP, execute novamente o instalador para atualizar esse valor.

## Atualizações e preservação de dados

No mesmo diretório e com o mesmo usuário:

```bash
cd /opt/nexus-facilities
sudo git pull --ff-only
sudo bash scripts/install_vps.sh
```

Reexecuções preservam e-mail, hash, chave de criptografia e senhas do banco. Não geram um novo acesso nem aceitam trocar credenciais pelas opções de primeira instalação. Alterações locais no checkout interrompem a instalação para revisão; nenhum reset é executado.

Antes de migrar um banco existente, o instalador constrói as imagens, pausa somente a API do Facilities e cria um `pg_dump` no formato customizado. Os backups ficam em `data/backups/`, junto de cópias protegidas da configuração. Há uma breve indisponibilidade do Facilities durante backup, migração e reinício. Os outros apps continuam em execução.

**Preserve `.env.production` e seus backups fora da VPS em local privado.** A chave é necessária para abrir integrações, contatos e anexos criptografados; perder essa configuração impede recuperar esses conteúdos. O volume do banco é `nexus-facilities-production_facilities_data`. Não use `down --volumes` nessa stack. O instalador não transfere dados nem chaves do ambiente local.

O backup automático ocorre antes das atualizações, não em agenda recorrente. Defina a rotina de cópia externa e retenção operacional antes do uso contínuo. Não há restauração nem rollback automático: se uma etapa falhar, banco e configuração são preservados para diagnóstico. Se a API já tiver sido pausada, ela poderá permanecer indisponível até resolver a falha e reexecutar o instalador.

## Diagnóstico

```bash
cd /opt/nexus-facilities
sudo docker compose --project-name nexus-facilities-production --env-file .env.production -f compose.production.yaml ps
sudo docker compose --project-name nexus-facilities-production --env-file .env.production -f compose.production.yaml logs --tail 100 api web
curl --fail --show-error --include https://facilities.nexusdataanalytics.tech/api/v1/health
```

O endpoint deve responder `{"status":"ok"}` e um cabeçalho `X-Facilities-Release` correspondente ao commit instalado. Não compartilhe `.env.production`, dumps nem a saída completa de `docker compose config` ou `docker inspect`, pois podem conter segredos.

Se o HTTPS apresentar certificado autoassinado, confira o resolver, a emissão do certificado e os routers no Traefik. Não desative a validação TLS para contornar o problema. A consulta inicial do domínio antes da instalação apresentou esse problema; a publicação real precisa confirmar sua correção. Se já existir um router específico para o mesmo domínio com outro destino, revise esse conflito no Traefik antes de concluir a instalação.

## Após entrar

1. Entre como Superadmin, cadastre a empresa e seu administrador inicial.
2. Configure OpenWA e Resend em **Integrações**. As chaves do desenvolvimento não são copiadas automaticamente.
3. Entre como administrador da empresa para conectar o WhatsApp por QR Code e preparar locais/categorias. Para habilitar o recebimento de solicitações, siga também [a configuração e homologação do webhook](TRAEFIK.md).

O instalador e as imagens foram verificados localmente com Docker, PostgreSQL, migrações e autenticação. Isso não substitui executar a instalação e homologar TLS, rotas e provedores na VPS real.

Referências: [Compose e espera por saúde](https://docs.docker.com/reference/cli/docker/compose/up/), [interpolação de variáveis e valores literais](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/) e [roteamento pelo provider Docker do Traefik](https://doc.traefik.io/traefik/reference/routing-configuration/other-providers/docker/).
