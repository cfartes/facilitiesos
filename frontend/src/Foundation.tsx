import { useEffect, useState, type FormEvent } from "react";
import {
  Building2,
  Check,
  Copy,
  FolderTree,
  LoaderCircle,
  Pencil,
  Plus,
  Search,
  ShieldCheck,
  UserPlus,
  Users,
} from "lucide-react";
import { api } from "./api";
import { CompanyForm } from "./CompanyForm";
import { InvitationEmailChoice } from "./InvitationEmailChoice";
import { actionNames } from "./operationTypes";
import { errorMessage, Loading, Modal, Notice } from "./ui";
import type { Company, Invitation, Location, Member, User } from "./types";

export type FoundationPage = "companies" | "locations" | "users" | "audit";
const titles = {
  companies: "Empresas",
  locations: "Estrutura física",
  users: "Usuários e permissões",
  audit: "Histórico de auditoria",
};
const emailStates: Record<string, string> = {
  queued: "Na fila",
  sending: "Em envio",
  retrying: "Nova tentativa agendada",
  accepted: "Aceito pelo Resend — entrega não confirmada",
  failed: "Falha no envio",
  cancelled: "Envio cancelado",
};
const subtitles = {
  companies: "Organize as empresas atendidas pela plataforma.",
  locations: "Cada atendimento começa por saber exatamente onde agir.",
  users: "Convide pessoas e defina o alcance de cada acesso.",
  audit: "Acompanhe os autores e as ações registradas na empresa.",
};
const kinds = {
  unit: "Unidade",
  building: "Prédio",
  floor: "Andar",
  environment: "Ambiente",
};
const criticalities: Record<string, string> = {
  low: "Baixa",
  medium: "Média",
  high: "Alta",
  critical: "Crítica",
};
const roles: Record<string, string> = {
  requester: "Solicitante",
  technician: "Técnico",
  supervisor: "Supervisor",
  manager: "Gestor",
  approver: "Aprovador",
  auditor: "Auditor",
  company_admin: "Administrador da empresa",
};
const actions: Record<string, string> = {
  ...actionNames,
  "category.created": "Categoria cadastrada",
  "category.updated": "Categoria atualizada",
  "asset.created": "Ativo cadastrado",
  "asset.updated": "Ativo atualizado",
  "occurrence.created": "Ocorrência registrada",
  "whatsapp.intake_enabled": "Solicitações pelo WhatsApp habilitadas",
  "whatsapp.intake_disabled": "Solicitações pelo WhatsApp desativadas",
  "order.message_added": "Mensagem registrada na ordem",
  "company.created": "Empresa cadastrada",
  "user.initial_admin_created": "Administrador inicial cadastrado",
  "company.updated": "Empresa atualizada",
  "company.suspended": "Empresa suspensa",
  "location.created": "Local cadastrado",
  "location.updated": "Local atualizado",
  "user.invited": "Usuário convidado",
  "user.access_updated": "Permissões do usuário alteradas",
  "user.invitation_reissued": "Convite reemitido",
  "user.invitation_accepted": "Convite aceito",
  "invitation_email.queued": "Convite enfileirado para e-mail",
  "invitation_email.accepted": "Convite aceito pelo provedor de e-mail",
  "invitation_email.retrying": "Nova tentativa de e-mail agendada",
  "invitation_email.failed": "Falha no envio do convite",
  "invitation_email.cancelled": "Envio de convite cancelado",
};
const formatDate = (value: string) =>
  new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "America/Sao_Paulo",
  }).format(new Date(value));
type Audit = {
  id: number;
  actor: string;
  action: string;
  created_at: string;
  entity_id: string | null;
};

function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty-state">
      <FolderTree size={32} aria-hidden="true" />
      <h2>{title}</h2>
      <p>{text}</p>
    </div>
  );
}

function LocationForm({
  companyId,
  location,
  locations,
  onClose,
  onSaved,
  canCreateUnit,
}: {
  companyId: string;
  location: Location | null;
  locations: Location[];
  onClose: () => void;
  onSaved: () => void;
  canCreateUnit: boolean;
}) {
  const [name, setName] = useState(location?.name ?? "");
  const [kind, setKind] = useState<Location["kind"]>(
    location?.kind ?? (canCreateUnit ? "unit" : "building"),
  );
  const [parent, setParent] = useState(location?.parent_id ?? "");
  const [criticality, setCriticality] = useState(
    location?.criticality ?? "medium",
  );
  const [timezone, setTimezone] = useState("America/Sao_Paulo");
  const [active, setActive] = useState(location?.is_active ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const parentKind = (
    { building: "unit", floor: "building", environment: "floor" } as Record<
      string,
      string
    >
  )[kind];
  const options = locations.filter(
    (item) => item.kind === parentKind && item.is_active,
  );
  function locationPath(item: Location): string {
    const above = locations.find((parent) => parent.id === item.parent_id);
    return above ? `${locationPath(above)} / ${item.name}` : item.name;
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(
        `/foundation/companies/${companyId}/locations${location ? "/" + location.id : ""}`,
        location ? "PUT" : "POST",
        location
          ? {
              name,
              criticality,
              is_active: active,
              expected_version: location.version,
            }
          : {
              name,
              kind,
              criticality,
              timezone,
              parent_id: kind === "unit" ? null : parent,
            },
      );
      onSaved();
      onClose();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={location ? "Editar local" : "Novo local"}
      onClose={onClose}
      busy={busy}
    >
      <form onSubmit={submit}>
        <fieldset className="plain-fieldset" disabled={busy}>
          <div className="field">
            <label htmlFor="location-kind">Tipo de local</label>
            <select
              id="location-kind"
              value={kind}
              disabled={!!location}
              onChange={(e) => {
                setKind(e.target.value as Location["kind"]);
                setParent("");
              }}
            >
              {Object.entries(kinds)
                .filter(([key]) => key !== "unit" || canCreateUnit || location)
                .map(([key, label]) => (
                  <option value={key} key={key}>
                    {label}
                  </option>
                ))}
            </select>
          </div>
          {kind !== "unit" && !location && (
            <div className="field">
              <label htmlFor="location-parent">Local superior</label>
              <select
                id="location-parent"
                value={parent}
                onChange={(e) => setParent(e.target.value)}
                required
              >
                <option value="">
                  Selecione{" "}
                  {kinds[parentKind as Location["kind"]]?.toLowerCase()}
                </option>
                {options.map((item) => (
                  <option key={item.id} value={item.id}>
                    {locationPath(item)}
                  </option>
                ))}
              </select>
              {!options.length && (
                <small>
                  Cadastre um local superior ativo antes de continuar.
                </small>
              )}
            </div>
          )}
          <div className="field">
            <label htmlFor="location-name">Nome do local</label>
            <input
              id="location-name"
              required
              minLength={2}
              maxLength={160}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="location-criticality">
              Criticidade operacional
            </label>
            <select
              id="location-criticality"
              value={criticality}
              onChange={(e) => setCriticality(e.target.value)}
            >
              {Object.entries(criticalities).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          {kind === "unit" && !location && (
            <div className="field">
              <label htmlFor="location-timezone">Fuso horário da unidade</label>
              <select
                id="location-timezone"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
              >
                {[
                  "America/Sao_Paulo",
                  "America/Manaus",
                  "America/Cuiaba",
                  "America/Rio_Branco",
                  "America/Noronha",
                ].map((value) => (
                  <option key={value}>{value}</option>
                ))}
              </select>
              <small>
                Prédios, andares e ambientes herdam o fuso da unidade.
              </small>
            </div>
          )}
          {location && (
            <label className="checkbox">
              <input
                type="checkbox"
                checked={active}
                onChange={(e) => setActive(e.target.checked)}
              />{" "}
              Local ativo
            </label>
          )}
          {error && <Notice error>{error}</Notice>}
          <div className="modal-actions">
            <button
              type="button"
              className="button secondary"
              onClick={onClose}
            >
              Cancelar
            </button>
            <button
              className="button primary"
              disabled={
                busy || (!location && kind !== "unit" && !options.length)
              }
            >
              {busy && <LoaderCircle className="spin" size={16} />}Salvar local
            </button>
          </div>
        </fieldset>
      </form>
    </Modal>
  );
}

function UserForm({
  companyId,
  member,
  units,
  onClose,
  onSaved,
  onInvitation,
}: {
  companyId: string;
  member: Member | null;
  units: Location[];
  onClose: () => void;
  onSaved: () => void;
  onInvitation: (invitation: Invitation) => void;
}) {
  const [name, setName] = useState(member?.name ?? "");
  const [email, setEmail] = useState(member?.email ?? "");
  const [sendEmail, setSendEmail] = useState(false);
  const [selectedRoles, setSelectedRoles] = useState(
    member?.roles ?? ["requester"],
  );
  const [allUnits, setAllUnits] = useState(member?.all_units ?? false);
  const [unitIds, setUnitIds] = useState(member?.unit_ids ?? []);
  const [active, setActive] = useState(member?.is_active ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const admin = selectedRoles.includes("company_admin");
  function changeRole(role: string, checked: boolean) {
    setSelectedRoles((current) =>
      checked ? [...current, role] : current.filter((item) => item !== role),
    );
    if (role === "company_admin" && checked) {
      setAllUnits(true);
      setUnitIds([]);
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const payload = {
        name,
        roles: selectedRoles,
        all_units: allUnits,
        unit_ids: allUnits ? [] : unitIds,
      };
      const result = await api<{ invitation: Invitation }>(
        `/foundation/companies/${companyId}/users${member ? "/" + member.id : ""}`,
        member ? "PUT" : "POST",
        member
          ? { ...payload, is_active: active, expected_version: member.version }
          : { ...payload, email, send_email: sendEmail },
      );
      onSaved();
      onClose();
      if (!member) onInvitation(result.invitation);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={member ? "Editar acesso do usuário" : "Convidar usuário"}
      onClose={onClose}
      busy={busy}
    >
      <form onSubmit={submit}>
        <fieldset className="plain-fieldset" disabled={busy}>
          <div className="field">
            <label htmlFor="member-name">Nome completo</label>
            <input
              id="member-name"
              minLength={2}
              maxLength={160}
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="member-email">E-mail corporativo</label>
            <input
              id="member-email"
              type="email"
              required
              maxLength={254}
              disabled={!!member}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <fieldset className="choice-group">
            <legend>Perfis de acesso</legend>
            <div className="roles-grid">
              {Object.entries(roles).map(([value, label]) => (
                <label className="checkbox" key={value}>
                  <input
                    type="checkbox"
                    checked={selectedRoles.includes(value)}
                    onChange={(e) => changeRole(value, e.target.checked)}
                  />
                  {label}
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className="choice-group">
            <legend>Unidades autorizadas</legend>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={allUnits}
                disabled={admin}
                onChange={(e) => {
                  setAllUnits(e.target.checked);
                  setUnitIds([]);
                }}
              />
              Todas as unidades atuais e futuras
            </label>
            {admin && (
              <p className="form-help">
                O administrador gerencia toda a empresa.
              </p>
            )}
            {!allUnits && (
              <>
                {units.length === 0 && (
                  <p className="form-help">
                    Cadastre uma unidade ou selecione o perfil Administrador da
                    empresa para o primeiro acesso.
                  </p>
                )}
                {units.map((unit) => (
                  <label className="checkbox" key={unit.id}>
                    <input
                      type="checkbox"
                      checked={unitIds.includes(unit.id)}
                      onChange={(e) =>
                        setUnitIds((current) =>
                          e.target.checked
                            ? [...current, unit.id]
                            : current.filter((id) => id !== unit.id),
                        )
                      }
                    />
                    {unit.name}
                    {!unit.is_active && " (inativa)"}
                  </label>
                ))}
              </>
            )}
          </fieldset>
          {member && (
            <>
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={active}
                  onChange={(e) => setActive(e.target.checked)}
                />{" "}
                Usuário ativo
              </label>
              <p className="form-help">
                Alterações de acesso encerram as sessões deste usuário.
              </p>
            </>
          )}
          {!member && (
            <InvitationEmailChoice
              companyId={companyId}
              value={sendEmail}
              onChange={setSendEmail}
            />
          )}
          {error && <Notice error>{error}</Notice>}
          <div className="modal-actions">
            <button
              type="button"
              className="button secondary"
              onClick={onClose}
            >
              Cancelar
            </button>
            <button
              className="button primary"
              disabled={
                busy || !selectedRoles.length || (!allUnits && !unitIds.length)
              }
            >
              {busy && <LoaderCircle className="spin" size={16} />}
              {member ? "Salvar acesso" : "Gerar convite"}
            </button>
          </div>
        </fieldset>
      </form>
    </Modal>
  );
}

function InvitationDialog({
  invitation,
  onClose,
}: {
  invitation: Invitation;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  return (
    <Modal title="Convite de primeiro acesso" onClose={onClose}>
      {invitation.email_queued && (
        <Notice>
          Convite registrado na fila de e-mail. Acompanhe o resultado na lista
          de usuários; o envio não confirma entrega.
        </Notice>
      )}
      <p className="form-help">
        Compartilhe este link somente com a pessoa convidada, por um canal
        autorizado. Válido por {invitation.expires_in_hours} horas e para um
        único uso. O link não será exibido novamente após fechar.
      </p>
      <div className="field">
        <label htmlFor="invitation-link">Link individual do convite</label>
        <textarea
          id="invitation-link"
          readOnly
          value={invitation.url}
          rows={4}
          onFocus={(e) => e.target.select()}
        />
      </div>
      {error && <Notice error>{error}</Notice>}
      <div className="modal-actions">
        <button className="button secondary" onClick={onClose}>
          Fechar
        </button>
        <button
          className="button primary"
          onClick={() => {
            void navigator.clipboard
              .writeText(invitation.url)
              .then(() => setCopied(true))
              .catch(() => setError("Selecione e copie o link manualmente."));
          }}
        >
          {copied ? <Check size={17} /> : <Copy size={17} />}
          {copied ? "Copiado" : "Copiar link"}
        </button>
      </div>
    </Modal>
  );
}

function RenewInvitation({
  companyId,
  member,
  onClose,
  onSaved,
}: {
  companyId: string;
  member: Member;
  onClose: () => void;
  onSaved: (invitation: Invitation) => void;
}) {
  const [sendEmail, setSendEmail] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      onSaved(
        await api<Invitation>(
          `/foundation/companies/${companyId}/users/${member.id}/invitation`,
          "POST",
          { send_email: sendEmail },
        ),
      );
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Gerar novo convite" busy={busy} onClose={onClose}>
      <p className="form-help">
        O link anterior de {member.name} será invalidado, e envios pendentes
        desse convite serão cancelados. Uma mensagem já enviada ou em andamento
        pode chegar com o link antigo, que não dará acesso.
      </p>
      <form onSubmit={submit}>
        <fieldset className="plain-fieldset" disabled={busy}>
          <InvitationEmailChoice
            companyId={companyId}
            value={sendEmail}
            onChange={setSendEmail}
          />
          {error && <Notice error>{error}</Notice>}
          <div className="modal-actions">
            <button
              type="button"
              className="button secondary"
              onClick={onClose}
            >
              Cancelar
            </button>
            <button className="button primary" disabled={busy}>
              Gerar novo convite
            </button>
          </div>
        </fieldset>
      </form>
    </Modal>
  );
}

export function Foundation({
  page,
  user,
}: {
  page: FoundationPage;
  user: User;
}) {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [companyId, setCompanyId] = useState("");
  const [locations, setLocations] = useState<Location[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [search, setSearch] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [companyModal, setCompanyModal] = useState<Company | "new" | null>(
    null,
  );
  const [locationModal, setLocationModal] = useState<Location | "new" | null>(
    null,
  );
  const [userModal, setUserModal] = useState<Member | "new" | null>(null);
  const [invitation, setInvitation] = useState<Invitation | null>(null);
  const [renewing, setRenewing] = useState<Member | null>(null);
  const isNexus = user.role === "superadmin";
  const canManageUsers = isNexus || user.roles?.includes("company_admin");
  const canManageLocations =
    canManageUsers || user.roles?.includes("supervisor");
  const selected = companies.find((company) => company.id === companyId);
  const saved = () => {
    setRefresh((value) => value + 1);
    setSuccess("Alterações salvas com sucesso.");
  };
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");
    void api<Company[]>("/foundation/companies")
      .then((data) => {
        if (cancelled) return;
        setCompanies(data);
        setCompanyId((current) =>
          data.some((company) => company.id === current)
            ? current
            : (data.find(
                (company) =>
                  company.id ===
                  new URLSearchParams(window.location.search).get("empresa"),
              )?.id ??
              data[0]?.id ??
              ""),
        );
        if (page === "companies" || !data.length) setLoading(false);
      })
      .catch((error) => {
        if (!cancelled) {
          setError(errorMessage(error));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [refresh, page]);
  useEffect(() => {
    if (page === "companies" || !companyId) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    setLocations([]);
    setMembers([]);
    setAudit([]);
    const path = `/foundation/companies/${companyId}`;
    const request =
      page === "audit"
        ? api<Audit[]>(path + "/audit").then((data) => {
            if (!cancelled) setAudit(data);
          })
        : Promise.all([
            api<Location[]>(path + "/locations"),
            page === "users"
              ? api<Member[]>(path + "/users")
              : Promise.resolve([]),
          ]).then(([places, people]) => {
            if (!cancelled) {
              setLocations(places);
              setMembers(people);
            }
          });
    void request
      .catch((error) => {
        if (!cancelled) setError(errorMessage(error));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [companyId, page, refresh]);
  function selectCompany(id: string) {
    setCompanyId(id);
    setSearch("");
    setSuccess("");
    const url = new URL(window.location.href);
    url.searchParams.set("empresa", id);
    window.history.replaceState(null, "", url);
  }
  const filteredCompanies = companies.filter((company) =>
    `${company.name} ${company.slug}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const filteredMembers = members.filter((member) =>
    `${member.name} ${member.email}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  const locationPath = (item: Location): string => {
    const parent = locations.find((location) => location.id === item.parent_id);
    return parent ? `${locationPath(parent)} / ${item.name}` : item.name;
  };
  const orderedLocations: Location[] = [];
  function visit(parent: string | null) {
    locations
      .filter((item) => item.parent_id === parent)
      .forEach((item) => {
        orderedLocations.push(item);
        visit(item.id);
      });
  }
  visit(null);
  // Unidades fora de escopo nunca são reconstruídas a partir de nomes ou IDs.
  const filteredLocations = orderedLocations.filter((item) =>
    locationPath(item).toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            {isNexus
              ? "ADMINISTRAÇÃO DA PLATAFORMA"
              : "ADMINISTRAÇÃO DA EMPRESA"}
          </span>
          <h1>{titles[page]}</h1>
          <p className="muted">{subtitles[page]}</p>
        </div>
        {page === "companies" && isNexus ? (
          <button
            className="button primary"
            onClick={() => setCompanyModal("new")}
          >
            <Plus size={17} />
            Nova empresa
          </button>
        ) : page === "locations" && canManageLocations ? (
          <button
            className="button primary"
            disabled={!companyId || loading || !!error}
            onClick={() => setLocationModal("new")}
          >
            <Plus size={17} />
            Novo local
          </button>
        ) : page === "users" && canManageUsers ? (
          <button
            className="button primary"
            disabled={!companyId || loading || !!error}
            onClick={() => setUserModal("new")}
          >
            <UserPlus size={17} />
            Convidar usuário
          </button>
        ) : null}
      </div>
      {success && <Notice>{success}</Notice>}
      {error && <Notice error>{error}</Notice>}
      {page !== "companies" && companies.length > 0 && (
        <div className="company-selector">
          <Building2 size={20} />
          <div className="field">
            <label htmlFor="selected-company">Empresa</label>
            <select
              id="selected-company"
              value={companyId}
              onChange={(e) => selectCompany(e.target.value)}
            >
              {companies.map((company) => (
                <option value={company.id} key={company.id}>
                  {company.name}
                  {!company.is_active ? " · suspensa" : ""}
                </option>
              ))}
            </select>
          </div>
          <span className="scope-caption">
            <ShieldCheck size={15} />
            Dados no escopo do seu acesso
          </span>
        </div>
      )}
      {loading ? (
        <Loading />
      ) : (
        <>
          {!error && page !== "companies" && !companies.length ? (
            <Empty
              title="Cadastre a primeira empresa"
              text="Crie a empresa para organizar os locais e convidar os responsáveis pela operação."
            />
          ) : (
            !error && (
              <>
                {page !== "audit" && (
                  <div className="list-toolbar">
                    {page === "users" && (
                      <button
                        className="button secondary compact"
                        onClick={() => setRefresh((value) => value + 1)}
                      >
                        Atualizar envios
                      </button>
                    )}
                    <div className="search-field">
                      <Search size={17} />
                      <input
                        aria-label="Buscar registros"
                        placeholder={
                          page === "companies"
                            ? "Buscar empresa ou identificador…"
                            : page === "locations"
                              ? "Buscar na estrutura física…"
                              : "Buscar nome ou e-mail…"
                        }
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                    </div>
                    <span>
                      {page === "companies"
                        ? companies.length +
                          (companies.length === 1 ? " empresa" : " empresas")
                        : page === "locations"
                          ? locations.length +
                            (locations.length === 1 ? " local" : " locais")
                          : members.length +
                            (members.length === 1 ? " usuário" : " usuários")}
                    </span>
                  </div>
                )}
                {page === "companies" &&
                  (filteredCompanies.length ? (
                    <div className="company-grid">
                      {filteredCompanies.map((company) => (
                        <article className="company-card" key={company.id}>
                          <div className="company-card-top">
                            <span className="small-icon">
                              <Building2 size={23} />
                            </span>
                            <span
                              className={`status-badge ${company.is_active ? "configured" : ""}`}
                            >
                              {company.is_active ? "Ativa" : "Suspensa"}
                            </span>
                          </div>
                          <h2>{company.name}</h2>
                          <p className="muted">{company.slug}</p>
                          <div className="company-card-actions">
                            <button
                              className="icon-button"
                              aria-label={`Editar ${company.name}`}
                              onClick={() => setCompanyModal(company)}
                            >
                              <Pencil size={17} />
                            </button>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <Empty
                      title={
                        search
                          ? "Nenhuma empresa encontrada"
                          : "Sua plataforma começa aqui"
                      }
                      text={
                        search
                          ? "Revise os termos da busca."
                          : "Cadastre a primeira empresa para preparar a operação."
                      }
                    />
                  ))}
                {page === "locations" &&
                  (filteredLocations.length ? (
                    <div
                      className="table-container"
                      tabIndex={0}
                      role="region"
                      aria-label="Tabela com rolagem horizontal"
                    >
                      <table>
                        <caption className="sr-only">
                          Locais da empresa {selected?.name}
                        </caption>
                        <thead>
                          <tr>
                            <th>Local</th>
                            <th>Tipo</th>
                            <th>Criticidade</th>
                            <th>Situação</th>
                            {canManageLocations && <th>Ações</th>}
                          </tr>
                        </thead>
                        <tbody>
                          {filteredLocations.map((location) => (
                            <tr key={location.id}>
                              <td>
                                <strong>{location.name}</strong>
                                <small>{locationPath(location)}</small>
                              </td>
                              <td>{kinds[location.kind]}</td>
                              <td>
                                <span
                                  className={`priority ${location.criticality}`}
                                >
                                  {criticalities[location.criticality]}
                                </span>
                              </td>
                              <td>
                                {location.is_active ? "Ativo" : "Inativo"}
                              </td>
                              {canManageLocations && (
                                <td>
                                  <button
                                    className="icon-button"
                                    aria-label={`Editar ${location.name}`}
                                    onClick={() => setLocationModal(location)}
                                  >
                                    <Pencil size={17} />
                                  </button>
                                </td>
                              )}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <Empty
                      title={
                        search
                          ? "Nenhum local encontrado"
                          : "Organize sua estrutura física"
                      }
                      text={
                        search
                          ? "Revise os termos da busca."
                          : "Comece por uma unidade. Depois adicione prédios, andares e ambientes."
                      }
                    />
                  ))}
                {page === "users" &&
                  (filteredMembers.length ? (
                    <div
                      className="table-container"
                      tabIndex={0}
                      role="region"
                      aria-label="Tabela com rolagem horizontal"
                    >
                      <table>
                        <caption className="sr-only">
                          Usuários da empresa {selected?.name}
                        </caption>
                        <thead>
                          <tr>
                            <th>Pessoa</th>
                            <th>Perfis</th>
                            <th>Unidades</th>
                            <th>Acesso</th>
                            <th>Ações</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filteredMembers.map((member) => (
                            <tr key={member.id}>
                              <td>
                                <strong>{member.name}</strong>
                                <small>{member.email}</small>
                              </td>
                              <td>
                                <div className="role-tags">
                                  {member.roles.map((role) => (
                                    <span key={role}>
                                      {roles[role] ?? role}
                                    </span>
                                  ))}
                                </div>
                              </td>
                              <td>
                                {member.all_units
                                  ? "Todas as unidades"
                                  : member.unit_ids
                                      .map(
                                        (id) =>
                                          locations.find(
                                            (location) => location.id === id,
                                          )?.name ?? "Unidade restrita",
                                      )
                                      .join(", ")}
                              </td>
                              <td>
                                {!member.is_active
                                  ? "Suspenso"
                                  : member.invitation_pending
                                    ? "Convite pendente"
                                    : "Ativo"}
                                {member.invitation_email && (
                                  <>
                                    <small>
                                      Último e-mail:{" "}
                                      {emailStates[
                                        member.invitation_email.status
                                      ] ?? "Indisponível"}
                                    </small>
                                    <small>
                                      {member.invitation_email.attempts}{" "}
                                      tentativa(s).{" "}
                                      {member.invitation_email.last_error}
                                    </small>
                                  </>
                                )}
                              </td>
                              <td>
                                <div className="row-actions">
                                  <button
                                    className="icon-button"
                                    aria-label={`Editar acesso de ${member.name}`}
                                    onClick={() => setUserModal(member)}
                                  >
                                    <Pencil size={17} />
                                  </button>
                                  {member.is_active &&
                                    member.invitation_pending && (
                                      <button
                                        className="button secondary compact"
                                        onClick={() => setRenewing(member)}
                                      >
                                        Novo convite
                                      </button>
                                    )}
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <Empty
                      title={
                        search
                          ? "Nenhum usuário encontrado"
                          : "Convide sua equipe"
                      }
                      text={
                        search
                          ? "Revise os termos da busca."
                          : "Comece pelo administrador da empresa, que poderá preparar os demais acessos."
                      }
                    />
                  ))}
                {page === "audit" &&
                  (audit.length ? (
                    <>
                      <p className="form-help">
                        Últimos 100 eventos no escopo autorizado. Não inclui o
                        conteúdo de senhas, chaves ou links de convite.
                      </p>
                      <div
                        className="table-container"
                        tabIndex={0}
                        role="region"
                        aria-label="Tabela com rolagem horizontal"
                      >
                        <table>
                          <caption className="sr-only">
                            Histórico de auditoria da empresa {selected?.name}
                          </caption>
                          <thead>
                            <tr>
                              <th>Data e hora</th>
                              <th>Autor</th>
                              <th>Ação</th>
                              <th>Registro</th>
                            </tr>
                          </thead>
                          <tbody>
                            {audit.map((event) => (
                              <tr key={event.id}>
                                <td>{formatDate(event.created_at)}</td>
                                <td>{event.actor}</td>
                                <td>{actions[event.action] ?? event.action}</td>
                                <td>
                                  <code>{event.entity_id ?? "—"}</code>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  ) : (
                    <Empty
                      title="Nenhum evento disponível"
                      text="As ações administrativas desta empresa serão registradas aqui."
                    />
                  ))}
              </>
            )
          )}
        </>
      )}
      {error && (
        <button
          className="button secondary"
          onClick={() => setRefresh((value) => value + 1)}
        >
          Recarregar dados
        </button>
      )}
      {companyModal && (
        <CompanyForm
          company={companyModal === "new" ? null : companyModal}
          onClose={() => setCompanyModal(null)}
          onSaved={saved}
        />
      )}
      {locationModal && (
        <LocationForm
          companyId={companyId}
          location={locationModal === "new" ? null : locationModal}
          locations={locations}
          canCreateUnit={isNexus || !!user.all_units}
          onClose={() => setLocationModal(null)}
          onSaved={saved}
        />
      )}
      {userModal && (
        <UserForm
          companyId={companyId}
          member={userModal === "new" ? null : userModal}
          units={locations.filter((location) => location.kind === "unit")}
          onClose={() => setUserModal(null)}
          onSaved={saved}
          onInvitation={setInvitation}
        />
      )}
      {invitation && (
        <InvitationDialog
          invitation={invitation}
          onClose={() => setInvitation(null)}
        />
      )}
      {renewing && (
        <RenewInvitation
          companyId={companyId}
          member={renewing}
          onClose={() => setRenewing(null)}
          onSaved={(result) => {
            setRenewing(null);
            setInvitation(result);
            saved();
          }}
        />
      )}
    </>
  );
}
