# Continuidade do Nexus Facilities OS

Atualizado em 23/10/2026. Referências: PDF funcional v1.0, diretrizes de segurança fornecidas e decisões desta conversa. O visual segue o Nexus RotaFY. Esta lista distingue recursos entregues de trabalho planejado; não representa implantação em produção.

O [escopo consolidado do projeto](ESCOPO_PROJETO.md) detalha a fase 1, suas pendências e a proposta de evolução posterior. Este arquivo mantém a continuidade imediata do desenvolvimento.

## Entregue — integrações e fundação

- Instalador Linux para VPS com Traefik existente, stack Docker própria, imagens de API/frontend, PostgreSQL privado e migração separada. Gera segredos, pede a senha do Superadmin no terminal, preserva credenciais nas reexecuções e faz backup antes das atualizações. Guia em `infra/INSTALACAO_VPS.md`. Verificado em containers locais; execução na VPS e validação pública permanecem pendentes.

- Tela de integrações OpenWA/Resend, segredos criptografados, substituição/remoção, testes explícitos e auditoria.
- Login no modelo visual do RotaFY: painel institucional, formulário com alternância de visibilidade da senha, versões de empresa/Nexus e apresentação compacta no celular. Autenticação e permissões existentes preservadas; redefinição web continua exclusiva das contas das empresas.
- PostgreSQL local isolado, papéis proprietários/runtime separados, migrações incrementais até `0010` e RLS/FORCE RLS nas 26 tabelas com dados privados. Metadados de migração sem dados privados em `schema_versions`.
- Superadmin restrito a empresas, integrações e auditoria, com bloqueio operacional também na API. Administrador do cliente gerencia estrutura, usuários e operação; dispõe do menu WhatsApp para iniciar a sessão exclusiva da empresa e ler o QR Code temporário.
- Empresas, suspensão, locais hierárquicos, criticidade e fuso por unidade.
- Cadastro completo de empresa seguindo os campos do RotaFY, sem plano, com administrador inicial, máscaras/validações de CPF/CNPJ e telefone, endereço e consulta de CEP pelo backend. Migração incremental `0003` preserva os registros anteriores. Tipo de operação adaptado ao Facilities; dados cadastrais detalhados são retornados apenas a Superadmin e administrador da empresa.
- Convites de uso único, senha definida pelo usuário, perfis acumuláveis e escopo por unidade.
- Recuperação de senha de contas ativas das empresas, com habilitação própria no Superadmin, resposta genérica, limites de solicitações, link de trinta minutos/uso único, troca transacional, encerramento das sessões e aviso por e-mail. Pedidos repetidos não invalidam o link vigente. Recuperação de contas Nexus não faz parte desse fluxo.
- Navegação e autorização de clientes; revogação de sessões ao alterar acesso ou suspender empresa.
- Auditoria por empresa e unidade, com consulta dos últimos cem eventos autorizados.
- Validação de API em SQLite/PostgreSQL, interface responsiva, teclado, Axe e fluxo de convite/login com API real.

O convite pode ser compartilhado manualmente ou enfileirado para Resend, após habilitação do Superadmin e solicitação explícita no cadastro/reemissão. A fila transacional protege o link temporariamente com criptografia, limita retentativas, cancela convites revogados/expirados e exibe o último resultado por usuário. Aceite do provedor não comprova entrega; homologação real e webhooks de entrega continuam pendentes. Calendários de funcionamento, equipes e organizações fornecedoras não estão implementados. O cadastro de fuso não equivale ao motor de SLA. Limites iniciais de listagem: 500 empresas, 1.000 usuários por empresa, 5.000 locais por empresa; paginar antes de ampliar essas escalas.

## Entregue — operação do piloto

1. Ativos básicos vinculados aos locais, categorias de serviço e responsáveis.
2. Ocorrência separada da ordem de serviço, com vários relatos por ordem.
3. Triagem por impacto/urgência; atribuição e execução com transições autorizadas.
4. Mensagens compartilhadas e notas internas com permissões distintas.
5. Resolução com evidência textual, confirmação/contestação pelo solicitante e reabertura justificada.
6. Notificações internas individuais, com leitura protegida por usuário.
7. Fotos JPEG/PNG privadas, com validação do conteúdo, limites, remoção de metadados, criptografia, download autorizado e remoção auditada. Fotos de relatos não são compartilhadas automaticamente com participantes da ordem. Limites e procedimento de uso no README.
8. Complementos textuais privados antes da OS, com autor/data, histórico preservado, reenvio idempotente, auditoria e notificações internas. Solicitante e coordenação escrevem; perfis de consulta autorizados apenas leem. A vinculação encerra os novos complementos e mantém a consulta privada.

Estados implementados: em triagem, atribuída, em execução, aguardando, resolvida e concluída; cancelamento e reabertura auditados. Conclusão automática permanece desabilitada no piloto. Uma contestação retoma a execução e abre novo ciclo; a próxima resolução exige novas confirmações. Atribuição preserva a primeira resposta registrada. Espera ainda não calcula nem pausa SLA. Solicitações críticas não devem depender exclusivamente do WhatsApp.

O Superadmin não acessa a operação em nenhum ambiente. Eventual suporte futuro exige perfil próprio e autorização pela empresa. Limites de listagem constam no README. Anexos de documentos/verificação de malware e filas para outras mensagens operacionais seguem pendentes antes de ampliar o piloto.

Próximos incrementos: homologar na VPS as etiquetas QR dos equipamentos e fotos recebidas, implementadas nesta entrega; etapa 3, acompanhamento/complementos/confirmação pelo WhatsApp. O usuário mostrou o fluxo textual funcionando. Checklist operacional e filtros por unidade/categoria/responsável permanecem no piloto web. Calendários/SLA vêm após essas pendências, antes de fornecedores/contratos/custos.

## WhatsApp no piloto

Ajuste de uso das etiquetas: telefone preenchido pelo número da sessão OpenWA vinculada à empresa, sem copiar o contato comercial; consulta protegida para administrador/supervisor e edição manual disponível. O bot aceita diretamente a mensagem do equipamento, o UUID ou o link completo da etiqueta, sem MENU. Se há rascunho em andamento, confirma retomar/substituir antes de descartar descrição/fotos. Primeiro contato coleta nome e segue com a seleção do QR preservada; confirmação final continua obrigatória.

Etapa 2 implementada: impressão individual e em lote dos ativos, seleção conforme filtro/acesso e A4; número de atendimento informado explicitamente antes da impressão; QR gerado localmente com identificador aleatório do ativo e link para enviar a mensagem no WhatsApp. Bot reconhece o identificador somente na empresa receptora ou permite pular para seleção manual. Até três fotos JPEG/PNG, normalizadas e criptografadas no rascunho, com confirmação transacional, deduplicação e cota. Reutiliza tabelas, migrações e permissões dos anexos existentes; não há nova migração. Homologação real de mídia/impressão pendente. Procedimento no README.

Diagnóstico de mídia (24/10): na sessão Facilities do provedor, a foto de aproximadamente 62 KiB apareceu com `omitted: true`, sem arquivo armazenado; o endpoint respondeu `No media stored for this message` e o histórico ao vivo também retornou somente o marcador. O usuário informou container `openwa-api`, imagem `rmyndharis/openwa:latest`, sem variáveis explícitas de download/arquivo no ambiente Docker. Erro interno do provedor ainda depende dos logs. Facilities passou a aceitar a foto inline do webhook assinado, com limite adequado para base64, e a distinguir arquivo ausente de falha genérica de rede. Nenhuma configuração do OpenWA ou de outros apps foi alterada.

Complemento do diagnóstico: o usuário forneceu logs `WhatsAppWebJsAdapter` com timeouts de download e `Runtime.callFunctionOn timed out`, referentes a mensagens `status@broadcast`. Isso aponta operações de mídia presas no Chromium, mas não identifica diretamente o erro da foto privada. O OpenWA em execução informa versão `0.24.0`; nessa versão o download é habilitado por padrão. Foi executado um reinício controlado somente da sessão `facilities-*` por `stop`/`start`, preservando a autenticação e o rascunho no Facilities. A sessão retornou `ready` e os estados das demais sessões permaneceram iguais. Validação com nova foto pendente; nenhum timeout, Compose ou versão do provedor foi modificado.

O administrador do cliente conecta pelo menu WhatsApp; a sessão usa nome exclusivo `facilities-{empresa}` e vínculo privado persistido. O usuário confirmou o QR de conexão funcionando. A API Key permanece global no Superadmin. Contratos de sessão e webhook foram localizados no RotaFY, sem copiar credenciais. QR de conexão não é persistido nem auditado; leituras são autenticadas e sem cache.

Etapa textual implementada: contato por empresa/telefone sem usuário/senha; nome no primeiro contato; unidade/local/equipamento opcional; descrição; resumo/confirmação; ocorrência na triagem; protocolo e aviso interno. Menus numerados com paginação, VOLTAR/CANCELAR/MENU e expiração de conversa. Categoria de entrada: Solicitações via WhatsApp. Webhook HMAC, deduplicação transacional, fila criptografada e contadores no cliente. Envio ambíguo não é repetido automaticamente. Nomes e posse de telefone não comprovam vínculo empregatício.

Infraestrutura informada: Traefik existente, vários apps na VPS, domínio `facilities.nexusdataanalytics.tech`. A [referência de publicação](infra/TRAEFIK.md) mantém host/routers/services próprios e rede externa existente. Na consulta desta sessão, o DNS resolveu para a VPS, mas o HTTPS apresentou certificado autoassinado; é necessário conferir router/resolver TLS e publicar a API nesta versão antes da homologação dos eventos. O dev local não recebe eventos da VPS somente por configurar o domínio. Nenhuma configuração dos outros apps foi alterada.

## Controle e inteligência — posterior à operação

- Calendários de unidade, horários úteis, feriados e SLA de primeira resposta/resolução. Espera exige motivo; somente motivos autorizados pausam prazo. Atribuição não reinicia contagem, resposta automática não conta como primeira resposta humana.
- Fornecedores com escopo próprio, contratos, orçamento versionado, alçadas e bloqueio de autoaprovação. Separar estimado, aprovado e realizado; custo desconhecido não é zero.
- Central de decisões por regras, reincidência, indicadores e evidências.
- Assistência de IA, base de conhecimento, preventivas e demais integrações somente após validar a base operacional e seus controles de acesso.

## Antes do uso real

Definir cliente e unidade piloto, responsáveis, categorias e metas de SLA; estabelecer retenção/descarte, revisar textos legais e compartilhamentos, validar infraestrutura/backup/restauração e acesso de suporte. Essas definições não impedem o desenvolvimento local, mas não podem ser apresentadas como validações concluídas.
