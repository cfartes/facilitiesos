# Nexus Facilities OS

Fundação do Nexus Facilities OS, seguindo a identidade visual do Nexus RotaFY. Inclui empresas, usuários por convite, permissões por unidade, estrutura física, auditoria e configuração de OpenWA/Resend.

## Recursos disponíveis

- Superadmin: cadastrar/editar/suspender empresas, organizar locais, convidar usuários, configurar permissões, consultar auditoria e administrar integrações.
- Empresa: acesso individual conforme perfil e unidades concedidas. Administradores gerenciam a própria equipe; supervisores organizam locais nas unidades autorizadas; os demais perfis consultam a estrutura dentro do escopo concedido. Auditoria disponível a administradores, gestores e auditores no seu escopo.
- Estrutura: unidade → prédio → andar → ambiente, com criticidade e fuso horário herdado da unidade. Não permite referências entre empresas nem inativação de um local com filhos ativos. Alterar hierarquia e exclusão definitiva não fazem parte desta etapa.
- Convite: link individual válido por 48 horas, de uso único, com token persistido somente por hash. O usuário define sua própria senha (mínimo 12 caracteres). O link é entregue ao administrador para compartilhamento; **não há envio automático de convites por e-mail nesta etapa**. Reemitir um convite invalida o anterior.
- Alterações de acesso encerram as sessões do usuário. Suspensão da empresa bloqueia login e acesso aos seus registros, preservando o histórico. O último administrador ativo com convite aceito não pode ser removido ou desativado.
- Perfis acumuláveis: solicitante, técnico, supervisor, gestor, aprovador, auditor e administrador da empresa. Os fluxos operacionais de cada perfil serão habilitados nas próximas entregas. Fornecedores aguardam cadastro e vínculo organizacional próprios.

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

Prepare a primeira empresa, sua estrutura e um convite para seu administrador. O administrador pode então convidar a equipe e restringir os acessos às unidades necessárias. Cada e-mail corresponde a uma conta e uma empresa nesta etapa; não há alternância entre empresas na mesma conta de cliente.

### Banco e migrações

`python -m backend.dev_database` preserva o volume e as credenciais existentes. As migrações `0001` e `0002` são incrementais e podem ser reaplicadas, sem excluir dados. Para um PostgreSQL externo, configure `FACILITIES_MIGRATION_DATABASE_URL`, `FACILITIES_DATABASE_URL` e `FACILITIES_PLATFORM_DATABASE_URL`; provisione os papéis seguindo `infra/init-db.sh` e execute `python -m backend.migrate` com a credencial proprietária.

As tabelas de configuração, autenticação, convites e limites são restritas ao papel da plataforma. Empresas, usuários, locais e auditoria têm RLS/FORCE RLS, com escopo de empresa por transação e restrições adicionais de unidade para locais e auditoria. Credenciais de conta ficam em tabela separada da listagem de usuários. A tabela `schema_versions` contém somente os identificadores de migração, sem dados privados.

Sem URLs PostgreSQL, o modo development permite SQLite para testes locais, com validação de escopo na API. SQLite não implementa RLS e é recusado fora desse modo. Alternar do SQLite para PostgreSQL **não importa automaticamente** registros do arquivo anterior; preserve o arquivo e planeje a importação se ele contiver dados. O provisionamento não copia dados ou segredos do RotaFY.

## Configurar os provedores

- OpenWA: insira a API Key, salve e use **Consultar sessões OpenWA**. A URL fica fixa no servidor conforme o guia fornecido; autenticação por `X-API-Key`. A consulta não envia mensagens. A sessão deve ser pareada no painel do provedor. A existência de chave cadastrada não comprova disponibilidade ou conexão.
- Resend: insira a API Key e um e-mail remetente de domínio verificado, salve e informe um destinatário para **Enviar e-mail de teste**. Esse botão envia uma mensagem real. O aceite da API não comprova entrega. Prefira chave limitada ao envio no domínio necessário. Referência: https://resend.com/docs/api-reference/emails/send-email.
- Campo de chave vazio preserva o valor anterior. A opção de remoção apaga a credencial ao salvar. A aplicação retorna apenas indicadores de configuração, nunca as chaves salvas.
- Os testes utilizam somente configurações salvas. Enquanto houver alterações, os botões de teste ficam desabilitados.

## Proteções e limites desta entrega

Credenciais criptografadas com Fernet no servidor, sessão aleatória persistida por hash, cookie HttpOnly/SameSite, cookie CSRF separado, validação de origem e CSRF, autorização por perfil/empresa/unidade, limitação persistente de tentativas, bloqueio de redirecionamentos dos provedores, mensagens de erro sem respostas brutas ou segredos, auditoria de ações e controle de concorrência por versão. Cookies usam Secure quando a origem configurada é HTTPS.

O PostgreSQL local foi preparado para desenvolvimento e testes; isso não certifica a implantação em produção. Ambientes externos exigem PostgreSQL com RLS/FORCE RLS, papéis de runtime sem privilégios administrativos e origem HTTPS. TLS/proxy, backups, restauração, acesso de suporte, retenção e revisão dos textos legais ainda precisam ser preparados e validados antes de uso real. A credencial proprietária de migração não deve ficar no ambiente da API em produção.

Ainda não implementado: ativos, ocorrências e ordens, SLA/calendários, fornecedores, contratos, aprovações financeiras, vínculo de sessões por empresa, recebimento de webhooks, filas operacionais, envio automático de convites, recuperação de senha, gestão de equipe Nexus, MFA e páginas legais. O envio Resend desta entrega é apenas o teste explícito. O guia OpenWA recebido documenta envio e consulta; não define o contrato de eventos recebidos. Não foram copiadas senhas ou chaves do documento original. O plano de continuidade está em `DESENVOLVIMENTO.md`.

## Verificação

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
cd frontend
npm run build
npm run test:e2e
```

Os testes de API verificam SQLite e, quando `.env.database` está disponível, PostgreSQL real em bancos aleatórios temporários `facilities_test_*`, criados e removidos pelo próprio teste. Não apagam dados do banco `facilities`. Incluem isolamento de empresas/unidades, RLS sem escopo, conexões reutilizadas, convites, suspensão, CSRF e proteção das credenciais. Sem PostgreSQL configurado, os respectivos cenários são marcados como ignorados.

O Playwright inicia uma API temporária em `127.0.0.1:8010` e o frontend em `127.0.0.1:5180`; essas portas devem estar livres. A conta `e2e-admin@example.com` existe **somente no processo de testes** e usa banco temporário. Um cenário percorre o fluxo completo com a API real; os demais simulam respostas para verificar erros, navegação, teclado e acessibilidade em desktop/mobile. Nenhuma mensagem real é enviada. Para instalar o navegador: `npx playwright install chromium`.

O build mantém CSP restrita à própria origem. Somente o servidor de desenvolvimento remove a meta CSP para permitir os scripts e estilos do HMR.
