import { useEffect, useState, type FormEvent } from "react";
import {
  Building2,
  Eye,
  EyeOff,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";
import { api } from "./api";
import { errorMessage, Notice } from "./ui";

export function AcceptInvitation({
  passwordReset = false,
}: { passwordReset?: boolean } = {}) {
  const [token] = useState(
    () => new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "",
  );
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [visible, setVisible] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  useEffect(() => {
    window.history.replaceState(
      null,
      "",
      passwordReset ? "/redefinir-senha" : "/convite",
    );
  }, [passwordReset]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (password !== confirmation) {
      setError("As senhas precisam ser iguais.");
      return;
    }
    setBusy(true);
    try {
      const result = await api<{ message: string }>(
        passwordReset
          ? "/public/password-reset/confirm"
          : "/public/invitations/accept",
        "POST",
        { token, password },
      );
      setSuccess(result.message);
      setPassword("");
      setConfirmation("");
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
          <Building2 size={25} />
          <strong>Nexus Facilities OS</strong>
        </div>
        <span className="small-icon">
          <ShieldCheck size={25} />
        </span>
        <span className="eyebrow">
          {passwordReset ? "RECUPERAÇÃO DE ACESSO" : "PRIMEIRO ACESSO"}
        </span>
        <h1>
          {passwordReset ? "Defina uma nova senha" : "Bem-vindo à sua operação"}
        </h1>
        <p className="muted">
          {passwordReset
            ? "Após a troca, suas sessões anteriores serão encerradas. Entre novamente para continuar."
            : "Defina sua senha para ativar o acesso concedido pela empresa."}
        </p>
        {success ? (
          <>
            <Notice>{success}</Notice>
            <a className="button primary full" href="/">
              Ir para o login
            </a>
          </>
        ) : !token ? (
          <Notice error>
            {passwordReset
              ? "O link de recuperação está incompleto. Abra o link recebido por e-mail ou solicite a recuperação novamente."
              : "O link do convite está incompleto. Abra o link fornecido pelo administrador ou solicite um novo convite."}
          </Notice>
        ) : (
          <form onSubmit={submit}>
            <fieldset disabled={busy} className="plain-fieldset">
              <div className="field">
                <label htmlFor="new-password">Nova senha</label>
                <div className="secret-input">
                  <input
                    id="new-password"
                    type={visible ? "text" : "password"}
                    minLength={12}
                    maxLength={passwordReset ? 128 : 1024}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="new-password"
                    aria-describedby="password-hint"
                    required
                  />
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={visible ? "Ocultar senha" : "Mostrar senha"}
                    onClick={() => setVisible(!visible)}
                  >
                    {visible ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
                <small id="password-hint">
                  {passwordReset
                    ? "Use de 12 a 128 caracteres, uma letra maiúscula e um caractere especial. Escolha uma senha diferente da atual."
                    : "Use pelo menos 12 caracteres e uma senha exclusiva."}
                </small>
              </div>
              <div className="field">
                <label htmlFor="confirm-password">Confirme a senha</label>
                <input
                  id="confirm-password"
                  type="password"
                  minLength={12}
                  maxLength={passwordReset ? 128 : 1024}
                  autoComplete="new-password"
                  required
                  value={confirmation}
                  onChange={(e) => setConfirmation(e.target.value)}
                />
              </div>
              {error && <Notice error>{error}</Notice>}
              <button className="button primary full" disabled={busy}>
                {busy ? (
                  <LoaderCircle className="spin" size={17} />
                ) : (
                  <ShieldCheck size={17} />
                )}
                {busy
                  ? passwordReset
                    ? "Alterando…"
                    : "Ativando…"
                  : passwordReset
                    ? "Alterar senha"
                    : "Ativar meu acesso"}
              </button>
            </fieldset>
          </form>
        )}
        <p className="login-note">
          {passwordReset
            ? "Link individual, válido por 30 minutos e de uso único."
            : "Convite individual, válido por 48 horas e de uso único."}
        </p>
        {passwordReset && !success && (
          <p className="login-note">
            <a href="/recuperar-senha">Solicitar recuperação novamente</a>
          </p>
        )}
      </section>
    </main>
  );
}
