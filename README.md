# Nexus Facilities OS

Nexus Facilities OS para validação do piloto, seguindo a identidade visual do Nexus RotaFY. Inclui cadastros, ocorrências, ordens de serviço, permissões por unidade, auditoria e configuração de OpenWA/Resend.

Consulte o [escopo completo, entregas, pendências da fase 1 e próximas features](ESCOPO_PROJETO.md).

Veja também a [revisão de interface e segurança de 26/10/2026](REVISAO_UI_SEGURANCA.md), com melhorias aplicadas, testes de dados extremos e limites da validação.

## Recursos disponíveis

- Superadmin: somente cadastro/edição/suspensão de empresas, integrações e auditoria. Operação, estrutura física e gestão de usuários pertencem ao administrador do cliente; a API aplica a mesma separação, inclusive em desenvolvimento.
- Cadastro de empresa equivalente ao RotaFY, sem plano: nome comercial, razão social, identificador de acesso, CPF/CNPJ com validação de dígitos, telefone/WhatsApp, CEP, endereço, número, complemento opcional, bairro, cidade, UF, perfil operacional e administrador inicial com nome, e-mail e senha. Perfis operacionais do Facilities: escritórios, indústria, logística e uso misto. A senha inicial exige 12 caracteres, maiúscula e símbolo. Empresa e administrador são criados na mesma transação. A consulta ViaCEP ocorre pelo backend e permite preenchimento manual em caso de falha, sem sobrescrever alterações feitas durante a consulta.
- Empresa: acesso individual conforme perfil e unidades concedidas. Administradores gerenciam a própria equipe; supervisores organizam locais nas unidades autorizadas; os demais perfis consultam a estrutura dentro do escopo concedido. Auditoria disponível a administradores, gestores e auditores no seu escopo.
- Estrutura: unidade → prédio → andar → ambiente, com criticidade e fuso horário herdado da unidade. Não permite referências entre empresas nem inativação de um local com filhos ativos. Alterar hierarquia e exclusão definitiva não fazem parte desta etapa.
- Convite: link individual válido por 48 horas, de uso único, com hash na tabela de autenticação. O usuário define sua própria senha (mínimo 12 caracteres). O administrador pode compartilhar o link manualmente ou solicitar envio por e-mail, quando habilitado pelo Superadmin. Para envio, o corpo com o link fica temporariamente criptografado na fila e é limpo ao terminar/cancelar o processamento. Reemitir um convite invalida o anterior.
- Alterações de acesso encerram as sessões do usuário. Suspensão da empresa bloqueia login e acesso aos seus registros, preservando o histórico. O último administrador ativo com acesso configurado não pode ser removido ou desativado.
- Perfis acumuláveis: solicitante, técnico, supervisor, gestor, aprovador, auditor e administrador da empresa. Fornecedores e aprovações financeiras aguardam seus fluxos próprios.

### Operação do piloto

- Categorias de serviço e ativos vinculados aos locais, com criticidade, situação e consulta ao histórico de ordens.
- Ocorrência separada da ordem de serviço. O solicitante registra e acompanha seus relatos; a coordenação faz triagem por impacto × urgência e pode reunir relatos do mesmo local, categoria e ativo em uma ordem. Reenvios com o mesmo identificador de solicitação não duplicam ocorrências.
- Atribuição a profissionais ativos e autorizados na unidade; execução, espera justificada, resolução com solução e evidência textual, confirmação ou contestação pelo próprio solicitante, encerramento e reabertura justificada. Não há conclusão automática. Encerrar sem todas as confirmações exige revisão justificada; contestações retomam a execução.
- Mensagens compartilhadas, notas internas, linha do tempo e notificações individuais no aplicativo. Solicitantes não recebem notas internas nem os relatos de outros participantes. Técnicos consultam as ordens atribuídas; administradores e supervisores coordenam; gestores e auditores consultam no seu escopo. Auditor sem outro perfil não escreve.
- O Superadmin não acessa a operação das empresas. Para validar a operação, entre com o administrador inicial cadastrado na criação da empresa.

No detalhe da ocorrência, use **Adicionar complemento privado** antes da vinculação à OS. Solicitante e coordenação podem registrar textos de até 4.000 caracteres, com limite de cem por relato; perfis de consulta autorizados apenas leem. Autor/data e conteúdo ficam preservados, sem edição ou exclusão pela aplicação. O histórico não é copiado para as mensagens da OS nem liberado ao técnico por sua atribuição. Depois do vínculo, use a conversa da ordem para novas mensagens.

Prepare locais, categorias e usuários da operação antes de registrar ocorrências. Clientes usam `/app/ocorrencias` e `/app/ordens`, conforme seus perfis e unidades. Solicitantes pelo WhatsApp não precisam de cadastro prévio nem de usuário no painel; o fluxo textual foi demonstrado pelo usuário. Etiquetas QR dos equipamentos e fotos opcionais estão implementadas e aguardam homologação real na VPS. A resolução exige descrição e evidência textual; fotos privadas podem complementar o registro. Calendário/SLA ainda não está disponível.

### Fotos de evidência

Depois de registrar a ocorrência, abra o relato e use **Fotos de evidência**. Na ordem de serviço, o mesmo bloco permite compartilhar fotos com seus participantes ou, conforme o perfil, mantê-las internas. Fotos anexadas à ocorrência permanecem restritas ao próprio solicitante e a quem tem acesso à triagem; vinculá-la a uma ordem não compartilha automaticamente suas imagens. O técnico atribuído consulta os anexos da ordem, incluindo os internos, mas não as fotos privadas dos relatos.

- JPEG/PNG estáticos de até **5 MiB e 16 megapixels**, dez imagens por registro. O servidor verifica o formato real, decodifica e regrava somente os pixels, aplicando a orientação EXIF. Os originais, EXIF/GPS, comentários e perfis ICC não são armazenados. A imagem normalizada pode diferir do arquivo original e não é uma preservação forense do original.
- Conteúdo criptografado com a mesma chave Fernet da instalação, armazenado no banco privado, com RLS/FORCE RLS. Download autenticado por empresa, unidade, objeto e visibilidade, sem URL pública ou cache. O histórico e a auditoria registram ações sem conteúdo das fotos nem nomes de arquivo.
- Autor ou coordenação podem remover imagens enquanto o atendimento não estiver concluído/cancelado; na ordem, a remoção exige motivo e o registra na linha do tempo com a mesma visibilidade do anexo. A imagem sai do banco ativo; backups e conservação legal seguem os procedimentos de retenção, ainda pendentes de definição.
- Limites do piloto: **200 MiB de conteúdo normalizado por empresa**, dez tentativas de envio por usuário/minuto e dois processamentos simultâneos por processo da API. Reenviar a mesma imagem normalizada ao mesmo registro e visibilidade retorna o anexo existente. Não há aumento automático da cota.

O armazenamento no banco mantém arquivo, permissões e auditoria na mesma transação neste piloto. Migrar o conteúdo para armazenamento privado de objetos antes de ampliar a escala, mantendo criptografia, autorização e consistência. PDFs, SVG, arquivos de escritório, vídeos e HEIC não são aceitos; aceitar documentos exigirá validação e verificação de malware próprias. A normalização das imagens não equivale a uma certificação de ausência de malware. Referência de implementação: [Pillow Image](https://pillow.readthedocs.io/en/stable/reference/Image.html) e [orientação EXIF](https://pillow.readthedocs.io/en/stable/reference/ImageOps.html#PIL.ImageOps.exif_transpose).

Limites de listagem: 500 categorias, 1.000 ativos, 500 ocorrências/ordens e 100 notificações. Detalhes exibem até 500 mensagens e eventos por ordem. Paginar antes de ampliar o piloto além desses limites; indicadores referem-se às ordens listadas.

## Instalar na VPS

Use o [instalador para a VPS com Traefik existente](infra/INSTALACAO_VPS.md). Ele cria uma stack própria de produção, gera os segredos e preserva o banco nas atualizações. O Superadmin padrão é `admin@facilities.dev`; informe a senha já definida no terminal da VPS. A publicação real e o TLS ainda precisam ser validados nesse ambiente.

## Executar no Windows

Pré-requisitos: Python 3.12 ou superior, Node.js compatível com Vite 8 (Node 22.12+ ou 24) e Docker Desktop para o PostgreSQL local.

Na raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
.\.venv\Scripts\python.exe -m backend.dev_database
.\.venv\Scripts\python.exe -m backend.bootstrap
.\.venv\Scripts\python.exe -m uvicorn backend.main:create_app --factory --host 127.0.0.1 --port 8010
```

O provisionamento cria somente o projeto Docker `nexus-facilities`, PostgreSQL em `127.0.0.1:5452`, volume próprio e credenciais aleatórias em `.env.database`. Não modifica o RotaFY. O usuário proprietário aplica as migrações; a API usa papéis separados, sem superusuário, criação de papéis ou BYPASSRLS.

O bootstrap solicita e-mail e senha do Superadmin no terminal. Cria `.env` com hash de senha e chave de criptografia exclusiva. Não há senha padrão. Se o Superadmin já foi configurado, pule essa etapa. Preserve a chave de criptografia; sua substituição impede abrir credenciais anteriores. Restrinja acesso ao `.env`, `.env.database` e à pasta `data` no sistema operacional. Não copie credenciais do RotaFY.

Em outro terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Acesse **http://127.0.0.1:5180/nexus/empresas**. Use esse endereço, incluindo `127.0.0.1`, pois a API valida a origem. Para outra origem, ajuste `FACILITIES_ORIGIN` e a configuração de proxy/CSP. A conta Superadmin pode acessar `/nexus/configuracoes/integracoes`; usuários das empresas entram pelo mesmo formulário e recebem navegação adequada ao perfil.

Cadastre a primeira empresa e seu administrador inicial, depois prepare a estrutura física. O administrador já pode entrar com o e-mail e a senha inicial informados; ele pode então convidar a equipe e restringir os acessos às unidades necessárias. Cada e-mail corresponde a uma conta e uma empresa nesta etapa; não há alternância entre empresas na mesma conta de cliente.

### Banco e migrações

`python -m backend.dev_database` preserva o volume e as credenciais existentes. As migrações `0001` a `0010` são incrementais e podem ser reaplicadas, sem excluir dados. A `0010` acrescenta contatos sem login, conversa/fila privadas e solicitante de contato na ocorrência; a migração preserva relatos, ordens e anexos anteriores. A `0009` acrescenta o vínculo privado das sessões WhatsApp por empresa. A `0008` acrescenta o histórico privado de complementos das ocorrências. A `0007` acrescenta a recuperação de senha e separa as finalidades na fila. A `0006` acrescenta a fila privada de convites e sua habilitação, inicialmente desativada. A `0005` acrescenta os anexos de imagens e suas policies. A `0004` acrescenta as tabelas operacionais e suas políticas RLS. A `0003` acrescenta os campos cadastrais da empresa; dados que não existiam ficam em branco, sem inventar documentos, contatos ou endereços. Ao editar um cadastro anterior, complete os campos obrigatórios. Identificadores anteriores com hífen podem ser mantidos; novos identificadores e alterações usam de 2 a 50 letras minúsculas/números. Para um PostgreSQL externo, configure `FACILITIES_MIGRATION_DATABASE_URL`, `FACILITIES_DATABASE_URL` e `FACILITIES_PLATFORM_DATABASE_URL`; provisione os papéis seguindo `infra/init-db.sh` e execute `python -m backend.migrate` com a credencial proprietária.

As tabelas de configuração, autenticação, convites e limites são restritas ao papel da plataforma. Empresas, usuários, locais e auditoria têm RLS/FORCE RLS, com escopo de empresa por transação e restrições adicionais de unidade para locais e auditoria. Credenciais de conta ficam em tabela separada da listagem de usuários. A tabela `schema_versions` contém somente os identificadores de migração, sem dados privados.

Sem URLs PostgreSQL, o modo development permite SQLite para testes locais, com validação de escopo na API. SQLite não implementa RLS e é recusado fora desse modo. Alternar do SQLite para PostgreSQL **não importa automaticamente** registros do arquivo anterior; preserve o arquivo e planeje a importação se ele contiver dados. O provisionamento não copia dados ou segredos do RotaFY.

## Configurar os provedores

- OpenWA: insira a API Key, salve e use **Consultar sessões OpenWA**. A URL fica fixa no servidor conforme o guia fornecido; autenticação por `X-API-Key`. A consulta não envia mensagens. A sessão deve ser pareada no painel do provedor. A existência de chave cadastrada não comprova disponibilidade ou conexão.
- Resend: insira a API Key e um e-mail remetente de domínio verificado, salve e informe um destinatário para **Enviar e-mail de teste**. Esse botão envia uma mensagem real. O aceite da API não comprova entrega. Prefira chave limitada ao envio no domínio necessário. Referência: https://resend.com/docs/api-reference/emails/send-email.
- Campo de chave vazio preserva o valor anterior. A opção de remoção apaga a credencial ao salvar. A aplicação retorna apenas indicadores de configuração, nunca as chaves salvas.
- Os testes utilizam somente configurações salvas. Enquanto houver alterações, os botões de teste ficam desabilitados.

## Proteções e limites desta entrega

### Envio de convites pelo Resend

1. No Superadmin, configure chave e remetente de domínio verificado e habilite **Habilitar envio de convites por e-mail**. A migração mantém essa opção desativada; ter uma chave salva não habilita envios por si só.
2. Ao cadastrar usuário ou gerar novo convite, marque **Enviar convite por e-mail** se desejar o envio. A opção começa desmarcada e o link manual permanece disponível. Salvar grava usuário, convite e envio na mesma transação.
3. Na lista de usuários, use **Atualizar envios** para consultar o último resultado: na fila, em envio, nova tentativa agendada, aceito pelo Resend, falha ou cancelado. **Aceito pelo Resend não confirma entrega.** Não há webhook de entrega nesta etapa.

A API processa a fila em segundo plano enquanto está em execução; não há serviço de fila externo nem processamento com a API desligada. Envios pendentes sobrevivem à reinicialização. Desabilitar o envio pausa o processamento; reabilitar retoma os convites ainda válidos. Mensagens já enviadas ou em andamento não podem ser recolhidas.

São no máximo cinco tentativas, com intervalos de 1, 5, 15 e 60 minutos, respeitando `Retry-After` numérico do provedor até uma hora. Cada envio mantém payload e chave de idempotência estáveis. Retentativas/recuperação de processamento são limitadas a 23 horas desde a primeira tentativa, dentro da [janela de 24 horas documentada pelo Resend](https://resend.com/docs/dashboard/emails/idempotency-keys), e à validade do convite. Trocar a chave Resend interrompe jobs vinculados à credencial anterior; revise a integração e gere novo convite, se necessário. Remover a chave desabilita o envio.

Reemitir, usar ou revogar o convite e suspender o usuário/empresa cancelam os envios pendentes correspondentes; expiração é verificada pelo processador. O resultado de uma chamada já iniciada pode chegar após o cancelamento, mas não substitui seu estado e um link revogado não dá acesso. Em falhas, gere um novo convite apenas após revisar a situação; não há reprocessamento manual irrestrito de um job antigo.

A tabela privada `email_outbox` é exclusiva do papel de plataforma, com RLS/FORCE RLS. Administradores consultam somente metadados autorizados da própria empresa; chaves, payload e tokens da fila não são retornados. Não houve envio real a destinatários durante a implementação ou os testes. Domínio, chave e entrega precisam ser homologados na conta utilizada. Em dev, links `127.0.0.1` abrem somente na máquina do destinatário; configure a origem acessível correta antes do piloto externo.

### Recuperação de senha de usuários das empresas

No Superadmin, em **Integrações → Resend**, habilite **Habilitar recuperação de senha por e-mail** após configurar chave e remetente. Essa opção é independente do envio de convites e começa desativada na migração `0007`.

No login, o usuário acessa **Esqueci minha senha** (`/recuperar-senha`). A resposta é a mesma para e-mail inexistente, conta ainda não ativada, suspensão, envio desabilitado ou configuração indisponível. Há limite de dez solicitações por IP a cada quinze minutos e três por e-mail/hora; o limite por e-mail mantém a resposta genérica. Respostas curtas têm tempo mínimo com pequena variação para reduzir diferenças observáveis; isso não elimina todos os canais laterais de tempo.

Para contas ativas com senha já definida, a fila envia link de **30 minutos e uso único**. O token é aleatório, armazenado por hash na tabela privada `password_resets`, e só aparece temporariamente no corpo criptografado do e-mail pendente. O link usa a origem configurada no servidor, nunca o Host recebido. No navegador, o token chega no fragmento e é removido da URL; não vai em query string, armazenamento local nem no endpoint público de solicitação.

Um pedido repetido não substitui um link ainda válido nem reenvia o e-mail. Se não receber a mensagem, confira spam/administrador e aguarde o prazo do link antes de pedir outro, respeitando os limites. Falhas do provedor seguem as retentativas da fila e a validade de trinta minutos; não há envio após o vencimento.

A nova senha exige 12–128 caracteres, uma maiúscula e um caractere especial, seguindo a regra do administrador inicial, e deve ser diferente da atual. Ao confirmar, a transação altera a senha, consome o token, revoga as sessões da conta e os convites anteriores, cancela e-mails de recuperação pendentes e enfileira um aviso sem senha nem link de acesso. O usuário volta ao login; não há autenticação automática. O aviso é uma solicitação de envio, não uma garantia de entrega.

Suspensão do usuário/empresa, mudança de credencial ou desativação da recuperação invalidam os links correspondentes. Desativar a recuperação ou remover a chave Resend cancela pedidos pendentes; reabilitar não restaura esses links. Administradores não recebem tokens pela lista de usuários: o acompanhamento ali continua exclusivo de convites. A tabela de recuperação tem RLS/FORCE RLS e é exclusiva do papel de plataforma. A recuperação do **Superadmin Nexus não é feita por esse fluxo**; permanece sob responsabilidade da administração da instalação.

O processamento depende da API em execução e do Resend configurado. Não houve envio externo nos testes desta entrega. Referência de desenho: [OWASP — Forgot Password](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html).

### Controles gerais

Credenciais criptografadas com Fernet no servidor, sessão aleatória persistida por hash, cookie HttpOnly/SameSite, cookie CSRF separado, validação de origem e CSRF, autorização por perfil/empresa/unidade, limitação persistente de tentativas, bloqueio de redirecionamentos dos provedores, mensagens de erro sem respostas brutas ou segredos, auditoria de ações e controle de concorrência por versão. Cookies usam Secure quando a origem configurada é HTTPS.

O PostgreSQL local foi preparado para desenvolvimento e testes; isso não certifica a implantação em produção. Ambientes externos exigem PostgreSQL com RLS/FORCE RLS, papéis de runtime sem privilégios administrativos e origem HTTPS. TLS/proxy, backups, restauração, acesso de suporte, retenção e revisão dos textos legais ainda precisam ser preparados e validados antes de uso real. A credencial proprietária de migração não deve ficar no ambiente da API em produção.

Ainda não implementado: anexos de documentos e verificação de malware, SLA/calendários, fornecedores, contratos, aprovações financeiras, leitura de QR de equipamentos/fotos pelo WhatsApp, acompanhamento pelo WhatsApp e filas para outras mensagens operacionais, recuperação web de contas Nexus, gestão de equipe Nexus, MFA e páginas legais. O Resend atende teste explícito, convites solicitados pelos administradores e recuperação/aviso de senha das contas das empresas; não há confirmação de entrega por webhook. O guia OpenWA recebido documenta envio e consulta; não define o contrato de eventos recebidos. Não foram copiadas senhas ou chaves do documento original. O plano de continuidade está em `DESENVOLVIMENTO.md`.

## Verificação

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
npm run build
npm run test:e2e
```

Os testes de API verificam SQLite e, quando `.env.database` está disponível, PostgreSQL real em bancos aleatórios temporários `facilities_test_*`, criados e removidos pelo próprio teste. Não apagam dados do banco `facilities`. Incluem isolamento de empresas/unidades, RLS sem escopo, conexões reutilizadas, convites, suspensão, CSRF e proteção das credenciais. Sem PostgreSQL configurado, os respectivos cenários são marcados como ignorados.

O Playwright inicia uma API temporária em `127.0.0.1:8011` e o frontend em `127.0.0.1:5190`; essas portas devem estar livres e são distintas das portas do dev. A conta `e2e-admin@example.com` existe **somente no processo de testes** e usa banco temporário. Quatro cenários percorrem cadastros/acesso, fotos, fila de convites e recuperação de senha com API real; o Resend e a caixa de e-mail são sintéticos, sem entrega externa. A rota da caixa de teste é registrada somente em `backend.tests.serve_e2e`, nunca na API normal. Os demais cenários simulam respostas para verificar erros, navegação, teclado e acessibilidade em desktop/mobile. ViaCEP não é acionado durante os testes. Para instalar o navegador: `npx playwright install chromium`.

O build mantém CSP restrita à própria origem. Somente o servidor de desenvolvimento remove a meta CSP para permitir os scripts e estilos do HMR.

## Conectar WhatsApp da empresa

1. O Superadmin configura a API Key do OpenWA em Integrações. A chave precisa permitir criar e iniciar sessões.
2. Entre com o administrador do cliente e acesse **WhatsApp** (`/app/whatsapp`). Clique em **Conectar WhatsApp**.
3. No aparelho da empresa, abra **Aparelhos conectados → Conectar um aparelho** e leia o QR Code. A tela consulta o status por até dois minutos; use **Atualizar conexão** para continuar ou renovar o QR.

Uma sessão exclusiva `facilities-{empresa}` é criada ou recuperada pelo servidor. O navegador não recebe a API Key nem pode escolher sessões. Repetir a conexão reutiliza o vínculo; consultas concorrentes são bloqueadas temporariamente. O QR é imagem PNG validada, transitória e sem cache, nunca registrada no banco ou na auditoria. Se o provedor perder a sessão ou perder permissão para ela, a interface informa a falha; excluir/substituir sessões e desconectar pelo aplicativo ficam para uma etapa posterior.

O contrato de criação/inicialização/status/QR segue o módulo local do RotaFY. O usuário confirmou o funcionamento do QR de conexão. O recebimento de solicitações tem habilitação própria, descrita abaixo; a homologação dos eventos na VPS continua pendente.

## Abertura guiada pelo WhatsApp — texto, QR do equipamento e fotos

Após publicar a API com HTTPS válido, configurar `FACILITIES_WEBHOOK_ORIGIN=https://facilities.nexusdataanalytics.tech` e seguir a [referência do Traefik existente](infra/TRAEFIK.md). No administrador do cliente, em **WhatsApp → Abertura de solicitações**, usar **Ativar solicitações pelo WhatsApp**. A API registra o webhook na sessão exclusiva da empresa e cria a categoria de entrada **Solicitações via WhatsApp**. A categoria precisa permanecer ativa. Desativar impede novas interações, descarta rascunhos e cancela respostas ainda na fila; um envio já em andamento pode terminar.

O contrato foi localizado no módulo `whatsapp_automation.py` do RotaFY: `message.received`, `sessionId`, `timestamp`, `data.id/from/fromMe/isGroup/body/type`, assinatura `X-Openwa-Signature: sha256=<HMAC-SHA256 do corpo original>` e segredo exclusivo por empresa. O webhook aceita remetentes individuais com telefone confirmado (`@c.us`, `@s.whatsapp.net` ou identificador privado resolvido pelo provedor); grupos, mensagens do próprio bot, eventos antigos e sessões divergentes são ignorados. Identificadores privados `@lid` são resolvidos pela consulta autenticada `/sessions/{sessao}/contacts/{id}/phone`, encontrada no RotaFY; seus dígitos nunca são tratados como telefone. A resolução ocorre fora da transação de gravação, com assinatura/sessão verificadas antes e depois, limite por empresa e falha temporária se o provedor não confirmar o número.

Fluxo: apresentação/orientação de privacidade → nome no primeiro contato → QR do equipamento ou unidade/local/equipamento manual → descrição → fotos opcionais → resumo → confirmação → ocorrência e protocolo. Menus possuem oito opções por página, com MAIS/ANTERIOR. Há VOLTAR, CANCELAR e MENU. Um local não cadastrado pode ser informado em texto dentro de uma unidade existente; sem equipamento identificado, seu nome/código pode ser incluído na descrição. Os cadastros de ativos não são alterados automaticamente. A ocorrência aparece na triagem e pode gerar uma OS; a confirmação de resolução pelo WhatsApp pertence à terceira etapa. Até lá, a conclusão exige revisão justificada pela coordenação quando não houver confirmação do solicitante.

Contatos são separados de `users`/`auth_accounts`: nenhum login, senha ou permissão é gerado. Nome e posse do telefone não comprovam vínculo empregatício. O telefone fica criptografado; a busca usa HMAC por empresa, com chave derivada da chave da instalação. O mesmo número pode representar contatos diferentes em empresas diferentes. A aplicação operacional consulta o nome autorizado, sem acesso SQL à coluna do telefone. Conteúdo de conversa e respostas pendentes fica criptografado e não entra na auditoria.

Cada evento tem deduplicação transacional: confirmação, ocorrência, notificação interna e resposta são persistidas juntas. Protocolo só é enfileirado após a gravação e não é cancelado ao iniciar outro rascunho. O worker envia fora da transação, em ordem por contato. Não há garantia de idempotência de envio documentada pelo OpenWA: timeout, resposta ambígua ou processo interrompido durante envio resultam em **resultado não confirmado**, sem repetição automática. Os contadores ficam na tela do cliente. Aceite não comprova entrega; o colaborador pode retomar com MENU após revisão do WhatsApp.

Limites do piloto: trinta mensagens novas/minuto por telefone/empresa; eventos de até trinta minutos, tolerância de cinco minutos no futuro; conversa expira após 24 horas; descrição de 10 a 3.000 caracteres; uma hora para entregar respostas pendentes. Conteúdo enviado/cancelado/não confirmado é limpo da fila; metadados de eventos/entregas são descartados após trinta dias, e rascunhos expirados são removidos pelo worker. Retenção de contatos e ocorrências depende do procedimento de privacidade ainda a formalizar. O worker precisa da API em execução. Catálogos seguem os limites do piloto (até 5.000 locais/1.000 ativos), sem ampliação de escala presumida.

### Imprimir etiquetas dos equipamentos

No administrador ou supervisor da empresa, abra **Ativos → Imprimir QR Codes**. A impressão oferece os equipamentos não baixados do filtro atual, com seleção individual ou de todos, dentro das unidades autorizadas e do limite de 1.000 ativos do piloto. No cadastro existente, use **Imprimir QR Code deste equipamento**; a linha do ativo também possui um botão de impressão. O campo de telefone é preenchido automaticamente com o número da sessão WhatsApp vinculada à empresa; permite ajuste ou preenchimento manual se a consulta não estiver disponível. Não utiliza o telefone comercial como substituto automático. Confira o destino, gere a pré-visualização e imprima em A4, escala 100%, sem cabeçalhos/rodapés. São duas etiquetas por linha. Equipamentos baixados ou com locais/ancestrais inativos não geram etiquetas.

O QR é gerado localmente com [qrcode](https://pypi.org/project/qrcode/), sem serviço externo, e contém um [link de conversa do WhatsApp](https://faq.whatsapp.com/5913398998672934) com a mensagem `EQUIPAMENTO <identificador aleatório do ativo>`. O colaborador lê a etiqueta pela câmera do celular e **envia a mensagem preenchida**; ler o QR sozinho não registra uma ocorrência. A sessão receptora determina a empresa e valida o equipamento/local. O identificador não é senha nem concede acesso ao painel. Confira o número de destino antes de imprimir; se o atendimento mudar de número, reimprima as etiquetas. Sem etiqueta, escolha **0 — Pular QR Code** no diálogo. Não se trata de reconhecer uma foto do QR enviada ao bot.

Também é possível enviar diretamente no WhatsApp o conteúdo da etiqueta: a mensagem `EQUIPAMENTO ...`, o identificador ou o link completo `https://wa.me/...?...` gerado pelo sistema. Não exige MENU: contatos conhecidos seguem para a descrição com equipamento/local identificados; no primeiro contato, pede somente o nome antes de continuar. O link é interpretado localmente, sem acessar URLs recebidas. Se houver rascunho com descrição/fotos, oferece retomar ou confirmar seu descarte para iniciar pelo novo QR. A ocorrência e o protocolo continuam sendo criados somente após descrição e confirmação.

### Fotos recebidas pelo WhatsApp

Após a descrição, envie até **três fotos JPEG/PNG**, uma por mensagem, usando o clipe/câmera do WhatsApp, ou digite **0** para seguir. Cada foto admite até **5 MiB e 16 megapixels** e recebe as mesmas verificações e remoção de metadados do upload web. Legendas não substituem a descrição textual. Áudio, vídeo, documentos e outros formatos ficam fora desta etapa. Digite **REMOVER FOTOS** para descartar as fotos do rascunho; **0** encerra o envio e apresenta o resumo com sua contagem.

Quando o webhook assinado já contém `data.media.data` em base64, a foto é validada diretamente. Caso contrário, o download usa o endpoint autenticado fixo `/sessions/{sessão}/messages/{chat}/{mensagem}/media`. A assinatura, sessão, remetente, idade/deduplicação do evento e etapa de conversa são verificados antes de processar a imagem. URLs fornecidas na mensagem não são acessadas; redirecionamentos são recusados. Falha ou formato inválido gera orientação para reenviar ou continuar sem a foto. Fotos enviadas fora da etapa solicitada não são baixadas. O limite do corpo do webhook acomoda 5 MiB em base64 mais o envelope; os limites das outras rotas permanecem independentes.

Se o OpenWA responder **No media stored for this message**, o arquivo não está disponível no provedor. Isso pode ocorrer com download desativado, limite excedido ou falha de download no próprio OpenWA; não se resolve aumentando o limite do Facilities. O histórico ao vivo também pode retornar apenas `omitted: true`. Consulte [mídia no OpenWA](https://docs.open-wa.org/guides/sending-messages/) e [mídia nos webhooks](https://docs.open-wa.org/guides/webhooks/). Para conferir somente as opções de mídia do container, sem exibir chaves, execute `sudo python3 scripts/check_openwa_media.py openwa-api` na VPS. O diagnóstico não altera configurações. Caso os valores estejam adequados, investigue os erros de download nos logs do provedor, sem compartilhar tokens, telefones ou URLs de mídia. Após corrigir o provedor, envie uma nova foto; não há recuperação garantida de uma mídia nunca armazenada.

Fotos normalizadas ficam no rascunho criptografado, expiram com a conversa e são descartadas ao cancelar/recomeçar/desativar. Só a confirmação cria ocorrência e anexos na mesma transação. A cota de 200 MiB por empresa também limita conservadoramente os rascunhos pendentes (pelo tamanho criptografado). Ao mudar unidade/local/equipamento pelo diálogo, fotos do rascunho anterior são descartadas. Os anexos confirmados ficam privados na ocorrência e não são compartilhados automaticamente com o técnico da OS. O download no painel mantém as permissões existentes.

Geração de etiquetas, diálogos e recebimento de fotos foram testados localmente; impressão física, leitura em aparelhos e eventos reais de mídia precisam de homologação na VPS. Acompanhamento, complementos e confirmação/contestação pelo WhatsApp continuam pendentes. Não há IA no diálogo.
