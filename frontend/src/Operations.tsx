import { useEffect, useRef, useState } from "react";
import {
  Bell,
  Building2,
  Check,
  Columns3,
  List,
  Pencil,
  Plus,
  Printer,
  Search,
  ShieldCheck,
} from "lucide-react";
import { api } from "./api";
import { errorMessage, Loading, Notice } from "./ui";
import {
  CatalogForm,
  OccurrenceDetail,
  OccurrenceForm,
} from "./OperationForms";
import { OrderDetail } from "./OrderDetail";
import { AssetLabels } from "./AssetLabels";
import {
  assetStates,
  dateTime,
  outcomes,
  placeName,
  priorities,
  states,
  type Asset,
  type Category,
  type Meta,
  type Notification,
  type Occurrence,
  type OperationPage,
  type WorkOrder,
} from "./operationTypes";
import type { Company, User } from "./types";

const names: Record<OperationPage, string> = {
  assets: "Ativos",
  categories: "Categorias de serviço",
  occurrences: "Ocorrências",
  orders: "Ordens de serviço",
  notifications: "Suas notificações",
};
const subtitles: Record<OperationPage, string> = {
  assets: "Conheça os equipamentos e o histórico de atendimento de cada local.",
  categories: "Organize os tipos de atendimento disponíveis aos solicitantes.",
  occurrences: "Do relato ao resultado, acompanhe cada problema registrado.",
  orders: "Priorize, distribua e acompanhe o trabalho da operação.",
  notifications: "Acompanhe as atualizações dos seus atendimentos.",
};
function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="empty-state">
      <h2>Nenhum registro disponível</h2>
      <p>{children}</p>
    </div>
  );
}

export function Operations({
  page,
  user,
}: {
  page: OperationPage;
  user: User;
}) {
  const [companies, setCompanies] = useState<Company[]>([]),
    [company, setCompany] = useState(""),
    [meta, setMeta] = useState<Meta | null>(null),
    [reports, setReports] = useState<Occurrence[]>([]),
    [orders, setOrders] = useState<WorkOrder[]>([]),
    [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [refresh, setRefresh] = useState(0),
    [search, setSearch] = useState(""),
    [status, setStatus] = useState(""),
    [priority, setPriority] = useState(""),
    [view, setView] = useState("list");
  const [catalog, setCatalog] = useState<Asset | Category | "new" | null>(null),
    [newReport, setNewReport] = useState(false),
    [report, setReport] = useState<Occurrence | null>(null),
    [order, setOrder] = useState<string | null>(() =>
      new URLSearchParams(location.search).get("ordem"),
    ),
    [assetFilter, setAssetFilter] = useState(
      () => new URLSearchParams(location.search).get("ativo") ?? "",
    );
  const base = "/operations/companies/" + company,
    navBase = user.role === "superadmin" ? "/nexus" : "/app";
  const [labelAssets, setLabelAssets] = useState<Asset[] | null>(null);
  const loadedCompany = useRef("");
  useEffect(() => {
    let cancelled = false;
    void api<Company[]>("/foundation/companies")
      .then((rows) => {
        if (cancelled) return;
        setCompanies(rows);
        setCompany(
          rows.find(
            (item) =>
              item.id === new URLSearchParams(location.search).get("empresa"),
          )?.id ??
            rows[0]?.id ??
            "",
        );
        if (!rows.length) setLoading(false);
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
  }, []);
  useEffect(() => {
    if (!company) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    if (loadedCompany.current !== company) setMeta(null);
    setReports([]);
    setOrders([]);
    setNotifications([]);
    void Promise.all([
      api<Meta>(base + "/metadata"),
      page === "occurrences"
        ? api<Occurrence[]>(base + "/occurrences")
        : Promise.resolve([]),
      ["orders", "occurrences"].includes(page)
        ? api<WorkOrder[]>(base + "/orders")
        : Promise.resolve([]),
      page === "notifications"
        ? api<Notification[]>(base + "/notifications")
        : Promise.resolve([]),
    ])
      .then(([metadata, occurrences, work, alerts]) => {
        if (cancelled) return;
        setMeta(metadata);
        loadedCompany.current = company;
        setReports(occurrences);
        setOrders(work);
        setNotifications(alerts);
        const selected = new URLSearchParams(location.search).get("ocorrencia");
        if (selected)
          setReport(occurrences.find((item) => item.id === selected) ?? null);
      })
      .catch((error) => {
        if (!cancelled) setError(errorMessage(error));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [company, page, refresh]);
  const changed = () => {
    setRefresh((value) => value + 1);
    setNotice("Alterações registradas.");
  };
  const matches = (value: string) =>
    value
      .toLocaleLowerCase("pt-BR")
      .includes(search.toLocaleLowerCase("pt-BR"));
  const visibleOrders = orders.filter(
    (item) =>
      matches(
        item.code +
          " " +
          item.title +
          " " +
          item.location_name +
          " " +
          (item.assignee_name ?? ""),
      ) &&
      (!status || item.state === status) &&
      (!priority || item.priority === priority) &&
      (!assetFilter || item.asset_id === assetFilter),
  );
  const visibleReports = reports.filter((item) =>
    matches(
      item.code +
        " " +
        item.title +
        " " +
        item.location_name +
        " " +
        item.requester_name,
    ),
  );
  const visibleAssets =
    meta?.assets.filter((item) =>
      matches(item.code + " " + item.name + " " + item.category),
    ) ?? [];
  const visibleCategories =
    meta?.categories.filter((item) => matches(item.name)) ?? [];
  const canCatalog =
    meta?.can_coordinate &&
    (page !== "categories" || user.role === "superadmin" || user.all_units);
  async function openNotification(item: Notification) {
    setError("");
    try {
      await api(base + "/notifications/" + item.id + "/read", "POST");
      if (item.order_id)
        location.href =
          navBase + "/ordens?empresa=" + company + "&ordem=" + item.order_id;
      else if (item.occurrence_id)
        location.href =
          navBase +
          "/ocorrencias?empresa=" +
          company +
          "&ocorrencia=" +
          item.occurrence_id;
      else changed();
    } catch (error) {
      setError(errorMessage(error));
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">OPERAÇÃO FACILITIES</span>
          <h1>{names[page]}</h1>
          <p className="muted">{subtitles[page]}</p>
        </div>
        {!loading &&
          meta &&
          (page === "occurrences" && meta.can_report ? (
            <button
              className="button primary"
              disabled={
                !meta.locations.some((item) => item.is_active) ||
                !meta.categories.some((item) => item.is_active)
              }
              onClick={() => setNewReport(true)}
            >
              <Plus size={17} />
              Nova ocorrência
            </button>
          ) : ["assets", "categories"].includes(page) && canCatalog ? (
            <button
              className="button primary"
              disabled={
                page === "assets" &&
                !meta.locations.some((item) => item.is_active)
              }
              onClick={() => setCatalog("new")}
            >
              <Plus size={17} />
              {page === "assets" ? "Novo ativo" : "Nova categoria"}
            </button>
          ) : null)}
      </div>
      {notice && <Notice>{notice}</Notice>}
      {error && <Notice error>{error}</Notice>}
      {companies.length > 0 && (
        <div className="company-selector">
          <Building2 size={20} />
          <div className="field">
            <label htmlFor="operation-company">Empresa</label>
            <select
              id="operation-company"
              value={company}
              onChange={(event) => {
                setCompany(event.target.value);
                setReport(null);
                setOrder(null);
                setCatalog(null);
                setSearch("");
                setNotice("");
                setAssetFilter("");
                const url = new URL(location.href);
                url.search = "?empresa=" + event.target.value;
                history.replaceState(null, "", url);
              }}
            >
              {companies.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name}
                  {!item.is_active ? " · suspensa" : ""}
                </option>
              ))}
            </select>
          </div>
          <span className="scope-caption">
            <ShieldCheck size={15} />
            Acesso por empresa, unidade e atendimento
          </span>
        </div>
      )}
      {loading ? (
        <Loading />
      ) : !company ? (
        <Empty>Cadastre uma empresa para preparar a operação.</Empty>
      ) : meta ? (
        <>
          {page === "orders" && (
            <div className="operation-summary">
              <article>
                <small>Ordens listadas</small>
                <strong>{visibleOrders.length}</strong>
              </article>
              <article>
                <small>Prioridade crítica</small>
                <strong>
                  {
                    visibleOrders.filter(
                      (item) =>
                        item.priority === "critical" &&
                        !["closed", "cancelled"].includes(item.state),
                    ).length
                  }
                </strong>
              </article>
              <article>
                <small>Em execução</small>
                <strong>
                  {
                    visibleOrders.filter((item) => item.state === "in_progress")
                      .length
                  }
                </strong>
              </article>
              <article>
                <small>Aguardando confirmação</small>
                <strong>
                  {
                    visibleOrders.filter((item) => item.state === "resolved")
                      .length
                  }
                </strong>
              </article>
            </div>
          )}
          {page !== "notifications" && (
            <div className="list-toolbar operation-toolbar">
              <div className="search-field">
                <Search size={17} />
                <input
                  aria-label="Buscar na operação"
                  placeholder="Buscar por identificação, título ou local…"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                />
              </div>
              {page === "orders" && (
                <>
                  <select
                    aria-label="Filtrar por situação"
                    value={status}
                    onChange={(event) => setStatus(event.target.value)}
                  >
                    <option value="">Todas as situações</option>
                    {Object.entries(states).map(([value, label]) => (
                      <option value={value} key={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <select
                    aria-label="Filtrar por prioridade"
                    value={priority}
                    onChange={(event) => setPriority(event.target.value)}
                  >
                    <option value="">Todas as prioridades</option>
                    {Object.entries(priorities).map(([value, label]) => (
                      <option value={value} key={value}>
                        {label}
                      </option>
                    ))}
                  </select>
                  <div
                    className="view-switch"
                    role="group"
                    aria-label="Visualização das ordens"
                  >
                    <button
                      className="icon-button"
                      aria-label="Visualizar lista"
                      aria-pressed={view === "list"}
                      onClick={() => setView("list")}
                    >
                      <List size={19} />
                    </button>
                    <button
                      className="icon-button"
                      aria-label="Visualizar quadro"
                      aria-pressed={view === "board"}
                      onClick={() => setView("board")}
                    >
                      <Columns3 size={19} />
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
          {page === "assets" && meta.can_coordinate && (
            <div className="detail-buttons">
              <button
                className="button secondary"
                disabled={
                  !visibleAssets.some((item) => item.status !== "retired")
                }
                onClick={() =>
                  setLabelAssets(
                    visibleAssets.filter((item) => item.status !== "retired"),
                  )
                }
              >
                <Printer size={17} />
                Imprimir QR Codes
              </button>
            </div>
          )}
          {page === "assets" &&
            (visibleAssets.length ? (
              <div
                className="table-container"
                role="region"
                aria-label="Tabela de ativos"
                tabIndex={0}
              >
                <table>
                  <caption className="sr-only">Ativos no seu acesso</caption>
                  <thead>
                    <tr>
                      <th>Ativo</th>
                      <th>Local</th>
                      <th>Criticidade</th>
                      <th>Situação</th>
                      <th>Ações</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleAssets.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <strong>
                            {item.code} · {item.name}
                          </strong>
                          <small>{item.category}</small>
                        </td>
                        <td>{placeName(meta, item.location_id)}</td>
                        <td>
                          <span className={"priority " + item.criticality}>
                            {priorities[item.criticality]}
                          </span>
                        </td>
                        <td>{assetStates[item.status]}</td>
                        <td>
                          <div className="row-actions">
                            {meta.can_coordinate &&
                              item.status !== "retired" && (
                                <button
                                  className="icon-button"
                                  aria-label={
                                    "Imprimir QR Code de " + item.name
                                  }
                                  onClick={() => setLabelAssets([item])}
                                >
                                  <Printer size={16} />
                                </button>
                              )}
                            {meta.can_coordinate && (
                              <button
                                className="icon-button"
                                aria-label={"Editar ativo " + item.name}
                                onClick={() => setCatalog(item)}
                              >
                                <Pencil size={16} />
                              </button>
                            )}
                            <a
                              className="button secondary compact"
                              href={
                                navBase +
                                "/ordens?empresa=" +
                                company +
                                "&ativo=" +
                                item.id
                              }
                            >
                              Histórico
                            </a>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty>
                Cadastre os equipamentos e vincule cada ativo ao local onde está
                instalado.
              </Empty>
            ))}
          {page === "categories" &&
            (visibleCategories.length ? (
              <div
                className="table-container"
                role="region"
                aria-label="Tabela de categorias"
                tabIndex={0}
              >
                <table>
                  <caption className="sr-only">Categorias de serviço</caption>
                  <thead>
                    <tr>
                      <th>Categoria</th>
                      <th>Situação</th>
                      {canCatalog && <th>Ações</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {visibleCategories.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <strong>{item.name}</strong>
                        </td>
                        <td>{item.is_active ? "Ativa" : "Inativa"}</td>
                        {canCatalog && (
                          <td>
                            <button
                              className="icon-button"
                              aria-label={"Editar categoria " + item.name}
                              onClick={() => setCatalog(item)}
                            >
                              <Pencil size={16} />
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <Empty>
                Cadastre os serviços atendidos pela equipe, como elétrica,
                hidráulica e climatização.
              </Empty>
            ))}
          {page === "occurrences" && (
            <>
              {(!meta.locations.some((item) => item.is_active) ||
                !meta.categories.some((item) => item.is_active)) && (
                <p className="form-help">
                  É necessário ter um local e uma categoria ativos para
                  registrar ocorrências. Solicite a preparação ao administrador
                  da empresa.
                </p>
              )}
              {visibleReports.length ? (
                <div
                  className="table-container"
                  role="region"
                  aria-label="Tabela de ocorrências"
                  tabIndex={0}
                >
                  <table>
                    <caption className="sr-only">
                      Ocorrências no seu acesso
                    </caption>
                    <thead>
                      <tr>
                        <th>Ocorrência</th>
                        <th>Local e serviço</th>
                        <th>Solicitante</th>
                        <th>Andamento</th>
                        <th>Abertura</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleReports.map((item) => (
                        <tr key={item.id}>
                          <td>
                            <button
                              className="record-link"
                              onClick={() => setReport(item)}
                            >
                              {item.code}
                              <strong>{item.title}</strong>
                            </button>
                          </td>
                          <td>
                            {item.location_name}
                            <small>
                              {item.category_name}
                              {item.asset_name ? " · " + item.asset_name : ""}
                            </small>
                          </td>
                          <td>{item.requester_name}</td>
                          <td>
                            {outcomes[item.outcome]}
                            {item.order_code && (
                              <small>
                                {item.order_code} ·{" "}
                                {states[item.order_state ?? ""]}
                              </small>
                            )}
                          </td>
                          <td>{dateTime(item.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <Empty>
                  Registre um problema para iniciar o acompanhamento com a
                  equipe responsável.
                </Empty>
              )}
            </>
          )}
          {page === "orders" && (
            <>
              {assetFilter && (
                <div className="asset-filter-note">
                  <span>
                    Histórico do ativo:{" "}
                    {meta.assets.find((item) => item.id === assetFilter)
                      ?.name ?? "ativo selecionado"}
                  </span>
                  <button
                    className="button secondary compact"
                    onClick={() => setAssetFilter("")}
                  >
                    Mostrar todos os ativos
                  </button>
                </div>
              )}
              {visibleOrders.length === 0 ? (
                <Empty>
                  As ordens são criadas pela coordenação a partir da triagem das
                  ocorrências.
                </Empty>
              ) : view === "board" ? (
                <div
                  className="orders-board"
                  role="region"
                  aria-label="Quadro de ordens de serviço"
                  tabIndex={0}
                >
                  {Object.entries(states).map(([state, label]) => (
                    <section className="board-column" key={state}>
                      <h2>
                        {label}
                        <span>
                          {
                            visibleOrders.filter((item) => item.state === state)
                              .length
                          }
                        </span>
                      </h2>
                      {visibleOrders
                        .filter((item) => item.state === state)
                        .map((item) => (
                          <button
                            className="order-card"
                            onClick={() => setOrder(item.id)}
                            key={item.id}
                          >
                            <span className={"priority " + item.priority}>
                              {priorities[item.priority]}
                            </span>
                            <small>{item.code}</small>
                            <strong>{item.title}</strong>
                            <span>{item.location_name}</span>
                            <span>
                              {item.assignee_name ?? "Responsável a definir"}
                            </span>
                          </button>
                        ))}
                    </section>
                  ))}
                </div>
              ) : (
                <div
                  className="table-container"
                  role="region"
                  aria-label="Tabela de ordens"
                  tabIndex={0}
                >
                  <table>
                    <caption className="sr-only">
                      Ordens de serviço no seu acesso
                    </caption>
                    <thead>
                      <tr>
                        <th>Ordem</th>
                        <th>Situação</th>
                        <th>Prioridade</th>
                        <th>Responsável</th>
                        <th>Local</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleOrders.map((item) => (
                        <tr key={item.id}>
                          <td>
                            <button
                              className="record-link"
                              onClick={() => setOrder(item.id)}
                            >
                              {item.code}
                              <strong>{item.title}</strong>
                            </button>
                          </td>
                          <td>
                            <span className={"order-state " + item.state}>
                              {states[item.state]}
                            </span>
                          </td>
                          <td>
                            <span className={"priority " + item.priority}>
                              {priorities[item.priority]}
                            </span>
                          </td>
                          <td>{item.assignee_name ?? "A definir"}</td>
                          <td>
                            {item.location_name}
                            <small>{item.category_name}</small>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
          {page === "notifications" &&
            (notifications.length ? (
              <>
                <p className="form-help">
                  {notifications.filter((item) => !item.read_at).length} não
                  lidas entre as últimas {notifications.length} notificações.
                </p>
                <ul className="notifications-list">
                  {notifications.map((item) => (
                    <li
                      className={item.read_at ? "read" : "unread"}
                      key={item.id}
                    >
                      <Bell size={19} />
                      <div>
                        <strong>{item.title}</strong>
                        <small>
                          {dateTime(item.created_at)} ·{" "}
                          {item.read_at ? "Lida" : "Não lida"}
                        </small>
                      </div>
                      <button
                        className="button secondary"
                        onClick={() => void openNotification(item)}
                      >
                        {item.order_id || item.occurrence_id ? (
                          "Abrir atendimento"
                        ) : (
                          <>
                            <Check size={16} />
                            Marcar como lida
                          </>
                        )}
                      </button>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <Empty>
                Você receberá avisos sobre os atendimentos em que participa.
              </Empty>
            ))}
        </>
      ) : error ? (
        <button
          className="button secondary"
          onClick={() => setRefresh((value) => value + 1)}
        >
          Recarregar dados
        </button>
      ) : null}
      {meta && catalog && (
        <CatalogForm
          kind={page === "categories" ? "category" : "asset"}
          category={
            page === "categories" && catalog !== "new"
              ? (catalog as Category)
              : undefined
          }
          asset={
            page === "assets" && catalog !== "new"
              ? (catalog as Asset)
              : undefined
          }
          meta={meta}
          base={base}
          onClose={() => setCatalog(null)}
          onSaved={changed}
          onPrint={(asset) => {
            setCatalog(null);
            setLabelAssets([asset]);
          }}
        />
      )}
      {labelAssets && (
        <AssetLabels
          company={company}
          assets={labelAssets}
          onClose={() => setLabelAssets(null)}
        />
      )}
      {meta && newReport && (
        <OccurrenceForm
          meta={meta}
          base={base}
          onClose={() => setNewReport(false)}
          onSaved={changed}
        />
      )}
      {meta && report && (
        <OccurrenceDetail
          report={report}
          meta={meta}
          orders={orders}
          base={base}
          onClose={() => {
            const url = new URL(location.href);
            url.searchParams.delete("ocorrencia");
            history.replaceState(null, "", url);
            setReport(null);
          }}
          onChanged={changed}
          onOrder={setOrder}
        />
      )}
      {meta && order && (
        <OrderDetail
          base={base}
          id={order}
          meta={meta}
          onClose={() => setOrder(null)}
          onChanged={changed}
        />
      )}
    </>
  );
}
