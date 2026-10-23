import {
  useEffect,
  useId,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import {
  Building2,
  Cable,
  Check,
  ChevronRight,
  CircleHelp,
  Eye,
  EyeOff,
  FileClock,
  FolderTree,
  KeyRound,
  LoaderCircle,
  LogOut,
  Mail,
  MessageCircle,
  RefreshCw,
  Save,
  Settings2,
  ShieldCheck,
  Unplug,
  Users,
} from "lucide-react";
import { api } from "./api";
import { Foundation, type FoundationPage } from "./Foundation";
import { AcceptInvitation } from "./Invitation";
import type { User } from "./types";

type Configuration = {
  version: number;
  openwa_base_url: string;
  openwa_key_configured: boolean;
  resend_key_configured: boolean;
  email_from: string;
  updated_at: string | null;
};
type Session = { id: string; name: string; status: string };
const errorMessage = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Não foi possível concluir a operação.";

function Brand({ light = false }: { light?: boolean }) {
  return (
    <div className={`brand ${light ? "light" : ""}`}>
      <span className="brand-mark">
        <Building2 size={25} aria-hidden="true" />
      </span>
      <span>
        <b>
          facilities<span>.</span>
        </b>
        <small>NEXUS · OS</small>
      </span>
    </div>
  );
}

function SecretField({
  label,
  value,
  onChange,
  configured,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  configured: boolean;
  disabled: boolean;
}) {
  const [visible, setVisible] = useState(false);
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <div className="secret-input">
        <KeyRound size={17} aria-hidden="true" />
        <input
          id={id}
          type={visible ? "text" : "password"}
          autoComplete="new-password"
          spellCheck={false}
          autoCapitalize="none"
          maxLength={4096}
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          placeholder={
            configured
              ? "Deixe vazio para manter a chave atual"
              : "Insira a API Key"
          }
        />
        <button
          type="button"
          className="icon-button"
          disabled={disabled}
          aria-label={visible ? `Ocultar ${label}` : `Mostrar ${label}`}
          onClick={() => setVisible(!visible)}
        >
          {visible ? <EyeOff size={18} /> : <Eye size={18} />}
        </button>
      </div>
      <small id={`${id}-hint`}>
        {configured
          ? "A chave salva está protegida e não pode ser consultada."
          : "A chave será criptografada ao salvar."}
      </small>
    </div>
  );
}

function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <div
      className={`notice ${error ? "error" : "success"}`}
      role={error ? "alert" : "status"}
    >
      {error ? (
        <CircleHelp size={18} aria-hidden="true" />
      ) : (
        <Check size={18} aria-hidden="true" />
      )}
      <span>{children}</span>
    </div>
  );
}

function Login({ onLogin }: { onLogin: (user: User) => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onLogin(await api<User>("/auth/login", "POST", { email, password }));
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
      setPassword("");
    }
  }
  return (
    <div className="login-layout">
      <aside className="login-story">
        <Brand light />
        <div>
          <span className="eyebrow">NEXUS FACILITIES OS</span>
          <h1>
            Conecte a operação.
            <br />
            <em>Cuide de cada detalhe.</em>
          </h1>
          <p>O ponto de encontro entre ambientes, equipes e soluções.</p>
        </div>
        <span className="login-footer">
          <ShieldCheck size={18} /> Ambientes, pessoas e operação
        </span>
      </aside>
      <main className="login-main">
        <form className="login-form" onSubmit={submit}>
          <span className="small-icon">
            <ShieldCheck size={24} />
          </span>
          <span className="eyebrow">ACESSO À PLATAFORMA</span>
          <h2>Acesse o Facilities OS</h2>
          <p className="muted">Entre com o acesso concedido à sua conta.</p>
          <div className="field">
            <label htmlFor="email">E-mail</label>
            <input
              id="email"
              type="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              maxLength={254}
              disabled={busy}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Senha</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              maxLength={1024}
              disabled={busy}
            />
          </div>
          {error && <Notice error>{error}</Notice>}
          <button className="button primary full" disabled={busy}>
            {busy ? (
              <LoaderCircle className="spin" size={18} />
            ) : (
              <ShieldCheck size={18} />
            )}
            {busy ? "Entrando…" : "Entrar"}
          </button>
          <p className="login-note">
            Primeiro acesso? Utilize o link enviado pelo administrador da sua
            empresa.
          </p>
        </form>
      </main>
    </div>
  );
}

function Integrations() {
  const [config, setConfig] = useState<Configuration | null>(null);
  const [loading, setLoading] = useState(true);
  const [openwa, setOpenwa] = useState("");
  const [resend, setResend] = useState("");
  const [sender, setSender] = useState("");
  const [removeOpenwa, setRemoveOpenwa] = useState(false);
  const [removeResend, setRemoveResend] = useState(false);
  const [recipient, setRecipient] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [openwaResult, setOpenwaResult] = useState<{
    message: string;
    sessions: Session[];
  } | null>(null);
  const [resendResult, setResendResult] = useState("");
  const dirty =
    !!config &&
    (!!openwa ||
      !!resend ||
      removeOpenwa ||
      removeResend ||
      sender !== config.email_from);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  async function load() {
    setLoading(true);
    setError("");
    setSaved(false);
    try {
      const result = await api<Configuration>("/nexus/integrations");
      setConfig(result);
      setSender(result.email_from);
      setOpenwa("");
      setResend("");
      setRemoveOpenwa(false);
      setRemoveResend(false);
      setOpenwaResult(null);
      setResendResult("");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  function changed() {
    setSaved(false);
    setError("");
    setOpenwaResult(null);
    setResendResult("");
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!config) return;
    setBusy("save");
    setError("");
    setSaved(false);
    try {
      const result = await api<Configuration>("/nexus/integrations", "PUT", {
        expected_version: config.version,
        openwa_api_key: openwa || undefined,
        resend_api_key: resend || undefined,
        email_from: sender || undefined,
        clear_openwa_key: removeOpenwa,
        clear_resend_key: removeResend,
      });
      setConfig(result);
      setSender(result.email_from);
      setOpenwa("");
      setResend("");
      setRemoveOpenwa(false);
      setRemoveResend(false);
      setSaved(true);
      setOpenwaResult(null);
      setResendResult("");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy("");
    }
  }
  async function testOpenwa() {
    setBusy("openwa");
    setError("");
    setOpenwaResult(null);
    try {
      setOpenwaResult(await api("/nexus/integrations/test/openwa", "POST"));
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy("");
    }
  }
  async function testResend() {
    setBusy("resend");
    setError("");
    setResendResult("");
    try {
      setResendResult(
        (
          await api<{ message: string }>(
            "/nexus/integrations/test/resend",
            "POST",
            { recipient },
          )
        ).message,
      );
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy("");
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ADMINISTRAÇÃO DA PLATAFORMA</span>
          <h1>Integrações</h1>
          <p className="muted">
            Configure os canais que conectam pessoas à operação.
          </p>
        </div>
        <span className="access-badge">
          <ShieldCheck size={16} /> Superadmin completo
        </span>
      </div>
      <div className="privacy-banner">
        <span className="small-icon">
          <ShieldCheck size={22} />
        </span>
        <div>
          <strong>Credenciais protegidas, acesso controlado</strong>
          <p>
            As API Keys são usadas pelo servidor e não são exibidas após o
            salvamento. As alterações ficam registradas no histórico de
            auditoria.
          </p>
        </div>
      </div>
      {error && <Notice error>{error}</Notice>}
      {loading ? (
        <p className="loading" role="status">
          <LoaderCircle className="spin" size={20} /> Carregando configurações…
        </p>
      ) : !config ? (
        <button className="button secondary" onClick={() => void load()}>
          Tentar novamente
        </button>
      ) : (
        <>
          <form onSubmit={save}>
            <fieldset disabled={!!busy} className="integration-grid">
              <section className="card" aria-labelledby="openwa-title">
                <header className="card-header">
                  <span className="provider-icon whatsapp">
                    <MessageCircle size={25} />
                  </span>
                  <div>
                    <span className="provider-category">WHATSAPP</span>
                    <h2 id="openwa-title">OpenWA</h2>
                  </div>
                  <span
                    className={`status-badge ${config.openwa_key_configured ? "configured" : ""}`}
                  >
                    <span />
                    {config.openwa_key_configured
                      ? "Chave cadastrada"
                      : "Não configurado"}
                  </span>
                </header>
                <div className="card-body">
                  <p className="card-description">
                    Conecte o gateway de mensagens que será usado no atendimento
                    dos solicitantes.
                  </p>
                  <div className="endpoint">
                    <span>ENDEREÇO DO GATEWAY</span>
                    <code>{config.openwa_base_url}</code>
                  </div>
                  <SecretField
                    label="API Key do OpenWA"
                    value={openwa}
                    configured={config.openwa_key_configured}
                    disabled={!!busy || removeOpenwa}
                    onChange={(value) => {
                      setOpenwa(value);
                      changed();
                    }}
                  />
                  {config.openwa_key_configured && (
                    <label className="checkbox danger">
                      <input
                        type="checkbox"
                        checked={removeOpenwa}
                        onChange={(e) => {
                          setRemoveOpenwa(e.target.checked);
                          setOpenwa("");
                          changed();
                        }}
                      />{" "}
                      Remover a chave OpenWA ao salvar
                    </label>
                  )}
                  <div className="helper">
                    <CircleHelp size={17} />
                    <p>
                      A API usa o cabeçalho <code>X-API-Key</code>. Usuário e
                      senha do painel OpenWA não são necessários aqui.
                    </p>
                  </div>
                  <div className="test-section">
                    <h3>Verificar conexão</h3>
                    <p>
                      Consulta as sessões acessíveis com a chave salva. Não
                      envia mensagens.
                    </p>
                    <button
                      type="button"
                      className="button secondary"
                      disabled={
                        !!busy || dirty || !config.openwa_key_configured
                      }
                      onClick={() => void testOpenwa()}
                    >
                      {busy === "openwa" ? (
                        <LoaderCircle className="spin" size={17} />
                      ) : (
                        <Cable size={17} />
                      )}
                      {busy === "openwa"
                        ? "Consultando…"
                        : "Consultar sessões OpenWA"}
                    </button>
                  </div>
                  {openwaResult && (
                    <div className="test-result" role="status">
                      <p>{openwaResult.message}</p>
                      {openwaResult.sessions.length === 0 ? (
                        <p>Nenhuma sessão disponível para esta chave.</p>
                      ) : (
                        <ul>
                          {openwaResult.sessions.map((session, index) => (
                            <li key={session.id || index}>
                              <strong>{session.name}</strong>
                              <span>{session.status}</span>
                              <small>{session.id}</small>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
                <footer className="card-footer">
                  <Unplug size={16} />
                  <span>
                    Cadastrar a chave não ativa o recebimento de ocorrências.
                    Sessões por empresa e webhooks serão configurados na etapa
                    de atendimento.
                  </span>
                </footer>
              </section>
              <section className="card" aria-labelledby="resend-title">
                <header className="card-header">
                  <span className="provider-icon email">
                    <Mail size={25} />
                  </span>
                  <div>
                    <span className="provider-category">
                      E-MAIL TRANSACIONAL
                    </span>
                    <h2 id="resend-title">Resend</h2>
                  </div>
                  <span
                    className={`status-badge ${config.resend_key_configured ? "configured" : ""}`}
                  >
                    <span />
                    {config.resend_key_configured
                      ? "Chave cadastrada"
                      : "Não configurado"}
                  </span>
                </header>
                <div className="card-body">
                  <p className="card-description">
                    Prepare o envio de convites, recuperação de acesso e
                    atualizações operacionais por e-mail.
                  </p>
                  <SecretField
                    label="API Key do Resend"
                    value={resend}
                    configured={config.resend_key_configured}
                    disabled={!!busy || removeResend}
                    onChange={(value) => {
                      setResend(value);
                      changed();
                    }}
                  />
                  <div className="field">
                    <label htmlFor="sender">E-mail remetente</label>
                    <input
                      id="sender"
                      type="email"
                      maxLength={254}
                      placeholder="notificacoes@suaempresa.com.br"
                      value={sender}
                      required={
                        !!resend ||
                        (config.resend_key_configured && !removeResend)
                      }
                      onChange={(e) => {
                        setSender(e.target.value);
                        changed();
                      }}
                    />
                    <small>
                      Utilize um endereço de domínio verificado na sua conta
                      Resend.
                    </small>
                  </div>
                  {config.resend_key_configured && (
                    <label className="checkbox danger">
                      <input
                        type="checkbox"
                        checked={removeResend}
                        onChange={(e) => {
                          setRemoveResend(e.target.checked);
                          setResend("");
                          changed();
                        }}
                      />{" "}
                      Remover a chave Resend ao salvar
                    </label>
                  )}
                  <div className="helper">
                    <ShieldCheck size={17} />
                    <p>
                      Prefira uma chave com permissão de envio restrita ao
                      domínio necessário.
                    </p>
                  </div>
                  <div className="test-section">
                    <h3>Enviar e-mail de teste</h3>
                    <p>
                      Envia uma mensagem real usando as configurações salvas.
                    </p>
                    <div className="field">
                      <label htmlFor="recipient">Destinatário do teste</label>
                      <input
                        id="recipient"
                        type="email"
                        maxLength={254}
                        value={recipient}
                        placeholder="seuemail@empresa.com.br"
                        onChange={(e) => {
                          setRecipient(e.target.value);
                          setResendResult("");
                        }}
                      />
                    </div>
                    <button
                      type="button"
                      className="button secondary"
                      disabled={
                        !!busy ||
                        dirty ||
                        !config.resend_key_configured ||
                        !recipient ||
                        !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(recipient)
                      }
                      onClick={() => void testResend()}
                    >
                      {busy === "resend" ? (
                        <LoaderCircle className="spin" size={17} />
                      ) : (
                        <Mail size={17} />
                      )}
                      {busy === "resend"
                        ? "Solicitando envio…"
                        : "Enviar e-mail de teste"}
                    </button>
                  </div>
                  {resendResult && <Notice>{resendResult}</Notice>}
                </div>
                <footer className="card-footer">
                  <CircleHelp size={16} />
                  <span>
                    O aceite do envio pelo Resend não confirma a entrega.
                    Confira também a pasta de spam do destinatário.
                  </span>
                </footer>
              </section>
            </fieldset>
            <div className="save-bar">
              <div>
                {saved ? (
                  <span className="saved" role="status">
                    <Check size={18} /> Configurações salvas com sucesso.
                  </span>
                ) : (
                  <span className="muted">
                    {dirty
                      ? "Você tem alterações não salvas. Salve antes de testar."
                      : "Nenhuma alteração pendente."}
                  </span>
                )}
                <small>
                  {config.updated_at
                    ? `Última alteração: ${new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" }).format(new Date(config.updated_at))}`
                    : "As integrações ainda não foram configuradas."}
                </small>
              </div>
              <div className="save-actions">
                <button
                  type="button"
                  className="button secondary"
                  disabled={!!busy}
                  onClick={() => {
                    if (
                      !dirty ||
                      window.confirm(
                        "Descartar as alterações não salvas e recarregar?",
                      )
                    )
                      void load();
                  }}
                >
                  <RefreshCw size={16} /> Recarregar
                </button>
                <button className="button primary" disabled={!!busy || !dirty}>
                  {busy === "save" ? (
                    <LoaderCircle className="spin" size={17} />
                  ) : (
                    <Save size={17} />
                  )}
                  {busy === "save" ? "Salvando…" : "Salvar configurações"}
                </button>
              </div>
            </div>
          </form>
          <div className="scope-note">
            <ShieldCheck size={17} />
            <p>
              Configuração global da plataforma. A vinculação de cada sessão
              WhatsApp à empresa será feita separadamente, preservando o
              isolamento dos atendimentos.
            </p>
          </div>
        </>
      )}
    </>
  );
}

export function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [logoutError, setLogoutError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  useEffect(() => {
    if (window.location.pathname === "/convite") {
      setLoading(false);
      return;
    }
    void api<User>("/auth/me")
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
    const expire = () => setUser(null);
    window.addEventListener("session-expired", expire);
    return () => window.removeEventListener("session-expired", expire);
  }, []);
  async function logout() {
    setLoggingOut(true);
    setLogoutError("");
    try {
      await api("/auth/logout", "POST");
      setUser(null);
    } catch (error) {
      setLogoutError(errorMessage(error));
    } finally {
      setLoggingOut(false);
    }
  }
  if (window.location.pathname === "/convite") return <AcceptInvitation />;
  if (loading)
    return (
      <main className="initial-loading" role="status">
        Carregando Facilities OS…
      </main>
    );
  if (!user) return <Login onLogin={setUser} />;
  const isNexus = user.role === "superadmin";
  const canManage = isNexus || user.roles?.includes("company_admin");
  const canAudit =
    isNexus ||
    user.roles?.some((role) =>
      ["company_admin", "auditor", "manager"].includes(role),
    );
  const path = window.location.pathname;
  const page: FoundationPage | "integrations" = path.endsWith("/empresas")
    ? "companies"
    : path.endsWith("/usuarios")
      ? "users"
      : path.endsWith("/locais")
        ? "locations"
        : path.endsWith("/auditoria")
          ? "audit"
          : isNexus
            ? "integrations"
            : "locations";
  const label = {
    companies: "Empresas",
    users: "Usuários e permissões",
    locations: "Estrutura física",
    audit: "Auditoria",
    integrations: "Integrações",
  }[page];
  const base = isNexus ? "/nexus" : "/app";
  const allowed =
    (page !== "companies" || isNexus) &&
    (page !== "users" || canManage) &&
    (page !== "audit" || canAudit) &&
    (page !== "integrations" || isNexus);
  const navItems = [
    ...(isNexus
      ? [
          {
            key: "companies",
            title: "Empresas",
            href: "/nexus/empresas",
            icon: Building2,
          },
        ]
      : []),
    {
      key: "locations",
      title: "Estrutura física",
      href: base + "/locais",
      icon: FolderTree,
    },
    ...(canManage
      ? [
          {
            key: "users",
            title: "Usuários e permissões",
            href: base + "/usuarios",
            icon: Users,
          },
        ]
      : []),
    ...(canAudit
      ? [
          {
            key: "audit",
            title: "Auditoria",
            href: base + "/auditoria",
            icon: FileClock,
          },
        ]
      : []),
    ...(isNexus
      ? [
          {
            key: "integrations",
            title: "Integrações",
            href: "/nexus/configuracoes/integracoes",
            icon: Settings2,
          },
        ]
      : []),
  ];
  return (
    <div className="app-layout">
      <a href="#main" className="skip-link">
        Pular para o conteúdo
      </a>
      <aside className="sidebar">
        <Brand light />
        <div className="workspace">
          <span className="workspace-symbol">
            <Building2 size={20} />
          </span>
          <div>
            <strong>{isNexus ? "Administração Nexus" : "Minha empresa"}</strong>
            <small>{isNexus ? "Gestão da plataforma" : user.name}</small>
          </div>
        </div>
        <span className="nav-label">
          {isNexus ? "ADMINISTRAÇÃO" : "OPERAÇÃO"}
        </span>
        <nav aria-label="Administração">
          {navItems.map((item) => (
            <a
              key={item.key}
              href={item.href}
              className={`nav-item ${page === item.key ? "active" : ""}`}
              aria-current={page === item.key ? "page" : undefined}
            >
              <item.icon size={19} />
              {item.title}
              {page === item.key && (
                <ChevronRight className="nav-chevron" size={15} />
              )}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="sidebar-security">
            <ShieldCheck size={19} />
            <span>
              Acesso autorizado
              <br />
              <strong>
                {isNexus ? "Superadmin completo" : "Escopo da empresa"}
              </strong>
            </span>
          </div>
          <small>
            NEXUS DATA ANALYTICS
            <br />
            Facilities OS · fundação
          </small>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="breadcrumb">
            <span>{isNexus ? "Superadmin" : "Minha empresa"}</span>
            <ChevronRight size={14} />
            <strong>{label}</strong>
          </div>
          <div className="user-menu">
            <span className="avatar">{user.name?.slice(0, 1) ?? "N"}</span>
            <span className="user-email">{user.email}</span>
            <button
              className="icon-button"
              aria-label="Sair da conta"
              disabled={loggingOut}
              onClick={() => void logout()}
            >
              <LogOut size={18} />
            </button>
          </div>
        </header>
        <main id="main" className="content" tabIndex={-1}>
          {logoutError && <Notice error>{logoutError}</Notice>}
          {!allowed ? (
            <Notice error>Seu perfil não permite acessar esta página.</Notice>
          ) : page === "integrations" ? (
            <Integrations />
          ) : (
            <Foundation page={page} user={user} />
          )}
        </main>
        <footer className="app-footer">
          <span>© {new Date().getFullYear()} Nexus Data Analytics</span>
          <span>
            <ShieldCheck size={14} /> Facilities OS · Fundação
          </span>
        </footer>
      </div>
    </div>
  );
}
