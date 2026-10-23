# Continuidade do Nexus Facilities OS

Atualizado em 23/10/2026. Referências: PDF funcional v1.0, diretrizes de segurança fornecidas e decisões desta conversa. O visual segue o Nexus RotaFY. Esta lista distingue recursos entregues de trabalho planejado; não representa implantação em produção.

O [escopo consolidado do projeto](ESCOPO_PROJETO.md) detalha a fase 1, suas pendências e a proposta de evolução posterior. Este arquivo mantém a continuidade imediata do desenvolvimento.

## Entregue — integrações e fundação

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

Próximos incrementos: homologar a abertura textual na VPS/Traefik; etapa 2, QR dos equipamentos e fotos recebidas; etapa 3, acompanhamento/complementos/confirmação pelo WhatsApp. Checklist operacional e filtros por unidade/categoria/responsável permanecem no piloto web. Calendários/SLA vêm após essas pendências, antes de fornecedores/contratos/custos.

## WhatsApp no piloto

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
