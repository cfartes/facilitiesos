import { useEffect, useState, type FormEvent } from "react";
import { LoaderCircle, MessageSquare, ShieldCheck } from "lucide-react";
import { api } from "./api";
import { Attachments } from "./Attachments";
import { errorMessage, Loading, Modal, Notice } from "./ui";
import {
  actionNames,
  availablePeople,
  dateTime,
  outcomes,
  priorities,
  states,
  type Meta,
  type OrderDetail as Detail,
} from "./operationTypes";

const labels: Record<string, string> = {
  start: "Iniciar / retomar execução",
  wait: "Registrar espera",
  resolve: "Apresentar solução",
  close: "Concluir atendimento",
  reopen: "Reabrir atendimento",
  cancel: "Cancelar atendimento",
};

export function OrderDetail({
  base,
  id,
  meta,
  onClose,
  onChanged,
}: {
  base: string;
  id: string;
  meta: Meta;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [data, setData] = useState<Detail | null>(null),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [success, setSuccess] = useState(""),
    [action, setAction] = useState("");
  async function load() {
    try {
      setData(await api<Detail>(base + "/orders/" + id));
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setData(null);
    setError("");
    void api<Detail>(base + "/orders/" + id)
      .then((value) => {
        if (!cancelled) setData(value);
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
  }, [base, id]);
  async function run(path: string, body: unknown, kind: string) {
    setBusy(kind);
    setError("");
    setSuccess("");
    try {
      await api(base + "/orders/" + id + path, "POST", body);
      await load();
      onChanged();
      setSuccess("Alteração registrada.");
      return true;
    } catch (error) {
      setError(errorMessage(error));
      return false;
    } finally {
      setBusy("");
    }
  }
  async function submitAction(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!data) return;
    const form = new FormData(event.currentTarget);
    if (
      await run(
        "/actions",
        {
          action,
          expected_version: data.order.version,
          note: form.get("note") ?? "",
          solution: form.get("solution") ?? "",
          evidence: form.get("evidence") ?? "",
        },
        "action",
      )
    )
      setAction("");
  }
  async function message(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget,
      form = new FormData(target);
    if (
      await run(
        "/messages",
        {
          body: form.get("body"),
          visibility: form.get("visibility") ?? "shared",
        },
        "message",
      )
    )
      target.reset();
  }
  const order = data?.order;
  const options = order
    ? Object.keys(labels).filter(
        (value) =>
          (
            ({
              start: ["assigned", "waiting"],
              wait: ["in_progress"],
              resolve: ["in_progress"],
              close: ["resolved"],
              reopen: ["resolved", "closed"],
              cancel: [
                "triage",
                "assigned",
                "in_progress",
                "waiting",
                "resolved",
              ],
            })[value] ?? []
          ).includes(order.state) &&
          (data?.can_execute || false) &&
          (!["close", "reopen", "cancel"].includes(value) ||
            data?.can_coordinate),
      )
    : [];
  return (
    <Modal
      title={order?.code ?? "Ordem de serviço"}
      onClose={onClose}
      busy={!!busy}
      wide
    >
      {loading ? (
        <Loading />
      ) : data && order ? (
        <>
          <div className="order-detail-header">
            <h3 className="detail-title">{order.title}</h3>
            <span className={"order-state " + order.state}>
              {states[order.state]}
            </span>
            <span className={"priority " + order.priority}>
              {priorities[order.priority]}
            </span>
          </div>
          <div className="detail-facts">
            <span>{order.location_name}</span>
            <span>{order.category_name}</span>
            <span>{order.asset_name ?? "Sem ativo relacionado"}</span>
            <span>Responsável: {order.assignee_name ?? "A definir"}</span>
            <span>Ciclo {order.cycle}</span>
          </div>
          <p className="detail-text">{order.description}</p>
          <p className="form-help">
            Abertura: {dateTime(order.created_at)} · Impacto {order.impact} ×
            urgência {order.urgency}. A troca de responsável preserva o
            histórico.
          </p>
          {error && <Notice error>{error}</Notice>}
          {success && <Notice>{success}</Notice>}
          {order.solution && (
            <div className="detail-solution">
              <h4>
                {["resolved", "closed"].includes(order.state)
                  ? "Solução apresentada"
                  : "Última solução — atendimento em revisão"}
              </h4>
              <p className="detail-text">{order.solution}</p>
              <h4>Evidência textual</h4>
              <p className="detail-text">{order.evidence}</p>
            </div>
          )}
          {data.can_coordinate &&
            ["triage", "assigned", "in_progress", "waiting"].includes(
              order.state,
            ) && (
              <form
                className="assignment-form"
                onSubmit={(event) => {
                  event.preventDefault();
                  const form = new FormData(event.currentTarget);
                  void run(
                    "/assign",
                    {
                      assignee_id: form.get("assignee"),
                      expected_version: order.version,
                    },
                    "assign",
                  );
                }}
              >
                <fieldset className="plain-fieldset" disabled={!!busy}>
                  <div className="field">
                    <label htmlFor="detail-assignee">
                      Responsável pelo atendimento
                    </label>
                    <select
                      key={order.assignee_id ?? ""}
                      id="detail-assignee"
                      name="assignee"
                      required
                      defaultValue={order.assignee_id ?? ""}
                    >
                      <option value="">Selecione um responsável</option>
                      {availablePeople(meta, order.unit_id, true).map(
                        (person) => (
                          <option value={person.id} key={person.id}>
                            {person.name}
                          </option>
                        ),
                      )}
                    </select>
                  </div>
                  <button className="button secondary" disabled={!!busy}>
                    {busy === "assign" ? (
                      <LoaderCircle size={16} className="spin" />
                    ) : null}
                    Atualizar responsável
                  </button>
                </fieldset>
              </form>
            )}
          {options.length > 0 && (
            <section className="order-section">
              <h3>Atualizar atendimento</h3>
              <form onSubmit={submitAction}>
                <fieldset className="plain-fieldset" disabled={!!busy}>
                  <div className="field">
                    <label htmlFor="order-action">Próxima ação</label>
                    <select
                      id="order-action"
                      required
                      value={action}
                      onChange={(event) => setAction(event.target.value)}
                    >
                      <option value="">Selecione uma ação</option>
                      {options.map((value) => (
                        <option value={value} key={value}>
                          {labels[value]}
                        </option>
                      ))}
                    </select>
                  </div>
                  {action === "resolve" ? (
                    <>
                      <div className="field">
                        <label htmlFor="resolution">Solução realizada</label>
                        <textarea
                          id="resolution"
                          name="solution"
                          rows={4}
                          required
                          minLength={10}
                          maxLength={4000}
                        />
                      </div>
                      <div className="field">
                        <label htmlFor="evidence">
                          Evidência textual da verificação
                        </label>
                        <textarea
                          id="evidence"
                          name="evidence"
                          rows={4}
                          required
                          minLength={10}
                          maxLength={4000}
                          placeholder="Descreva o teste, medição ou verificação realizada e o resultado observado."
                        />
                      </div>
                      <p className="form-help">
                        A solução será apresentada aos solicitantes para
                        confirmação. Este registro não anexa arquivos.
                      </p>
                    </>
                  ) : (
                    action &&
                    action !== "start" && (
                      <div className="field">
                        <label htmlFor="action-note">
                          {action === "close"
                            ? "Justificativa da revisão (necessária se houver confirmações pendentes)"
                            : "Motivo"}
                        </label>
                        <textarea
                          id="action-note"
                          name="note"
                          rows={3}
                          required={action !== "close"}
                          minLength={10}
                          maxLength={4000}
                        />
                        {action === "wait" && (
                          <small>
                            A espera será registrada com o motivo. Esta etapa
                            ainda não calcula ou pausa SLA.
                          </small>
                        )}
                      </div>
                    )
                  )}
                  <button
                    className="button primary"
                    disabled={!!busy || !action}
                  >
                    {busy === "action" && (
                      <LoaderCircle size={16} className="spin" />
                    )}
                    Registrar ação
                  </button>
                </fieldset>
              </form>
            </section>
          )}
          {data.occurrences.length > 0 && (
            <section className="order-section">
              <h3>
                {meta.can_review ? "Relatos vinculados" : "Suas ocorrências"}
              </h3>
              <ul className="linked-reports">
                {data.occurrences.map((report) => (
                  <li key={report.id}>
                    <strong>
                      {report.code} · {report.requester_name}
                    </strong>
                    <span>{outcomes[report.outcome]}</span>
                  </li>
                ))}
              </ul>
              <p className="form-help">
                A confirmação ou contestação é feita pelo solicitante na tela de
                ocorrências.
              </p>
            </section>
          )}
          <section className="order-section">
            <h3>
              <MessageSquare size={17} />
              Comunicação
            </h3>
            {data.messages.length === 0 ? (
              <p className="form-help">Nenhuma mensagem disponível.</p>
            ) : (
              <ul className="messages-list">
                {data.messages.map((item) => (
                  <li className={item.visibility} key={item.id}>
                    <div>
                      <strong>{item.actor_name}</strong>
                      <small>{dateTime(item.created_at)}</small>
                    </div>
                    {item.visibility === "internal" && (
                      <span className="internal-label">
                        <ShieldCheck size={13} />
                        Nota interna
                      </span>
                    )}
                    <p className="detail-text">{item.body}</p>
                  </li>
                ))}
              </ul>
            )}
            {data.can_message &&
              !["closed", "cancelled"].includes(order.state) && (
                <form onSubmit={message}>
                  <fieldset className="plain-fieldset" disabled={!!busy}>
                    <div className="field">
                      <label htmlFor="message-body">Nova mensagem</label>
                      <textarea
                        id="message-body"
                        name="body"
                        rows={3}
                        required
                        maxLength={4000}
                      />
                    </div>
                    {data.can_internal && (
                      <div className="field">
                        <label htmlFor="message-visibility">
                          Quem pode ler
                        </label>
                        <select
                          id="message-visibility"
                          name="visibility"
                          defaultValue="shared"
                        >
                          <option value="shared">
                            Compartilhada com os solicitantes
                          </option>
                          <option value="internal">
                            Nota interna da equipe
                          </option>
                        </select>
                      </div>
                    )}
                    <button className="button secondary" disabled={!!busy}>
                      {busy === "message" && (
                        <LoaderCircle size={16} className="spin" />
                      )}
                      Enviar mensagem
                    </button>
                  </fieldset>
                </form>
              )}
          </section>
          <Attachments
            base={base + "/orders/" + id}
            revision={order.version}
            onChanged={() => {
              void load();
            }}
          />
          <section className="order-section">
            <h3>Linha do tempo</h3>
            <ol className="order-timeline">
              {data.events.map((item) => (
                <li key={item.id}>
                  <strong>{actionNames[item.action] ?? item.action}</strong>
                  <small>
                    {dateTime(item.created_at)} · {item.actor_name} · Ciclo{" "}
                    {item.cycle}
                  </small>
                  {item.note && <p className="detail-text">{item.note}</p>}
                </li>
              ))}
            </ol>
          </section>
        </>
      ) : error ? (
        <Notice error>{error}</Notice>
      ) : null}
    </Modal>
  );
}
