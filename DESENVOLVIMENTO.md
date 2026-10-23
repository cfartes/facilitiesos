# Continuidade do Nexus Facilities OS

Atualizado em 23/10/2026. Referências: PDF funcional v1.0, diretrizes de segurança fornecidas e decisões desta conversa. O visual segue o Nexus RotaFY. Esta lista distingue recursos entregues de trabalho planejado; não representa implantação em produção.

## Entregue — integrações e fundação

- Tela de integrações OpenWA/Resend, segredos criptografados, substituição/remoção, testes explícitos e auditoria.
- PostgreSQL local isolado, papéis proprietários/runtime separados, migrações incrementais e RLS/FORCE RLS nas nove tabelas com dados privados. Metadados de migração sem dados privados em `schema_versions`.
- Empresas, suspensão, locais hierárquicos, criticidade e fuso por unidade.
- Cadastro completo de empresa seguindo os campos do RotaFY, sem plano, com administrador inicial, máscaras/validações de CPF/CNPJ e telefone, endereço e consulta de CEP pelo backend. Migração incremental `0003` preserva os registros anteriores. Tipo de operação adaptado ao Facilities; dados cadastrais detalhados são retornados apenas a Superadmin e administrador da empresa.
- Convites de uso único, senha definida pelo usuário, perfis acumuláveis e escopo por unidade.
- Navegação e autorização de clientes; revogação de sessões ao alterar acesso ou suspender empresa.
- Auditoria por empresa e unidade, com consulta dos últimos cem eventos autorizados.
- Validação de API em SQLite/PostgreSQL, interface responsiva, teclado, Axe e fluxo de convite/login com API real.

O convite ainda é compartilhado manualmente por link. Calendários de funcionamento, equipes e organizações fornecedoras não estão implementados. O cadastro de fuso não equivale ao motor de SLA. Limites iniciais de listagem: 500 empresas, 1.000 usuários por empresa, 5.000 locais por empresa; paginar antes de ampliar essas escalas.

## Próximo bloco — operação do piloto

1. Ativos básicos vinculados aos locais, categorias de serviço e responsáveis.
2. Ocorrência separada da ordem de serviço, com vários relatos por ordem.
3. Triagem por impacto/urgência; atribuição e execução com transições autorizadas.
4. Mensagens compartilhadas e notas internas com permissões distintas.
5. Arquivos privados com limites, validação e verificação de conteúdo.
6. Resolução com evidências, confirmação/contestação e reabertura justificada.
7. Notificações internas e convites por e-mail com fila e tratamento de falhas.

Estados propostos: em triagem, atribuída, em execução, aguardando, resolvida e concluída; cancelamento e reabertura auditados. Conclusão automática permanece desabilitada no piloto. Solicitações críticas não devem depender exclusivamente do WhatsApp.

## WhatsApp no piloto

Utilizar OpenWA após vincular sessões exclusivas por empresa, verificar a identidade do solicitante e homologar os eventos recebidos. O guia disponibilizado cobre envio e consulta, sem contrato de webhooks. Consultar o módulo correspondente do RotaFY como referência, sem presumir compatibilidade nem reutilizar suas credenciais.

Fluxo guiado proposto: identificar solicitante, coletar unidade/local, descrição e foto opcional, confirmar resumo, persistir a ocorrência e só então informar o protocolo. Reenvios não podem criar relatos duplicados. Conexão, fila, falhas e reprocessamentos devem ser observáveis. IA não é necessária para esse fluxo.

## Controle e inteligência — posterior à operação

- Calendários de unidade, horários úteis, feriados e SLA de primeira resposta/resolução. Espera exige motivo; somente motivos autorizados pausam prazo. Atribuição não reinicia contagem, resposta automática não conta como primeira resposta humana.
- Fornecedores com escopo próprio, contratos, orçamento versionado, alçadas e bloqueio de autoaprovação. Separar estimado, aprovado e realizado; custo desconhecido não é zero.
- Central de decisões por regras, reincidência, indicadores e evidências.
- Assistência de IA, base de conhecimento, preventivas e demais integrações somente após validar a base operacional e seus controles de acesso.

## Antes do uso real

Definir cliente e unidade piloto, responsáveis, categorias e metas de SLA; estabelecer retenção/descarte, revisar textos legais e compartilhamentos, validar infraestrutura/backup/restauração e acesso de suporte. Essas definições não impedem o desenvolvimento local, mas não podem ser apresentadas como validações concluídas.
