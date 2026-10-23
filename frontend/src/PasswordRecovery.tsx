import { useState, type FormEvent } from "react";
import { Building2, LoaderCircle, ShieldCheck } from "lucide-react";
import { api } from "./api";
import { Notice, errorMessage } from "./ui";

export function PasswordRecovery() {
  const [email, setEmail] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api<{ message: string }>(
        "/public/password-reset/request",
        "POST",
        { email },
      );
      setMessage(result.message);
      setEmail("");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="invitation-page">
      <section className="invitation-card">
        <div className="invitation-brand">
          <Building2 size={25} aria-hidden="true" />
          <strong>Nexus Facilities OS</strong>
        </div>
        <span className="small-icon">
          <ShieldCheck size={25} aria-hidden="true" />
        </span>
        <span className="eyebrow">RECUPERAÇÃO DE ACESSO</span>
        <h1>Esqueceu sua senha?</h1>
        <p className="muted">
          Informe o e-mail do seu acesso. Se a recuperação estiver disponível
          para a conta, você receberá um link individual.
        </p>
        {message ? (
          <>
            <Notice>{message}</Notice>
            <button
              type="button"
              className="button secondary full"
              onClick={() => setMessage("")}
            >
              Tentar outro e-mail
            </button>
          </>
        ) : (
          <form onSubmit={submit}>
            <fieldset className="plain-fieldset" disabled={busy}>
              <div className="field">
                <label htmlFor="recovery-email">E-mail do acesso</label>
                <input
                  id="recovery-email"
                  type="email"
                  autoComplete="email"
                  maxLength={254}
                  required
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </div>
              {error && <Notice error>{error}</Notice>}
              <button className="button primary full" disabled={busy}>
                {busy && (
                  <LoaderCircle size={18} className="spin" aria-hidden="true" />
                )}{" "}
                {busy ? "Solicitando…" : "Solicitar recuperação"}
              </button>
            </fieldset>
          </form>
        )}
        <p className="login-note">
          Para contas de empresas. Se você ainda não ativou seu acesso ou não
          receber o e-mail, contate o administrador. A recuperação do acesso
          Nexus é feita pelo responsável pela instalação.
        </p>
        <p className="login-note">
          <a href="/">Voltar para o login</a>
        </p>
      </section>
    </main>
  );
}
