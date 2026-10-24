import { useEffect, useState } from "react";
import { api } from "./api";
import { errorMessage, Loading, Notice } from "./ui";

type Settings = {
  enabled: boolean;
  hook_status: string;
  public_url_configured: boolean;
  replies: Record<string, number>;
};

export function WhatsAppIntake({ connected }: { connected: boolean }) {
  const [data, setData] = useState<Settings | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    let active = true;
    void api<Settings>("/company/whatsapp/intake")
      .then((value) => {
        if (active) {
          setData(value);
          setError("");
        }
      })
      .catch((err) => {
        if (active) setError(errorMessage(err));
      });
    return () => {
      active = false;
    };
  }, [refresh]);
  async function toggle() {
    if (!data) return;
    setBusy(true);
    setError("");
    try {
      setData(
        await api<Settings>("/company/whatsapp/intake", "POST", {
          enabled: !data.enabled,
        }),
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section
      className="card"
      aria-labelledby="whatsapp-intake-title"
      style={{ marginTop: 24 }}
    >
      <header className="card-header">
        <h2 id="whatsapp-intake-title">Abertura de solicitações</h2>
      </header>
      <div className="card-body">
        <p>
          O colaborador envia uma mensagem, informa o nome no primeiro contato e
          identifica o equipamento pela etiqueta QR ou escolhe unidade e local,
          e pode enviar até três fotos. O sistema mostra um resumo e só registra
          a ocorrência após a confirmação.
        </p>
        <p className="form-help">
          Os contatos não recebem senha nem acesso ao painel. Imprima as
          etiquetas no cadastro de ativos. A leitura do QR é feita pela câmera
          do celular; as fotos são enviadas pelo clipe ou câmera do WhatsApp,
          quando solicitadas. Acompanhamento e atualizações pelo WhatsApp ficam
          para a próxima etapa.
        </p>
        {error && <Notice error>{error}</Notice>}
        {!data ? (
          error ? (
            <button
              className="button secondary"
              onClick={() => setRefresh((v) => v + 1)}
            >
              Tentar novamente
            </button>
          ) : (
            <Loading />
          )
        ) : (
          <>
            <p role="status">
              {data.enabled
                ? "Recebimento habilitado"
                : "Recebimento desativado"}
              {data.hook_status === "error"
                ? " · Revisar conexão do webhook"
                : ""}
            </p>
            {!data.public_url_configured && (
              <p>
                O responsável pela instalação precisa configurar o endereço
                público de recebimento.
              </p>
            )}
            <div className="detail-buttons">
              <button
                className="button primary"
                disabled={
                  busy ||
                  (!data.enabled && (!connected || !data.public_url_configured))
                }
                onClick={() => void toggle()}
              >
                {busy
                  ? "Salvando…"
                  : data.enabled
                    ? "Desativar solicitações"
                    : "Ativar solicitações pelo WhatsApp"}
              </button>
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => setRefresh((v) => v + 1)}
              >
                Atualizar recebimento
              </button>
            </div>
            <p className="form-help">
              Respostas na fila: {data.replies.queued ?? 0} · Aceitas pelo
              provedor: {data.replies.accepted ?? 0} · Resultado não confirmado:{" "}
              {data.replies.uncertain ?? 0}. Aceite não comprova entrega.
            </p>
            {!!data.replies.uncertain && (
              <Notice error>
                Há respostas cujo envio não foi confirmado. Confira o WhatsApp
                antes de orientar o colaborador a retomar com MENU; essas
                mensagens não serão repetidas automaticamente.
              </Notice>
            )}
          </>
        )}
      </div>
    </section>
  );
}
