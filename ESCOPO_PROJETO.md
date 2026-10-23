# Nexus Facilities OS — escopo, entregas e evolução

**Atualização:** 23/10/2026 — horário de Brasília.

**Referência do código analisado:** branch `feat/foundation`, migrações até `0010`.

**Repositório:** [cfartes/facilitiesos](https://github.com/cfartes/facilitiesos).

**Situação:** aplicação em desenvolvimento e validação local; fase 1 ainda não concluída nem homologada para produção.

## 1. Objetivo do produto

Conectar ocorrências, ambientes, ativos, pessoas, fornecedores e custos para organizar a operação física da empresa. O gestor deve conseguir identificar o que precisa de ação, quem é responsável, qual é o prazo e como o resultado foi comprovado.

Fluxo principal: **registrar → triar e priorizar → atribuir → executar → comprovar → confirmar → medir**.

O produto atende empresas com uma ou várias unidades, escritórios, fábricas e centros de distribuição, com equipes próprias e, nas etapas posteriores, prestadores externos. A primeira validação deve ocorrer em uma unidade, com poucas categorias e responsáveis definidos.

## 2. Fontes e decisões de escopo

| Fonte | Uso neste documento |
| --- | --- |
| [PDF funcional v1.0](Facilities_OS_Funcionalidades.pdf), de 23/10/2026 | Visão completa de atendimento, cadastros, controle, integrações e inteligência |
| [Diretrizes fornecidas de segurança, privacidade e acessibilidade](REGRAS_E_DIRETRIZES_SEGURANCA_PRIVACIDADE_ACESSIBILIDADE.md) | Requisitos de proteção e itens a adaptar ao Facilities |
| Decisões desta conversa | Visual do RotaFY, cadastro de empresa sem plano, OpenWA, Resend, desenvolvimento e publicação no GitHub |
| [README](README.md) e [continuidade do desenvolvimento](DESENVOLVIMENTO.md) | Operação da instalação e sequência de trabalho |
| Código de backend, frontend, migrações e testes | Conferência do que está efetivamente implementado |

As diretrizes fornecidas descrevem recursos e evidências do RotaFY. Isso não significa que todas essas funcionalidades já existam no Facilities. Políticas, módulos, fornecedores e resultados de testes daquele sistema não são considerados entregas deste projeto.

Decisões já estabelecidas:

- Manter a identidade visual e os padrões de interação do **Nexus RotaFY**.
- Usar os mesmos campos do cadastro de empresa do RotaFY, **sem plano de uso**.
- Utilizar **OpenWA** para a futura entrada de relatos e comunicação por WhatsApp.
- Disponibilizar ao Superadmin a configuração das chaves OpenWA e Resend.
- Preservar dados separados por empresa, com restrições adicionais por unidade e objeto.
- Manter a aplicação web responsiva, com uso pelo celular e conexão à internet.
- Não depender de IA para abrir, triar, executar ou concluir um atendimento.
- Não concluir atendimentos automaticamente no piloto.

## 3. Organização das fases

O PDF organiza a evolução por momentos, sem numerar uma “fase 1”. Para o acompanhamento, este documento adota a divisão abaixo como **proposta de organização**. A priorização das pendências é uma recomendação; não representa prazo, orçamento ou ampliação de escopo já aprovados.

| Fase | Resultado esperado | Situação atual |
| --- | --- | --- |
| **1 — Fundação e operação do piloto** | Cadastros, acesso, ocorrências, ordens, responsáveis, comunicação, evidências e confirmação; preparação e homologação do piloto | Em andamento; núcleo operacional disponível em dev |
| **2 — Controle operacional e financeiro** | Calendários, SLA, equipes, fornecedores, contratos, custos, aprovações e indicadores completos | Não implementada |
| **3 — Central de decisões e assistência de IA** | Alertas explicáveis, reincidência, recomendações e assistência sob revisão humana | Não implementada |
| **4 — Evoluções e integrações avançadas** | Procedimentos, preventivas, ERP/manutenção, identidade corporativa, sensores e análises avançadas | Não implementada; depende da validação e das necessidades do cliente |

Segurança, privacidade, acessibilidade e isolamento de dados são requisitos de todas as fases. A preparação para produção faz parte da conclusão do piloto; não deve ser adiada apenas por estar descrita em uma seção técnica.

## 4. Escopo completo por módulo

**Legenda:** “implementado” significa disponível no código para validação em desenvolvimento; “parcial” significa que apenas parte do módulo existe; “pendente” significa que o recurso ainda precisa ser desenvolvido ou validado.

| Módulo | Escopo do produto | Estado atual | Etapa de conclusão proposta |
| --- | --- | --- | --- |
| Administração Nexus | Empresas, acesso administrativo e configurações globais | Parcial: Superadmin, empresas e integrações entregues; equipe Nexus e suporte autorizado pendentes | Fase 1 para o suporte necessário ao piloto; evolução administrativa conforme necessidade |
| Cadastro da empresa | Dados equivalentes ao RotaFY, administrador inicial, ativação e suspensão; sem plano | Implementado | Fase 1 |
| Identidade e acesso | Login individual, convite, perfis, escopos, recuperação e autenticação corporativa | Parcial: login, convite, permissões e recuperação de contas das empresas entregues; recuperação Nexus, MFA e SSO pendentes | Fase 1 para requisitos do piloto; SSO conforme adoção corporativa |
| Locais | Unidade, prédio, andar, ambiente, criticidade, fuso, responsáveis e calendário | Parcial: hierarquia, criticidade e fuso entregues | Fase 2 para calendário e organização ampliada |
| Ativos | Identificação, categoria, local, situação, criticidade, documentos e histórico | Parcial: cadastro e histórico de ordens entregues; documentos próprios do ativo pendentes | Fase 1 para a base; fase 2 para documentação ampliada |
| Categorias de serviço | Catálogo de tipos de atendimento | Implementado no cadastro básico | Fase 1; parametrizações de SLA/checklist em etapas seguintes |
| Portal do solicitante | Relatar problema, anexar evidência, acompanhar, complementar e confirmar/contestar | Fluxo web entregue, incluindo complementos privados antes da OS; homologação do piloto pendente | Fase 1 |
| Triagem | Impacto, urgência, encaminhamento e reunião de relatos sobre um problema | Implementado manualmente | Fase 1; sugestões de duplicidade por IA na fase 3 |
| Ordens de serviço | Lista/quadro, filtros, atribuição, atividades, checklist, mensagens, anexos, orçamento e histórico | Parcial: fluxo de atendimento entregue; checklist, filtros completos e orçamento pendentes | Fase 1 para operação; fase 2 para orçamento, prazo e fornecedor |
| Comunicação | Mensagens compartilhadas, notas internas e notificações | Parcial: comunicação no aplicativo e fila de convites entregues; demais mensagens externas pendentes | Fase 1 |
| Evidências | Texto, fotos e documentos privados conforme necessidade e autorização | Parcial: texto e fotos JPEG/PNG entregues; documentos gerais pendentes | Fase 1 para fotos; documentos após definição e validação próprias |
| WhatsApp / OpenWA | Relatos, identificação do solicitante, protocolos e atualizações | Parcial: conexão, webhook assinado e abertura textual por contato sem login implementados; homologar na VPS, adicionar QR de equipamento/fotos e acompanhamento | Fase 1, condicionado à homologação do provedor |
| E-mail / Resend | Convites e comunicações operacionais com tratamento de falhas | Parcial: configuração, teste, convites, recuperação/aviso de senha, fila e retentativas entregues; demais mensagens e confirmação de entrega pendentes | Fase 1 |
| Equipes e fornecedores | Equipes próprias, organizações prestadoras, cobertura e acesso restrito | Pendente; usuários técnicos individuais já existem | Fase 2 |
| Contratos de serviço | Vigência, escopo, anexos, cobertura, metas, limites e vencimentos | Pendente | Fase 2 |
| Calendários e SLA | Metas de resposta/resolução, horários úteis, feriados e pausas autorizadas | Pendente; fuso e registros iniciais de tempo já existem | Fase 2 |
| Custos e aprovações | Propostas versionadas, alçadas, segregação de funções e custo realizado | Pendente; perfil aprovador cadastrado sem fluxo financeiro | Fase 2 |
| Indicadores | Tempos, SLA, backlog, reincidência, custos e fornecedores | Parcial: contadores das ordens listadas; análises gerenciais pendentes | Fase 2 |
| Central de decisões | Agir agora, aprovar, investigar e otimizar, com evidências e ações | Pendente | Fase 3 |
| Assistência de IA | Classificar, resumir e sugerir duplicidades com revisão humana | Pendente | Fase 3 |
| Procedimentos e conhecimento | Consultar documentos aprovados, com versão, trecho e autorização | Pendente | Fase 4 |
| Preventivas e dependências | Programação de manutenção e relações entre ambientes, ativos e atividades | Pendente | Fase 4 |
| Integrações corporativas | ERP/manutenção, identidade, sensores e ocupação agregada | Pendente | Fase 4, ou antecipação por necessidade comprovada do piloto |
| Privacidade, acessibilidade e produção | Controles de acesso, direitos dos titulares, políticas, operação segura e validações | Parcial: controles técnicos básicos entregues; páginas, processos e infraestrutura de produção pendentes | Transversal; requisitos do uso real antes da entrada em produção |

## 5. O que já foi implementado

### 5.1. Fundação, interface e administração

- Frontend React/TypeScript e backend FastAPI, com identidade visual baseada no RotaFY.
- Navegação para Superadmin e usuários das empresas, com interface responsiva.
- Login seguindo o visual do RotaFY, com painel institucional, formulário, visibilidade de senha e alternância entre portal da empresa e Administração Nexus; versão compacta para celular.
- Cadastro, edição e suspensão de empresas.
- Campos da empresa: nome comercial, razão social, identificador de acesso, CPF/CNPJ, telefone/WhatsApp, CEP, endereço, número, complemento opcional, bairro, cidade, UF e perfil operacional.
- Perfis operacionais da empresa: escritório, indústria, logística e uso misto.
- Administrador inicial com nome, e-mail e senha; criação conjunta da empresa e da conta em uma transação.
- Validação de CPF/CNPJ e telefone, máscaras e consulta de CEP pelo backend, permitindo preenchimento manual.
- Nenhum cadastro de plano de uso ou cobrança por plano.

### 5.2. Usuários e permissões

- Login e logout por sessão em cookie; credenciais protegidas no servidor.
- Recuperação de senha das contas ativas das empresas, com habilitação independente no Superadmin, resposta genérica e limites por IP/e-mail. Link de trinta minutos, de uso único, restrito à conta e à credencial vigente; pedidos repetidos não revogam o link válido.
- Troca de senha transacional, com encerramento das sessões, invalidação de links anteriores e aviso por e-mail sem senha/link. O retorno é ao login normal. Contas Nexus não são recuperadas por esse fluxo público.
- Convite de uso único, válido por 48 horas, para o usuário definir a própria senha.
- Reemissão de convite com invalidação do anterior; compartilhamento manual ou envio opcional por Resend, habilitado pelo Superadmin.
- Usuário/convite e envio gravados na mesma transação, com corpo criptografado enquanto pendente, no máximo cinco tentativas e chave de idempotência estável dentro da janela segura.
- Cancelamento de envios pendentes por substituição, uso, expiração ou suspensão; consulta do último resultado por usuário, sem expor o token da fila. Aceite do provedor não confirma entrega.
- Perfis acumuláveis: solicitante, técnico, supervisor, gestor, aprovador, auditor e administrador da empresa.
- Acesso à própria empresa, com todas as unidades ou apenas unidades concedidas.
- Revogação de sessões ao alterar acessos ou suspender a empresa.
- Proteção contra remoção/desativação do último administrador ativo com acesso configurado.
- Superadmin restrito a cadastro de empresas, integrações e auditoria, inclusive em desenvolvimento. Estrutura, usuários e operação são administrados pelo cliente. Eventual suporte operacional futuro requer perfil próprio e autorização da empresa.

O perfil de aprovador não significa que aprovações financeiras estejam disponíveis. A configuração atual associa cada e-mail a uma conta e uma empresa; alternância entre empresas por uma mesma conta de cliente não está implementada.

### 5.3. Locais, ativos e categorias

- Hierarquia **unidade → prédio → andar → ambiente**, com empresa e unidade de referência.
- Criticidade e fuso horário da unidade, herdado pelos níveis inferiores.
- Validações para impedir vínculos entre empresas e inativação de local com filhos ativos.
- Categorias de serviço com ativação/inativação; alteração do catálogo compartilhado exige coordenação com abrangência adequada.
- Ativos vinculados ao local, com código, nome, categoria do equipamento, criticidade e situação.
- Situações do ativo: ativo, fora de serviço e retirado de uso.
- Consulta ao histórico de ordens de um ativo, respeitando o acesso do usuário.

Categorias de equipamento e categorias de serviço são informações distintas. Calendário de funcionamento, responsáveis estruturados por local e documentos anexados diretamente ao ativo ainda não existem.

### 5.4. Ocorrências e triagem

- Abertura de relato com título, descrição, local, categoria e ativo opcional.
- Registro do próprio solicitante ou, pela coordenação, em nome de pessoa ativa e autorizada na unidade.
- Protocolo individual e proteção contra duplicação por reenvio com o mesmo identificador de solicitação.
- Ocorrência separada da ordem de serviço.
- Complementos privados de até 4.000 caracteres, limitados a cem por relato, com autor/data, reenvio idempotente e notificação interna. Solicitante e coordenação escrevem antes da vinculação; o histórico permanece privado e sem edição/exclusão pela aplicação após a criação da OS.
- Criação de uma OS a partir do relato e vinculação manual de outros relatos à mesma OS.
- Vinculação exige o mesmo local, categoria e ativo; não existe sugestão automática de duplicidade.
- Solicitantes consultam seus próprios relatos; estar na mesma OS não libera os relatos privados de outras pessoas.
- Prioridade calculada por impacto e urgência, ambos de 1 a 4: produto 1–3 baixo, 4–7 médio, 8–11 alto e 12–16 crítico.
- Primeira resposta humana registrada no complemento da coordenação ao solicitante ou no encaminhamento manual do relato; mensagens do próprio solicitante não contam. Isso ainda não constitui um motor de SLA ou um indicador homologado.

### 5.5. Atendimento e ordens de serviço

- Listagem e quadro por situação, busca textual e filtros de situação/prioridade.
- Histórico filtrado por ativo a partir de seu cadastro.
- Atribuição a técnico, supervisor ou administrador ativo e autorizado na unidade.
- Estados: **em triagem, atribuída, em execução, aguardando, resolvida, concluída e cancelada**.
- Início/retomada, espera com motivo, resolução com descrição e evidência textual e cancelamento justificado.
- Confirmação ou contestação pelo próprio solicitante do relato.
- Contestação retoma a execução e abre novo ciclo; a próxima resolução exige novas confirmações.
- Encerramento pela coordenação, com confirmações ou justificativa de revisão autorizada quando houver confirmações pendentes. Contestação pendente impede o encerramento.
- Reabertura justificada, preservando o histórico dos ciclos anteriores.
- Controle de concorrência por versão nas alterações de estado e atribuição.
- Ausência de encerramento automático; trocar o responsável não reinicia o registro da primeira resposta.

Os filtros dedicados por unidade, categoria e responsável ainda não estão completos. Filtros por fornecedor e prazo dependem de módulos futuros. A espera registra o motivo, mas não calcula nem pausa SLA.

### 5.6. Mensagens, notificações e evidências

- Mensagens compartilhadas e notas internas com acesso distinto.
- Linha do tempo e auditoria de ações.
- Notificações individuais no aplicativo, com marcação de leitura.
- Texto de solução e evidência de verificação obrigatórios na resolução; fotos complementares opcionais.
- Fotos JPEG/PNG estáticas de até **5 MiB e 16 megapixels**, até dez imagens por registro.
- Validação do formato real, decodificação e regravação dos pixels, com orientação da foto e remoção de metadados, como EXIF/GPS.
- Conteúdo das imagens criptografado no banco; download autenticado e sem cache ou URL pública.
- Imagens da ocorrência restritas ao solicitante e aos perfis com acesso à triagem; não são propagadas automaticamente à OS.
- Imagens da OS compartilhadas com participantes ou internas, conforme permissão. O técnico atribuído acessa os anexos da OS, incluindo os internos, sem acesso automático às fotos privadas dos relatos.
- Remoção pelo autor ou coordenação enquanto o atendimento não estiver concluído/cancelado; na OS, motivo obrigatório registrado com a mesma visibilidade do anexo.

Limites atuais de imagens: **200 MiB de conteúdo normalizado por empresa**, dez tentativas de envio por usuário/minuto e dois processamentos simultâneos por processo da API. Reenvio da mesma imagem normalizada ao mesmo registro e visibilidade reutiliza o anexo existente. A normalização não preserva o original para uso forense nem equivale à verificação de malware de documentos gerais.

### 5.7. Integrações disponíveis

| Integração | Disponível hoje | Ainda não disponível |
| --- | --- | --- |
| OpenWA | Chave no Superadmin, sessão exclusiva e QR de conexão; cliente ativa webhook assinado; contato sem login, abertura textual com resumo/confirmação, protocolo, fila criptografada e contadores de respostas | Homologação dos eventos na VPS/Traefik, QR dos equipamentos/fotos e acompanhamento/atualizações pelo WhatsApp |
| Resend | Chave, remetente, teste explícito, habilitação separada para convites/recuperação, fila transacional, retentativas limitadas e aviso de senha alterada; resultado do último convite por usuário | Confirmação de entrega por webhook, outras mensagens operacionais e homologação real da conta |
| ViaCEP | Consulta de endereço pelo backend com preenchimento manual alternativo | Não é integração operacional de atendimento |

Chave cadastrada não comprova conexão ativa. O usuário confirmou o funcionamento do QR de conexão. Aceite pelo provedor não comprova entrega. O guia OpenWA recebido documenta envio/consulta; o contrato de webhooks foi localizado posteriormente no código do RotaFY e implementado com testes simulados. Homologação real dos eventos ainda depende da publicação e TLS válido na VPS.

### 5.8. Segurança e estrutura técnica

- PostgreSQL local isolado, com migrações incrementais até `0010` e preservação dos dados existentes.
- RLS/FORCE RLS nas 26 tabelas privadas; metadados de migração separados.
- Papéis distintos para migração, plataforma e aplicação; runtime sem privilégios administrativos ou BYPASSRLS.
- Escopo de empresa por transação e verificações adicionais por unidade, objeto e perfil na API.
- Sessões e convites autenticados por hash; segredos de integração, conteúdo das fotos e corpo temporário de convites na fila criptografados. O corpo da fila é limpo quando o processamento termina ou é cancelado.
- Validação de origem/CSRF, limites de requisição e tentativas, consultas parametrizadas e respostas sem segredos brutos.
- Cookies HttpOnly/SameSite; Secure para origem HTTPS, exigida fora do ambiente de desenvolvimento.
- CSP, escape de texto no frontend, foco/teclado em diálogos e testes automatizados de acessibilidade.
- SQLite restrito a desenvolvimento/testes, sem equivalência à proteção RLS do PostgreSQL.

Esses controles não significam certificação de conformidade LGPD, acessibilidade integral ou infraestrutura de produção validada.

## 6. O que falta para concluir a fase 1

As pendências abaixo compõem a **recomendação de fechamento do piloto**, considerando a visão do PDF e as decisões da conversa. Não são funcionalidades já entregues.

| Prioridade | Pendência | Resultado necessário |
| --- | --- | --- |
| 1 | Homologação real de convites Resend | Fluxo, fila, limites e consulta de falhas implementados; falta validar domínio, conta, remetente, origem acessível e recebimento real |
| 1 | Homologação da recuperação de senha | Fluxo para contas das empresas implementado e testado; validar recebimento real, disponibilidade e procedimento de suporte. Recuperação Nexus continua administrativa |
| 1 | WhatsApp via OpenWA | Homologar na VPS o fluxo textual implementado; completar leitura de QR/fotos e acompanhamento, com identidade por empresa/telefone e protocolo após persistência |
| 1 | Confiabilidade de mensagens | Distinguir enfileirado, aceito pelo provedor, entregue quando comprovado e falho; evitar duplicação e permitir reprocessamento autorizado |
| 1 | Privacidade e páginas legais do Facilities | Adaptar termos, política, cookies e compartilhamentos; disponibilizar canal e acompanhamento dos pedidos de titulares com procedimentos definidos |
| 1 | Suporte Nexus em produção | Acesso autorizado pela empresa, temporário, limitado e auditado; definir necessidade de outros perfis Nexus e MFA antes de liberar acesso externo |
| 1 | Preparação de produção e homologação | HTTPS, segredos, infraestrutura, monitoramento, backups/restauração, teste de isolamento e aprovação do cliente piloto |
| 2 | Checklist operacional | Itens de execução/verificação e regras de obrigatoriedade acordadas com a operação piloto |
| 2 | Filtros operacionais dedicados | Unidade, categoria e responsável, mantendo o escopo de acesso; fornecedor e prazo entram com a fase 2 |
| 2 | Regras de evidência por serviço | Definir quando fotos/checklist são obrigatórios e como comprovar a resolução; hoje só o texto é obrigatório |
| 2 | Paginação e capacidade do piloto | Paginar consultas que ultrapassem os limites atuais; dimensionar banco e imagens conforme volume real |
| Condicionada | PDFs e outros documentos privados | Confirmar necessidade no piloto e implementar tipos permitidos, limites, validação, verificação de malware, autorização e retenção antes de aceitar arquivos |

O recebimento textual pelo WhatsApp está implementado para homologação, sem exigir usuários previamente cadastrados. Contatos são identificados pela empresa/sessão e pelo telefone, e o nome é coletado no primeiro contato; isso não comprova vínculo empregatício. QR/fotos dos equipamentos e acompanhamento pelo canal são etapas posteriores. O fluxo externo ainda não deve ser marcado como homologado enquanto não for validado na VPS.

### 6.1. Fluxo desejado para WhatsApp

1. Receber evento autenticado e reconhecer reenvios do provedor.
2. Identificar o usuário e verificar seu vínculo com empresa/unidade, sem assumir que possuir um número de telefone concede acesso.
3. Coletar local, descrição, categoria e ativo quando aplicável; foto opcional conforme as regras de evidência.
4. Apresentar resumo para confirmação do solicitante.
5. Persistir a ocorrência uma única vez e então retornar o protocolo.
6. Encaminhar à triagem normal e enviar atualizações permitidas, sem expor notas internas ou relatos de terceiros.
7. Exibir situação da conexão, filas, falhas e reprocessamentos; manter o portal como alternativa.

Esse fluxo pode ser determinístico, sem IA. Solicitações críticas precisam de orientação operacional que não dependa exclusivamente da disponibilidade do WhatsApp.

### 6.2. Critérios propostos de aceite da fase 1

- Empresa piloto, unidade, categorias e responsáveis cadastrados; matriz de acesso validada pelos perfis participantes.
- Fluxo completo no portal: relato → triagem → atribuição → execução/espera → evidências → resolução → confirmação/contestação → encerramento/reabertura.
- Vários relatos na mesma OS sem acesso indevido a relatos, fotos ou notas de outras pessoas.
- Convite e recuperação de acesso funcionais com tratamento de falhas de e-mail.
- Fluxo WhatsApp homologado, incluindo evento repetido e falha do provedor, ou exceção de escopo explicitamente acordada, mantendo a pendência visível.
- Checklist, evidências obrigatórias e filtros definidos para a operação piloto implementados e testados.
- Privacidade, suporte e requisitos de autenticação externa definidos e atendidos; nenhuma alegação de conformidade baseada apenas nos testes do código.
- Teste de backup e restauração, proteção de segredos e ambiente de produção validado.
- Homologação funcional, de permissões e acessibilidade com usuários reais do piloto.

## 7. Próximas features depois da fase 1

### 7.1. Fase 2 — Controle operacional e financeiro

| Frente | Features previstas | Regras e dependências |
| --- | --- | --- |
| Calendários | Horário por unidade, dias úteis, feriados e exceções | Considerar o fuso da unidade; definir critérios com a operação |
| SLA | Metas de primeira resposta e resolução por serviço/criticidade, vencimentos e alertas | Somente atendimento humano qualificado conta como primeira resposta; pausa exige motivo autorizado; troca de responsável não reinicia prazo; ciclos preservados |
| Equipes | Agrupamento de profissionais, responsáveis e cobertura por unidade/categoria | Permissões por equipe precisam complementar as restrições atuais de empresa/unidade |
| Fornecedores | Organizações, contatos, serviços, cobertura e acesso próprio | Cada fornecedor acessa somente trabalho da própria organização e dados necessários à execução |
| Contratos | Vigência, escopo, anexos, cobertura por categoria/unidade, metas e alertas de vencimento | Validar acesso e documentos; não substituir revisão jurídica |
| Orçamentos | Valor, moeda, justificativa, fornecedor, escopo e versões de proposta | Alteração relevante exige nova aprovação; preservar proposta anterior |
| Aprovações | Alçadas financeiras, aprovar/rejeitar e histórico de decisões | Impedir autoaprovação; validar escopo e versão da proposta antes da decisão |
| Custos | Estimado, aprovado e realizado registrados separadamente | Custo ausente não equivale a zero; não executar pagamento automaticamente |
| Indicadores | Tempos de resposta/resolução, SLA, backlog, vencidos, reincidência, custo por resolução e desempenho de fornecedores | Usar consultas completas e recortes autorizados, distinguindo relatos duplicados de novas falhas |
| Cadastros ampliados | Responsáveis por local, documentação de ativos e consultas cruzadas com contratos | Preservar histórico e permissões; ampliar armazenamento e paginação conforme escala |

Para indicadores de economia, separar oportunidade estimada de economia realizada. Comparações exigem base, período, volume, escopo e custos de implantação/operação identificados; não existe percentual de economia garantido.

### 7.2. Fase 3 — Central de decisões e assistência de IA

| Frente | Features previstas | Condições |
| --- | --- | --- |
| Agir agora | Ordens críticas, SLA próximo do vencimento, atrasos e contratos a vencer | Regras configuradas, dados de origem acessíveis e ação concreta |
| Aprovar | Fila de propostas que dependem de decisão | Depende de orçamento versionado e alçadas da fase 2 |
| Investigar | Reincidência por categoria, ambiente ou ativo em janela definida | Não confundir múltiplos relatos do mesmo evento com novas ocorrências |
| Otimizar | Oportunidades sustentadas por histórico e premissas explícitas | Distinguir estimativa de resultado comprovado |
| Assistência de IA | Sugerir categoria, resumir histórico e apontar possíveis duplicidades | Revisão humana, proteção por empresa/objeto, avaliação de qualidade e tratamento de indisponibilidade |

Cada recomendação deverá apresentar problema, local/ativo, motivo, evidências com data, responsável, ação sugerida e validade. A IA não aprova despesas, concede acesso, controla equipamentos ou comprova economia sozinha. Textos, mensagens e documentos recebidos são dados não confiáveis, não instruções para executar ferramentas.

### 7.3. Fase 4 — Evoluções condicionadas à validação

- **Conhecimento e procedimentos:** busca em documentos aprovados, com versão, trecho e referência; consulta apenas a conteúdo autorizado e indicação de evidência insuficiente.
- **Manutenção preventiva:** programação, geração controlada de atendimentos e acompanhamento de execução.
- **Dependências:** mapa entre ativos, ambientes e atividades para apoiar a avaliação de impacto.
- **ERP e sistemas de manutenção:** começar por importação/sincronização controlada e somente leitura, com rastreabilidade e reprocessamento.
- **Identidade corporativa:** integração com provedor do cliente e políticas de autenticação; pode ser antecipada se necessária para a adoção do piloto.
- **Sensores e ocupação:** sinais de ambientes e dados agregados de uso, condicionados à infraestrutura e à avaliação de necessidade/privacidade.
- **Análises e cenários:** oportunidades e simulações com premissas explícitas; modelos preditivos somente com histórico suficiente e qualidade comprovada.

Essas evoluções não têm datas, estimativas de esforço ou fornecedores contratados definidos neste documento.

## 8. Requisitos transversais e pendências externas

| Tema | Base existente | Trabalho necessário antes de ampliar o uso |
| --- | --- | --- |
| Isolamento | Empresa/unidade/objeto, RLS e verificações da API | Estender a equipe, fornecedor, contratos, financeiro e futuras integrações |
| Privacidade | Minimização em formulários, orientações em campos livres, controle de acesso e proteção das fotos | Textos do Facilities, responsabilidades/bases aplicáveis, pedidos de titulares, retenção, descarte e procedimentos sobre backups |
| Integrações | Segredos no backend e testes controlados | Homologar contas, domínios, sessões, eventos, contratos e compartilhamentos com os provedores utilizados |
| Auditoria | Registro de ações, autores e histórico operacional | Abranger novos módulos e decisões; definir conservação e acesso aos registros |
| Acessibilidade | Diálogos por teclado, foco e cenários Axe em desktop/celular | Revisão humana, leitores de tela e dispositivos/fluxos reais do piloto |
| Segurança de entrega | Verificações locais de dependências e segredos realizadas nas entregas | Automatização contínua no próprio repositório, manutenção de versões e resposta a incidentes |
| Operação | Banco e serviços locais para desenvolvimento | Ambiente externo, TLS/proxy, monitoramento, alertas, backups/restauração e configuração de acesso administrativo |

Não copiar automaticamente políticas comerciais ou integrações exclusivas do RotaFY. Plano de assinatura, cobrança, cancelamento/reembolso de assinatura, mapas e integrações financeiras daquele sistema não foram incluídos no Facilities por semelhança técnica.

## 9. Limites atuais e itens fora da primeira versão

### 9.1. Limites atuais do piloto

| Recurso | Limite implementado |
| --- | --- |
| Empresas | 500 na listagem |
| Usuários e locais | 1.000 usuários e 5.000 locais por empresa nas consultas |
| Catálogos operacionais | 500 categorias e 1.000 ativos |
| Atendimento | 500 ocorrências/ordens nas listagens; indicadores referem-se ao conjunto listado |
| Histórico por OS | Até 500 mensagens e 500 eventos exibidos |
| Notificações | Últimas 100 por usuário |
| Fotos | Dez por registro; até 5 MiB/16 megapixels por imagem; 200 MiB normalizados por empresa |
| Contas | Uma empresa por conta de cliente; sem alternância entre empresas |

As imagens estão no banco para manter consistência transacional no piloto. Ampliar o uso exige rever capacidade e migrar para armazenamento privado de objetos com as mesmas garantias de autorização e consistência. Remover do banco ativo não equivale a apagar backups.

### 9.2. Fora da primeira versão

- Uso offline e sincronização de alterações sem conexão.
- Aplicativo nativo para Android/iOS.
- Controle físico automático de equipamentos.
- Pagamentos automáticos.
- Aprovações autônomas e concessão de acesso por IA.
- Predição de falhas sem dados históricos suficientes.

Planos de uso e cobrança por plano não fazem parte do escopo definido para este projeto. Qualquer inclusão futura depende de decisão expressa.

## 10. Sequência recomendada de desenvolvimento

1. **Homologar acesso e e-mail:** convites e recuperação de senha das empresas já implementados; validar recebimento e suporte. Mensagens operacionais, recuperação Nexus e confirmação de entrega seguem como incrementos próprios.
2. **Homologar OpenWA em paralelo à preparação operacional:** validar na VPS o contrato de eventos encontrado no RotaFY, identidade de contato, sessão por empresa e abertura textual sem duplicação.
3. **Completar o piloto web:** informação adicional no relato, checklist, filtros e regras de evidência acordadas com a unidade piloto.
4. **Preparar entrada em produção:** privacidade, suporte autorizado, autenticação necessária, infraestrutura e restauração; homologar os fluxos ponta a ponta.
5. **Iniciar fase 2:** calendários/SLA, equipes e fornecedores, contratos, orçamento/custos/aprovações e indicadores.
6. **Iniciar fase 3:** central por regras e depois assistência de IA avaliada com dados reais autorizados.
7. **Priorizar fase 4 pelos resultados do piloto:** conhecimento, preventivas e integrações corporativas conforme necessidade e infraestrutura.

Decisões operacionais ainda necessárias: cliente/unidade piloto, categorias iniciais, responsáveis, critérios de checklist/evidência, metas de atendimento, regras de suporte, canal de verificação de identidade no WhatsApp e procedimentos de privacidade/retenção. A necessidade de MFA/SSO e de documentos além de fotos deve ser definida para o ambiente de uso real.

## 11. Validação e atualização deste documento

A implementação foi conferida nos módulos de [fundação](backend/foundation.py), [operação](backend/operations.py), [tratamento de imagens](backend/attachments.py), [fila de e-mails de acesso](backend/email_outbox.py), [recuperação de senha](backend/password_reset.py), [API e integrações](backend/main.py), [provedores](backend/providers.py), [schema](backend/schema.py), [políticas operacionais](backend/operation_schema.py) e nas telas correspondentes em `frontend/src`.

As verificações registraram suíte de API em SQLite/PostgreSQL, build e 45 cenários web aprovados, incluindo quatro fluxos com API real, fila/caixa de e-mail sintéticas, recuperação de senha, complementos privados, privacidade de fotos e acessibilidade em desktop/celular. O login também foi verificado por teclado, Axe e revisão visual em 1440/390 px. A fila também possui testes de cancelamento, retomada após perda de processamento, limite de tentativas, rotação de chave e janela de idempotência. Isso não comprova homologação dos provedores com contas reais, validação de produção ou revisão jurídica.

O ambiente local de validação é [Nexus Facilities OS dev](http://127.0.0.1:5180/nexus/empresas), quando os serviços locais estiverem em execução. Não há implantação externa de produção documentada como concluída.

Ao finalizar uma entrega, atualizar o estado do módulo, remover a respectiva pendência somente após verificar o fluxo e registrar dependências ainda não homologadas. Este arquivo concentra o escopo; o README continua sendo a referência de instalação/uso e `DESENVOLVIMENTO.md`, a referência de continuidade imediata.
