import { useEffect, useRef, useState, type FormEvent } from "react";
import { api } from "./api";
import { dateTime } from "./operationTypes";
import { errorMessage, Loading, Notice } from "./ui";

type History = {
  items: { id: string; actor_name: string; body: string; created_at: string }[];
  can_add: boolean;
  version: number;
};

export function OccurrenceMessages({
  base,
  onVersion,
}: {
  base: string;
  onVersion: (version: number) => void;
}) {
  const [data, setData] = useState<History | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const request = useRef<{ body: string; id: string } | null>(null);
  useEffect(() => {
    let active = true;
    void api<History>(base + "/messages")
      .then((result) => {
        if (active) {
          setData(result);
          onVersion(result.version);
        }
      })
      .catch((err) => {
        if (active) setError(errorMessage(err));
      });
    return () => {
      active = false;
    };
  }, [base, refresh, onVersion]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const target = event.currentTarget;
    const body = String(new FormData(target).get("body")).trim();
    if (!body) {
      setError("Informe o complemento.");
      return;
    }
    if (request.current?.body !== body)
      request.current = { body, id: crypto.randomUUID() };
    setBusy(true);
    setError("");
    try {
      const result = await api<{ version: number }>(
        base + "/messages",
        "POST",
        {
          body,
          client_request_id: request.current.id,
        },
      );
      onVersion(result.version);
      request.current = null;
      target.reset();
      setRefresh((value) => value + 1);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section aria-label="Complementos privados">
      <h3>Complementos do relato</h3>
      <p className="form-help">
        Visíveis ao solicitante e à equipe com acesso à triagem. Este histórico
        permanece privado após a vinculação à ordem.
      </p>
      {error && <Notice error>{error}</Notice>}
      {!data ? (
        error ? (
          <button
            className="button secondary"
            onClick={() => {
              setError("");
              setRefresh((v) => v + 1);
            }}
          >
            Tentar carregar novamente
          </button>
        ) : (
          <Loading />
        )
      ) : (
        <>
          <div aria-live="polite">
            {data.items.length ? (
              data.items.map((item) => (
                <article className="detail-solution" key={item.id}>
                  <strong>{item.actor_name}</strong>
                  <p className="form-help">{dateTime(item.created_at)}</p>
                  <p className="detail-text">{item.body}</p>
                </article>
              ))
            ) : (
              <p className="form-help">Nenhum complemento registrado.</p>
            )}
          </div>
          {data.can_add ? (
            <form onSubmit={submit}>
              <div className="field">
                <label htmlFor="occurrence-message">
                  Adicionar complemento privado
                </label>
                <textarea
                  id="occurrence-message"
                  name="body"
                  required
                  maxLength={4000}
                  rows={3}
                  disabled={busy}
                />
              </div>
              <button
                className="button secondary"
                type="submit"
                disabled={busy}
              >
                {busy ? "Registrando…" : "Registrar complemento"}
              </button>
            </form>
          ) : (
            <p className="form-help">
              Novos complementos exigem um relato sem ordem vinculada e acesso
              de solicitante ou coordenação. Para um atendimento vinculado, use
              as mensagens da ordem.
            </p>
          )}
        </>
      )}
    </section>
  );
}
