# Revisão de interface e segurança — 26/10/2026

Escopo: interface React do Facilities, com foco no shell, formulários compartilhados, ativos, etiquetas e conexão WhatsApp; segurança das rotas de autenticação, autorização/isolamento, imagens, webhooks e diagnóstico de logs. Mantida a identidade visual do Nexus RotaFY. Revisão de código e testes locais, sem ataque ativo à VPS ou alteração do OpenWA.

Skills aplicadas: `emil-design-eng`, `break-ui`, `mobile-native` e `animation-performance`, com a orientação de mudanças mínimas do Ponytail. As regras de animação foram usadas para manter o feedback curto e evitar efeitos adicionais em listas e formulários de uso frequente.

## Melhorias de interface

| Antes | Depois | Motivo e localização |
| --- | --- | --- |
| E-mail longo ocupava várias linhas e aumentava o cabeçalho | Linha única com reticências e valor completo em `title` | Estabilidade visual; `frontend/src/App.tsx` e `styles.css` |
| Inicial obtida cortando uma unidade UTF-16, exibindo símbolo corrompido em nomes com emoji | Primeiro grafema completo via `Intl.Segmenter`; fallback para nome ausente/vazio | Respeitar caracteres compostos; `frontend/src/App.tsx` |
| Campos com fonte de 14 px também em toque | Campos dos formulários com 16 px quando `pointer: coarse` | Evitar zoom automático ao focar campos no iOS; `frontend/src/operations.css` |
| Hover aplicado sem verificar o dispositivo | Hover condicionado a mouse preciso; feedback `:active` também em toque | Evitar estado hover persistente no celular; `frontend/src/styles.css` |
| Botões de ícone de 40 px e ações compactas menores | Área mínima de 44 px em controles de toque | Facilitar acionamento; `frontend/src/styles.css` |
| Cabeçalho do modal podia sair de vista durante a rolagem | Cabeçalho permanece acessível e rolagem não encadeia para a página | Fechar formulários longos em tela baixa; `frontend/src/foundation.css` |
| Impressão encostada no próximo campo; “1 selecionados” e “etiqueta(s)” | Espaço dedicado e singular/plural correto | Hierarquia e texto; `OperationForms.tsx`, `AssetLabels.tsx`, `styles.css` |
| Duas dimensões/espaçamentos via estilo inline nos componentes WhatsApp | Classes do projeto | Manter apresentação no CSS compartilhado; `WhatsAppConnection.tsx`, `WhatsAppIntake.tsx` |

Não foi adicionado pacote de animação, virtualização, tema novo ou biblioteca de componentes. Não há mudanças de permissões ou de fluxo operacional nesta melhoria visual.

## Testes com dados extremos

O catálogo e o seletor de empresa foram exercitados com o mesmo formato de dados usado pela API. Limites verificados no código: nome do ativo até 160 caracteres, identificação até 40, categoria de 2 a 100 e catálogo limitado a 1.000 ativos. Foram usados nomes portugueses longos, acentos, texto japonês/vietnamita, emoji composto, nome curto válido, e-mail corporativo longo e campos opcionais da empresa ausentes.

| Severidade observada | Campo/caso | Comportamento anterior | Correção |
| --- | --- | --- | --- |
| Quebrado | Inicial `👩🏽‍🔧 Jo` | Emoji cortado em um substituto Unicode isolado | Grafema completo em `frontend/src/App.tsx:1067` |
| Visual | E-mail corporativo longo | Cabeçalho crescia em altura | Linha única em `frontend/src/styles.css:282` e valor completo em `frontend/src/App.tsx:1073` |
| Frágil | Formulários no celular | Fonte abaixo de 16 px e controles pequenos | `frontend/src/styles.css:1154` e `frontend/src/operations.css:471` |
| Visual | Uma etiqueta selecionada | Texto no plural e sufixo “(s)” | Singular/plural em `frontend/src/AssetLabels.tsx:150` |

Casos que se mantiveram: tabelas contêm sua própria rolagem horizontal; nomes longos não escondem ações fora da página; lista vazia tem orientação; um item e mil itens renderizam; conteúdo ampliado a 200% no cenário desktop não gera rolagem horizontal da página. O limite de mil itens continua sendo um limite de piloto; não foi demonstrado desempenho de escala superior nem 60 fps em aparelhos reais.

O seletor **Demo data / Worst case / Empty / One / 1,000 rows** é injetado somente pelo teste `frontend/tests/ui-stress.spec.ts`, na borda dos dados simulados. A escolha fica em `?ui-case=...` durante o teste. Não há botão de teste ou rota de dados falsos no bundle de produção. Para inspeção interativa, execute `npx playwright test tests/ui-stress.spec.ts --headed --debug` dentro de `frontend` e avance até a página carregada. Capturas são gravadas em `frontend/test-results/`.

## Segurança

### Achado corrigido

**Exposição condicional de credenciais em diagnóstico local — baixa.** `scripts/check_openwa_media.py` ocultava URLs, números e identificadores longos, mas uma mensagem de erro como `X-API-Key=abc123` ou `Authorization: Bearer ...` podia preservar valores curtos. O caso foi reproduzido por um teste que falhou antes da correção. O filtro agora oculta campos de credenciais, incluindo valores com aspas e autenticação Bearer/Basic, antes de truncar a linha. Leitura continua limitada ao trecho final do arquivo. Não foi encontrada evidência de exposição real nem de um endpoint público que entregue esse diagnóstico.

### Controles verificados

- Entrada HTML maliciosa simulada em dados da API é exibida como texto, sem criar imagem/evento executável no DOM.
- A suíte existente verifica autenticação, CSRF, suspensão/revogação, Superadmin sem acesso operacional e isolamento por empresa/unidade, incluindo RLS/FORCE RLS no PostgreSQL de teste.
- Webhooks inválidos, assinaturas falsas, sessões divergentes, replay e mudança de estado durante download possuem testes; URLs recebidas não são usadas para buscar fotos.
- Imagens têm limites, validação real do formato, normalização, remoção de metadados, criptografia e downloads sujeitos às permissões; anexos privados não são copiados automaticamente para a ordem.
- Revisão dos pontos de saída: provedores fixos e redirecionamentos recusados; sem `dangerouslySetInnerHTML`, armazenamento de credenciais no navegador, `eval`, pickle ou shell dinâmico encontrados nas áreas pesquisadas.
- Compose de produção mantém banco sem porta pública, papéis separados, API sem usuário root e sem credencial proprietária de migração. Isso foi conferido no código, sem inspecionar a infraestrutura viva nesta revisão.

### Dependências e segredos

- `npm audit --json`: zero alertas conhecidos entre as dependências do frontend, incluindo desenvolvimento, na consulta desta revisão.
- `uvx pip-audit --requirement backend/requirements.txt --no-deps --disable-pip --format json`: 29 dependências Python de produção consultadas, zero alertas conhecidos e nenhum pacote ignorado. Relatório bruto local em `data/pip-audit-ui-security.json`, fora do Git.
- Gitleaks: 20 commits do histórico consultados, sem segredo detectado. Os arquivos reais de ambiente não foram incluídos no relatório ou no Git.

Ausência de alertas de dependências e testes passando não equivale a certificação de segurança. Esta revisão não incluiu pentest de rede, exploração contra serviços de terceiros, inspeção da VPS, varredura das imagens do container, teste de carga externo ou auditoria completa de todos os fluxos de negócio.

## Limites de validação

Resultados finais:

- Backend/instalador: **175 passaram, 3 ignorados**, com SQLite e PostgreSQL. As três variantes ignoradas se aplicam apenas ao outro dialeto (RLS exclusivo do PostgreSQL e reconstrução exclusiva do SQLite).
- Interface: **52 passaram**, incluindo fluxos com API real local, acessibilidade, casos extremos, conteúdo HTML hostil, zoom e emulação de toque.
- Build TypeScript/Vite: concluído sem erro. Não houve adição de dependências ao aplicativo.

Reprodução: `python -m pytest backend/tests scripts/test_install_vps.py -q`, `npm run build` e `npx playwright test --workers=2` (os comandos npm na pasta `frontend`). O relatório não inclui segredos, dados de clientes ou logs reais do provedor.

As telas foram renderizadas e inspecionadas em Chromium, com cenários de 320 e 1440 px, ampliação de 200%, emulação de toque e tela baixa. Acessibilidade automatizada usa axe nos cenários de dados extremos. A validação em hardware real de iPhone/Android, teclado virtual, Safari, notch e fluidez da animação permanece pendente. O zoom não foi desativado.

O recebimento real de fotos pelo OpenWA continua sendo uma homologação separada; esta revisão não afirma corrigir os timeouts do navegador do provedor. Nenhuma instância da VPS foi reiniciada nesta tarefa.
