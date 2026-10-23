import { useEffect, useState } from "react";
import { MessageCircle, RefreshCw } from "lucide-react";
import { api } from "./api";
import { errorMessage, Loading, Notice } from "./ui";

type Connection = {
  configured: boolean;
  status: string;
  qr_code: string | null;
};
const labels: Record<string, string> = {
  not_configured: "Integração indisponível",
  not_connected: "Não conectado",
  starting: "Preparando conexão",
  qr_ready: "Aguardando leitura do QR Code",
  connected: "WhatsApp conectado",
  disconnected: "Desconectado",
};

export function WhatsAppConnection() {
  const [data, setData] = useState<Connection | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [pollUntil, setPollUntil] = useState(0);
  useEffect(() => {
    let active = true;
    setBusy(true);
    setData((old) => (old ? { ...old, qr_code: null } : null));
    void api<Connection>("/company/whatsapp")
      .then((result) => {
        if (active) {
          setData(result);
          setError("");
        }
      })
      .catch((err) => {
        if (active) setError(errorMessage(err));
      })
      .finally(() => {
        if (active) setBusy(false);
      });
    return () => {
      active = false;
    };
  }, [refresh]);
  useEffect(() => {
    if (
      busy ||
      error ||
      !["starting", "qr_ready"].includes(data?.status ?? "") ||
      Date.now() >= pollUntil
    )
      return;
    const timeout = window.setTimeout(() => setRefresh((v) => v + 1), 10000);
    return () => window.clearTimeout(timeout);
  }, [data, busy, error, pollUntil]);
  async function connect() {
    setBusy(true);
    setError("");
    setData((old) => (old ? { ...old, qr_code: null } : null));
    try {
      setData(await api<Connection>("/company/whatsapp/connect", "POST"));
      setPollUntil(Date.now() + 120000);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ADMINISTRAÇÃO DA EMPRESA</span>
          <h1>WhatsApp</h1>
          <p className="muted">
            Conecte o número de atendimento da sua empresa.
          </p>
        </div>
      </div>
      {error && <Notice error>{error}</Notice>}
      <section className="card" aria-labelledby="whatsapp-title">
        <header className="card-header">
          <MessageCircle size={25} aria-hidden="true" />
          <h2 id="whatsapp-title">Conexão WhatsApp</h2>
        </header>
        <div className="card-body">
          <p role="status">
            {labels[data?.status ?? ""] ?? "Consultando conexão…"}
          </p>
          {busy && <Loading />}
          {data && !data.configured && (
            <p>Solicite ao Superadmin a configuração da integração OpenWA.</p>
          )}
          {data?.status === "connected" ? (
            <Notice>
              O número foi conectado ao OpenWA. A abertura de ocorrências pelo
              WhatsApp ainda depende da implantação dos webhooks.
            </Notice>
          ) : (
            <>
              <p>
                No WhatsApp do número da empresa, abra{" "}
                <strong>Aparelhos conectados → Conectar um aparelho</strong> e
                escaneie o QR Code exibido aqui.
              </p>
              <p className="form-help">
                O QR Code é temporário e permite conectar a conta. Compartilhe
                esta tela somente com os responsáveis pela empresa.
              </p>
            </>
          )}
          {!busy && data?.qr_code && (
            <img
              src={data.qr_code}
              alt="QR Code para conectar o WhatsApp da empresa"
              width={280}
              height={280}
              style={{ maxWidth: "100%", height: "auto" }}
            />
          )}
          <div className="detail-buttons">
            {data?.configured && data.status !== "connected" && (
              <button
                className="button primary"
                disabled={busy}
                onClick={() => void connect()}
              >
                Conectar WhatsApp
              </button>
            )}
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => {
                setError("");
                setPollUntil(Date.now() + 120000);
                setRefresh((v) => v + 1);
              }}
            >
              <RefreshCw size={16} aria-hidden="true" />
              Atualizar conexão
            </button>
          </div>
          <p className="form-help">
            Após iniciar a conexão, a tela consulta o status por até dois
            minutos. Se necessário, use Atualizar conexão para obter um novo QR
            Code.
          </p>
        </div>
      </section>
    </>
  );
}
