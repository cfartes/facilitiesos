import { useState, type FormEvent, type ReactNode } from "react";
import { LoaderCircle } from "lucide-react";
import { api } from "./api";
import { Attachments } from "./Attachments";
import { OccurrenceMessages } from "./OccurrenceMessages";
import { errorMessage, Modal, Notice } from "./ui";
import type {
  Asset,
  Category,
  Meta,
  Occurrence,
  WorkOrder,
} from "./operationTypes";
import {
  availablePeople,
  assetStates,
  dateTime,
  outcomes,
  placeName,
  priorities,
  states,
} from "./operationTypes";

function Form({
  children,
  onSubmit,
  busy,
  error,
  label = "Salvar",
  onClose,
}: {
  children: ReactNode;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  busy: boolean;
  error: string;
  label?: string;
  onClose: () => void;
}) {
  return (
    <form onSubmit={onSubmit}>
      <fieldset className="plain-fieldset" disabled={busy}>
        {children}
        {error && <Notice error>{error}</Notice>}
        <div className="modal-actions">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="button primary" disabled={busy}>
            {busy && <LoaderCircle className="spin" size={16} />} {label}
          </button>
        </div>
      </fieldset>
    </form>
  );
}

export function CatalogForm({
  kind,
  asset,
  category,
  meta,
  base,
  onClose,
  onSaved,
}: {
  kind: "asset" | "category";
  asset?: Asset;
  category?: Category;
  meta: Meta;
  base: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const common = { name: form.get("name") };
      const body =
        kind === "category"
          ? {
              ...common,
              ...(category
                ? {
                    expected_version: category.version,
                    is_active: form.get("active") === "on",
                  }
                : {}),
            }
          : {
              ...common,
              category: form.get("category"),
              criticality: form.get("criticality"),
              ...(asset
                ? {
                    expected_version: asset.version,
                    status: form.get("status"),
                  }
                : {
                    code: form.get("code"),
                    location_id: form.get("location"),
                  }),
            };
      const id = kind === "category" ? category?.id : asset?.id;
      await api(
        base +
          (kind === "category" ? "/categories" : "/assets") +
          (id ? "/" + id : ""),
        id ? "PUT" : "POST",
        body,
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
      title={
        kind === "category"
          ? category
            ? "Editar categoria"
            : "Nova categoria"
          : asset
            ? "Editar ativo"
            : "Novo ativo"
      }
      onClose={onClose}
      busy={busy}
    >
      <Form onSubmit={submit} busy={busy} error={error} onClose={onClose}>
        <div className="field">
          <label htmlFor="catalog-name">Nome</label>
          <input
            id="catalog-name"
            name="name"
            required
            minLength={2}
            maxLength={kind === "category" ? 120 : 160}
            defaultValue={asset?.name ?? category?.name ?? ""}
          />
        </div>
        {kind === "category" ? (
          category && (
            <label className="checkbox">
              <input
                name="active"
                type="checkbox"
                defaultChecked={!!category.is_active}
              />
              Categoria ativa
            </label>
          )
        ) : (
          <>
            {!asset && (
              <>
                <div className="field">
                  <label htmlFor="asset-code">Identificação do ativo</label>
                  <input
                    id="asset-code"
                    name="code"
                    required
                    minLength={2}
                    maxLength={40}
                    pattern="[A-Za-z0-9][A-Za-z0-9._-]*"
                    placeholder="AC-001"
                  />
                </div>
                <div className="field">
                  <label htmlFor="asset-place">Local do ativo</label>
                  <select
                    id="asset-place"
                    name="location"
                    required
                    defaultValue=""
                  >
                    <option value="">Selecione um local ativo</option>
                    {meta.locations
                      .filter((item) => item.is_active)
                      .map((item) => (
                        <option key={item.id} value={item.id}>
                          {placeName(meta, item.id)}
                        </option>
                      ))}
                  </select>
                </div>
              </>
            )}
            {asset && (
              <p className="form-help">
                {asset.code} · {placeName(meta, asset.location_id)}. O vínculo
                ao local é preservado para manter o histórico.
              </p>
            )}
            <div className="field">
              <label htmlFor="asset-category">Categoria do equipamento</label>
              <input
                id="asset-category"
                name="category"
                required
                minLength={2}
                maxLength={100}
                defaultValue={asset?.category ?? ""}
                placeholder="Climatização, elétrica, hidráulica…"
              />
            </div>
            <div className="field">
              <label htmlFor="asset-criticality">Criticidade</label>
              <select
                id="asset-criticality"
                name="criticality"
                defaultValue={asset?.criticality ?? "medium"}
              >
                {Object.entries(priorities).map(([value, label]) => (
                  <option value={value} key={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            {asset && (
              <div className="field">
                <label htmlFor="asset-status">Situação do ativo</label>
                <select
                  id="asset-status"
                  name="status"
                  defaultValue={asset.status}
                >
                  {Object.entries(assetStates).map(([value, label]) => (
                    <option value={value} key={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </>
        )}
      </Form>
    </Modal>
  );
}

export function OccurrenceForm({
  meta,
  base,
  onClose,
  onSaved,
}: {
  meta: Meta;
  base: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [location, setLocation] = useState(""),
    [asset, setAsset] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [requestId] = useState(() => crypto.randomUUID());
  const unit =
    meta.locations.find((item) => item.id === location)?.unit_id ?? "";
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      await api(base + "/occurrences", "POST", {
        title: form.get("title"),
        description: form.get("description"),
        location_id: location,
        category_id: form.get("category"),
        asset_id: asset || null,
        requester_id: form.get("requester") || undefined,
        client_request_id: requestId,
      });
      onSaved();
      onClose();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Nova ocorrência" onClose={onClose} busy={busy} wide>
      <p className="form-help">
        Informe o problema e o local. A equipe fará a triagem e direcionará o
        atendimento. Evite dados pessoais sensíveis nos campos livres. Depois de
        registrar, abra a ocorrência para adicionar fotos de evidência.
      </p>
      <Form
        onSubmit={submit}
        busy={busy}
        error={error}
        onClose={onClose}
        label="Registrar ocorrência"
      >
        <div className="field">
          <label htmlFor="report-title">O que aconteceu?</label>
          <input
            id="report-title"
            name="title"
            required
            minLength={5}
            maxLength={180}
            placeholder="Ex.: ar-condicionado vazando na sala de reunião"
          />
        </div>
        <div className="company-form-grid">
          <div className="field">
            <label htmlFor="report-place">Local da ocorrência</label>
            <select
              id="report-place"
              required
              value={location}
              onChange={(e) => {
                setLocation(e.target.value);
                setAsset("");
              }}
            >
              <option value="">Selecione o local</option>
              {meta.locations
                .filter((item) => item.is_active)
                .map((item) => (
                  <option key={item.id} value={item.id}>
                    {placeName(meta, item.id)}
                  </option>
                ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="report-category">Categoria do serviço</label>
            <select
              id="report-category"
              name="category"
              required
              defaultValue=""
            >
              <option value="">Selecione a categoria</option>
              {meta.categories
                .filter((item) => item.is_active)
                .map((item) => (
                  <option value={item.id} key={item.id}>
                    {item.name}
                  </option>
                ))}
            </select>
          </div>
        </div>
        <div className="field">
          <label htmlFor="report-asset">Ativo relacionado (opcional)</label>
          <select
            id="report-asset"
            value={asset}
            onChange={(e) => setAsset(e.target.value)}
          >
            <option value="">Sem ativo identificado</option>
            {meta.assets
              .filter(
                (item) =>
                  item.location_id === location && item.status !== "retired",
              )
              .map((item) => (
                <option value={item.id} key={item.id}>
                  {item.code} · {item.name}
                </option>
              ))}
          </select>
        </div>
        {meta.can_coordinate && (
          <div className="field">
            <label htmlFor="report-requester">Solicitante</label>
            <select
              id="report-requester"
              key={unit}
              name="requester"
              required={!meta.viewer_id}
              defaultValue=""
            >
              <option value="">
                {meta.viewer_id
                  ? "Eu mesmo"
                  : "Selecione a pessoa que relatou o problema"}
              </option>
              {availablePeople(meta, unit)
                .filter(
                  (person) =>
                    person.id !== meta.viewer_id &&
                    person.roles.some((role) => role !== "auditor"),
                )
                .map((person) => (
                  <option value={person.id} key={person.id}>
                    {person.name}
                  </option>
                ))}
            </select>
          </div>
        )}
        <div className="field">
          <label htmlFor="report-description">Descrição do problema</label>
          <textarea
            id="report-description"
            name="description"
            rows={5}
            required
            minLength={10}
            maxLength={4000}
            placeholder="Descreva o que observou e como isso afeta a operação."
          />
        </div>
      </Form>
    </Modal>
  );
}

export function OccurrenceDetail({
  report,
  meta,
  orders,
  base,
  onClose,
  onChanged,
  onOrder,
}: {
  report: Occurrence;
  meta: Meta;
  orders: WorkOrder[];
  base: string;
  onClose: () => void;
  onChanged: () => void;
  onOrder: (id: string) => void;
}) {
  const [mode, setMode] = useState("view"),
    [reportVersion, setReportVersion] = useState(report.version),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [impact, setImpact] = useState(2),
    [urgency, setUrgency] = useState(2);
  const score = impact * urgency,
    calculated =
      score >= 12
        ? "critical"
        : score >= 8
          ? "high"
          : score >= 4
            ? "medium"
            : "low";
  const candidates = orders.filter(
    (order) =>
      ["triage", "assigned", "in_progress", "waiting"].includes(order.state) &&
      ["location_id", "category_id", "asset_id"].every(
        (key) =>
          order[key as keyof WorkOrder] === report[key as keyof Occurrence],
      ),
  );
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      if (mode === "create") {
        const order = await api<WorkOrder>(base + "/orders", "POST", {
          occurrence_id: report.id,
          expected_occurrence_version: reportVersion,
          title: form.get("title"),
          description: form.get("description"),
          impact,
          urgency,
          assignee_id: form.get("assignee") || null,
        });
        onChanged();
        onClose();
        onOrder(order.id);
      } else if (mode === "link") {
        const identifier = String(form.get("order"));
        const order = orders.find((item) => item.id === identifier)!;
        await api(base + "/orders/" + identifier + "/link", "POST", {
          occurrence_id: report.id,
          expected_version: order.version,
        });
        onChanged();
        onClose();
        onOrder(identifier);
      } else {
        await api(
          base + "/occurrences/" + report.id + "/confirmation",
          "POST",
          {
            outcome: mode,
            expected_version: reportVersion,
            note: form.get("note") ?? "",
          },
        );
        onChanged();
        onClose();
      }
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title={report.code} onClose={onClose} busy={busy} wide>
      <h3 className="detail-title">{report.title}</h3>
      <p className="form-help">
        As fotos deste relato são privadas ao solicitante e à equipe com acesso
        à triagem. Para compartilhar uma imagem com os participantes de uma
        ordem, anexe-a na própria ordem.
      </p>
      <div className="detail-facts">
        <span>{report.location_name}</span>
        <span>{report.category_name}</span>
        <span>{report.asset_name ?? "Sem ativo relacionado"}</span>
        <span>{outcomes[report.outcome]}</span>
      </div>
      <p className="detail-text">{report.description}</p>
      <p className="form-help">
        Solicitante: {report.requester_name} · Abertura:{" "}
        {dateTime(report.created_at)}
        {report.first_response_at &&
          " · Primeira resposta humana: " + dateTime(report.first_response_at)}
      </p>
      {report.order_id && (
        <div className="detail-solution">
          <strong>
            {report.order_code} · {states[report.order_state ?? ""]}
          </strong>
          {report.solution && (
            <>
              <h4>Solução apresentada</h4>
              <p className="detail-text">{report.solution}</p>
              <h4>Evidência textual</h4>
              <p className="detail-text">{report.evidence}</p>
            </>
          )}
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              onClose();
              onOrder(report.order_id!);
            }}
          >
            Abrir ordem de serviço
          </button>
        </div>
      )}
      {mode === "view" && (
        <OccurrenceMessages
          base={base + "/occurrences/" + report.id}
          onVersion={setReportVersion}
        />
      )}
      {mode === "view" && (
        <Attachments base={base + "/occurrences/" + report.id} />
      )}
      {mode === "view" ? (
        <div className="detail-buttons">
          {meta.can_coordinate && !report.order_id && (
            <>
              <button
                className="button primary"
                onClick={() => setMode("create")}
              >
                Criar ordem de serviço
              </button>
              <button
                className="button secondary"
                disabled={!candidates.length}
                onClick={() => setMode("link")}
              >
                Vincular a uma ordem existente
              </button>
            </>
          )}
          {report.requester_id === meta.viewer_id &&
            ["resolved", "closed"].includes(report.order_state ?? "") &&
            report.outcome !== "confirmed" && (
              <>
                <button
                  className="button primary"
                  onClick={() => setMode("confirmed")}
                >
                  Confirmar solução
                </button>
                <button
                  className="button secondary"
                  onClick={() => setMode("contested")}
                >
                  Contestar solução
                </button>
              </>
            )}
        </div>
      ) : (
        <Form
          onSubmit={submit}
          busy={busy}
          error={error}
          onClose={() => setMode("view")}
          label={
            mode === "create"
              ? "Criar ordem"
              : mode === "link"
                ? "Vincular relato"
                : mode === "confirmed"
                  ? "Confirmar solução"
                  : "Contestar e reabrir"
          }
        >
          {mode === "create" ? (
            <>
              <div className="field">
                <label htmlFor="order-title">Título da ordem</label>
                <input
                  id="order-title"
                  name="title"
                  required
                  minLength={5}
                  maxLength={180}
                  defaultValue={report.title}
                />
              </div>
              <div className="field">
                <label htmlFor="order-description">
                  Descrição do atendimento
                </label>
                <textarea
                  id="order-description"
                  name="description"
                  rows={4}
                  required
                  minLength={10}
                  maxLength={4000}
                  defaultValue={report.description}
                />
              </div>
              <div className="company-form-grid">
                <div className="field">
                  <label htmlFor="order-impact">Impacto operacional</label>
                  <select
                    id="order-impact"
                    value={impact}
                    onChange={(e) => setImpact(Number(e.target.value))}
                  >
                    {[
                      "1 · Localizado",
                      "2 · Moderado",
                      "3 · Elevado",
                      "4 · Operação crítica",
                    ].map((label, index) => (
                      <option value={index + 1} key={label}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="order-urgency">Urgência</label>
                  <select
                    id="order-urgency"
                    value={urgency}
                    onChange={(e) => setUrgency(Number(e.target.value))}
                  >
                    {[
                      "1 · Pode aguardar",
                      "2 · Atendimento planejável",
                      "3 · Atendimento urgente",
                      "4 · Ação imediata",
                    ].map((label, index) => (
                      <option value={index + 1} key={label}>
                        {label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <p className="form-help">
                Prioridade: <strong>{priorities[calculated]}</strong>. Impacto ×
                urgência: {score}. Faixas: 1–3 baixa, 4–7 média, 8–11 alta,
                12–16 crítica.
              </p>
              <div className="field">
                <label htmlFor="order-assignee">
                  Responsável (opcional na triagem)
                </label>
                <select id="order-assignee" name="assignee" defaultValue="">
                  <option value="">Atribuir depois</option>
                  {availablePeople(meta, report.unit_id, true).map((person) => (
                    <option value={person.id} key={person.id}>
                      {person.name}
                    </option>
                  ))}
                </select>
              </div>
            </>
          ) : mode === "link" ? (
            <div className="field">
              <label htmlFor="existing-order">Ordem em andamento</label>
              <select id="existing-order" name="order" defaultValue="" required>
                <option value="">Selecione a ordem do mesmo problema</option>
                {candidates.map((order) => (
                  <option value={order.id} key={order.id}>
                    {order.code} · {order.title}
                  </option>
                ))}
              </select>
              <small>
                Somente ordens do mesmo local, categoria e ativo podem receber
                este relato.
              </small>
            </div>
          ) : (
            <>
              <p className="form-help">
                {mode === "confirmed"
                  ? "Confirme após verificar se o problema foi resolvido."
                  : "A contestação reabre o atendimento e preserva o histórico anterior."}
              </p>
              <div className="field">
                <label htmlFor="confirmation-note">
                  {mode === "confirmed"
                    ? "Comentário (opcional)"
                    : "Motivo da contestação"}
                </label>
                <textarea
                  id="confirmation-note"
                  name="note"
                  rows={4}
                  minLength={mode === "contested" ? 10 : undefined}
                  required={mode === "contested"}
                  maxLength={2000}
                />
              </div>
            </>
          )}
        </Form>
      )}
    </Modal>
  );
}
