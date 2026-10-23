import { useEffect, useState } from "react";
import { api } from "./api";

export function InvitationEmailChoice({
  companyId,
  value,
  onChange,
}: {
  companyId: string;
  value: boolean;
  onChange: (value: boolean) => void;
}) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let cancelled = false;
    void api<{ enabled: boolean }>(
      `/foundation/companies/${companyId}/invitation-email`,
    )
      .then((result) => {
        if (!cancelled) setEnabled(result.enabled);
      })
      .catch(() => {
        if (!cancelled) {
          setEnabled(false);
          setFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [companyId]);
  return (
    <>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={value}
          disabled={!enabled}
          onChange={(event) => onChange(event.target.checked)}
        />{" "}
        Enviar convite por e-mail
      </label>
      <p className="form-help">
        {enabled === null
          ? "Consultando disponibilidade do envio…"
          : failed
            ? "Não foi possível consultar o envio por e-mail. Você pode gerar e compartilhar o link manualmente."
            : enabled
              ? "O e-mail será enfileirado após salvar. Acompanhe o resultado na lista de usuários. O aceite do provedor não confirma entrega."
              : "Envio por e-mail desativado. O Superadmin pode habilitá-lo nas integrações. O link manual continua disponível."}
      </p>
    </>
  );
}
