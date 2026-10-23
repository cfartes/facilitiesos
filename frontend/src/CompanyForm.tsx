import { useState, type FormEvent } from "react";
import { Eye, EyeOff, LoaderCircle } from "lucide-react";
import { api } from "./api";
import { CompanyAddress } from "./CompanyAddress";
import { DocumentInput } from "./components/DocumentInput";
import { PhoneInput } from "./components/PhoneInput";
import { errorMessage, Modal, Notice } from "./ui";
import type { Company } from "./types";

export function CompanyForm({
  company,
  onClose,
  onSaved,
}: {
  company: Company | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [active, setActive] = useState(company?.is_active ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [visible, setVisible] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    const fields = [
      "trade_name",
      "corporate_name",
      "slug",
      "cnpj",
      "contact_phone",
      "address",
      "address_number",
      "address_complement",
      "neighborhood",
      "city",
      "state",
      "postal_code",
      "operational_profile",
    ];
    const values = Object.fromEntries(
      fields.map((field) => [field, String(form.get(field) ?? "").trim()]),
    );
    try {
      await api(
        `/foundation/companies${company ? "/" + company.id : ""}`,
        company ? "PUT" : "POST",
        company
          ? { ...values, is_active: active, expected_version: company.version }
          : {
              ...values,
              admin: {
                full_name: form.get("full_name"),
                email: form.get("email"),
                password: form.get("password"),
              },
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
      title={company ? "Editar empresa" : "Nova empresa"}
      onClose={onClose}
      busy={busy}
      wide
    >
      <form onSubmit={submit}>
        <fieldset className="plain-fieldset" disabled={busy}>
          <p className="form-help">
            {company
              ? "Atualize os dados cadastrais da empresa. Ao alterar o identificador de acesso, informe o novo identificador à equipe."
              : "Cadastre a empresa e seu primeiro administrador. Todos os campos são obrigatórios, exceto o complemento do endereço."}
          </p>
          <p className="company-data-notice">
            Os dados serão usados para identificação, contato e administração do
            serviço. Evite dados sensíveis em campos livres.
          </p>
          <fieldset className="company-section">
            <legend>Dados da empresa</legend>
            <div className="company-form-grid">
              <div className="field">
                <label htmlFor="company-trade">Nome comercial</label>
                <input
                  id="company-trade"
                  name="trade_name"
                  autoFocus
                  required
                  minLength={2}
                  maxLength={150}
                  defaultValue={company?.name ?? ""}
                />
              </div>
              <div className="field">
                <label htmlFor="company-corporate">Razão social</label>
                <input
                  id="company-corporate"
                  name="corporate_name"
                  required
                  minLength={2}
                  maxLength={150}
                  defaultValue={company?.corporate_name ?? company?.name ?? ""}
                />
              </div>
              <div className="field">
                <label htmlFor="company-slug">Identificador de acesso</label>
                <input
                  id="company-slug"
                  name="slug"
                  required
                  minLength={2}
                  maxLength={company ? 60 : 50}
                  pattern={company ? `[a-z0-9]+|${company.slug}` : "[a-z0-9]+"}
                  defaultValue={company?.slug ?? ""}
                  placeholder="empresaexemplo"
                  aria-describedby="company-slug-help"
                />
                <small id="company-slug-help">
                  Use letras minúsculas e números, de 2 a 50 caracteres, sem
                  espaços ou símbolos. Identificadores anteriores podem ser
                  mantidos.
                </small>
              </div>
              <div className="field">
                <label htmlFor="company-cnpj">CPF/CNPJ</label>
                <DocumentInput initialValue={company?.cnpj ?? ""} required />
                <small id="document-help">
                  CPF com 11 dígitos ou CNPJ com 14 caracteres. Os dígitos
                  verificadores serão conferidos ao salvar.
                </small>
              </div>
              <div className="field">
                <label htmlFor="company-contact_phone">
                  Telefone / WhatsApp
                </label>
                <PhoneInput
                  initialValue={company?.contact_phone ?? ""}
                  required
                />
                <small>
                  Contato da empresa. Use DDD ou + e código do país.
                </small>
              </div>
            </div>
          </fieldset>
          <CompanyAddress company={company} />
          <fieldset className="company-section">
            <legend>Tipo de operação</legend>
            <div className="field">
              <label htmlFor="company-profile">Perfil operacional</label>
              <select
                id="company-profile"
                name="operational_profile"
                required
                defaultValue={company?.operational_profile ?? ""}
              >
                <option value="" disabled>
                  Selecione o tipo de operação
                </option>
                <option value="office">
                  Escritórios e ambientes corporativos
                </option>
                <option value="industrial">Indústria e fábricas</option>
                <option value="logistics">
                  Logística e centros de distribuição
                </option>
                <option value="mixed">Uso misto</option>
              </select>
            </div>
          </fieldset>
          {!company && (
            <fieldset className="company-section">
              <legend>Administrador da empresa</legend>
              <div className="company-form-grid">
                <div className="field">
                  <label htmlFor="company-admin-name">Nome completo</label>
                  <input
                    id="company-admin-name"
                    name="full_name"
                    minLength={2}
                    maxLength={150}
                    required
                    autoComplete="off"
                  />
                </div>
                <div className="field">
                  <label htmlFor="company-admin-email">E-mail</label>
                  <input
                    id="company-admin-email"
                    name="email"
                    type="email"
                    maxLength={254}
                    required
                    autoComplete="off"
                  />
                </div>
                <div className="field">
                  <label htmlFor="company-admin-password">Senha inicial</label>
                  <div className="secret-input">
                    <input
                      id="company-admin-password"
                      name="password"
                      type={visible ? "text" : "password"}
                      minLength={12}
                      maxLength={128}
                      required
                      autoComplete="new-password"
                      aria-describedby="company-password-help"
                    />
                    <button
                      className="icon-button"
                      type="button"
                      aria-label={
                        visible
                          ? "Ocultar senha inicial"
                          : "Mostrar senha inicial"
                      }
                      onClick={() => setVisible(!visible)}
                    >
                      {visible ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                  </div>
                </div>
              </div>
              <p id="company-password-help" className="form-help">
                Mínimo de 12 caracteres, uma letra maiúscula e um caractere
                especial. O administrador terá acesso a todas as unidades.
                Compartilhe o acesso por um canal seguro.
              </p>
            </fieldset>
          )}
          {company && (
            <label className="checkbox">
              <input
                type="checkbox"
                checked={active}
                onChange={(e) => setActive(e.target.checked)}
              />
              Empresa ativa
            </label>
          )}
          {company && !active && (
            <p className="form-help">
              Suspender a empresa encerra as sessões de seus usuários e bloqueia
              novos acessos, preservando os registros.
            </p>
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
            <button className="button primary" disabled={busy}>
              {busy && <LoaderCircle size={16} className="spin" />}
              {company ? "Salvar empresa" : "Cadastrar empresa"}
            </button>
          </div>
        </fieldset>
      </form>
    </Modal>
  );
}
