import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Company } from "./types";

type Address = {
  address: string;
  neighborhood: string;
  city: string;
  state: string;
};
const STATES =
  "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(
    " ",
  );

export function CompanyAddress({ company }: { company: Company | null }) {
  const [postal, setPostal] = useState(
    (company?.postal_code ?? "").replace(/\D/g, ""),
  );
  const [address, setAddress] = useState<Address>({
    address: company?.address ?? "",
    neighborhood: company?.neighborhood ?? "",
    city: company?.city ?? "",
    state: company?.state ?? "",
  });
  const [notice, setNotice] = useState("");
  const edited = useRef({ address: 0, neighborhood: 0, city: 0, state: 0 });
  const previous = useRef(postal);
  function change(key: keyof Address, value: string) {
    edited.current[key]++;
    setAddress((current) => ({ ...current, [key]: value }));
  }
  useEffect(() => {
    if (postal.length !== 8 || postal === previous.current) return;
    const controller = new AbortController();
    const revisions = { ...edited.current };
    let disposed = false;
    let timeout: ReturnType<typeof setTimeout>;
    const timer = setTimeout(async () => {
      previous.current = postal;
      setNotice("Consultando CEP…");
      timeout = setTimeout(() => controller.abort(), 8000);
      try {
        const result = await api<Address>(
          `/foundation/postal-code/${postal}`,
          "GET",
          undefined,
          controller.signal,
        );
        if (disposed) return;
        if (
          !result ||
          !Object.keys(revisions).every(
            (key) => typeof result[key as keyof Address] === "string",
          )
        )
          throw new Error("Resposta de CEP inválida.");
        setAddress(
          (current) =>
            Object.fromEntries(
              Object.keys(current).map((key) => {
                const field = key as keyof Address;
                return [
                  field,
                  edited.current[field] === revisions[field] && result[field]
                    ? result[field]
                    : current[field],
                ];
              }),
            ) as Address,
        );
        setNotice(
          "CEP consultado. Confira o endereço e informe o número e o complemento, se houver.",
        );
      } catch {
        if (!disposed)
          setNotice(
            "Não foi possível consultar o CEP. Os campos continuam disponíveis para preenchimento manual.",
          );
      } finally {
        clearTimeout(timeout);
      }
    }, 350);
    return () => {
      disposed = true;
      clearTimeout(timer);
      clearTimeout(timeout);
      controller.abort();
    };
  }, [postal]);
  return (
    <fieldset className="company-section">
      <legend>Endereço da empresa</legend>
      <div className="company-form-grid">
        <div className="field">
          <label htmlFor="company-postal">CEP</label>
          <input
            id="company-postal"
            name="postal_code"
            autoComplete="postal-code"
            inputMode="numeric"
            maxLength={9}
            pattern="[0-9]{5}-?[0-9]{3}"
            required
            placeholder="00000-000"
            value={postal.replace(/^(\d{5})(\d)/, "$1-$2")}
            onChange={(event) => {
              previous.current = "";
              setNotice("");
              setPostal(event.target.value.replace(/\D/g, "").slice(0, 8));
            }}
          />
        </div>
        <div className="field">
          <label htmlFor="company-address">Endereço</label>
          <input
            id="company-address"
            name="address"
            required
            minLength={2}
            maxLength={250}
            autoComplete="address-line1"
            value={address.address}
            onChange={(e) => change("address", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="company-number">Número</label>
          <input
            id="company-number"
            name="address_number"
            required
            maxLength={30}
            placeholder="Número ou S/N"
            defaultValue={company?.address_number ?? ""}
          />
        </div>
        <div className="field">
          <label htmlFor="company-complement">Complemento (opcional)</label>
          <input
            id="company-complement"
            name="address_complement"
            maxLength={150}
            defaultValue={company?.address_complement ?? ""}
          />
        </div>
        <div className="field">
          <label htmlFor="company-neighborhood">Bairro</label>
          <input
            id="company-neighborhood"
            name="neighborhood"
            minLength={2}
            maxLength={100}
            required
            value={address.neighborhood}
            onChange={(e) => change("neighborhood", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="company-city">Cidade</label>
          <input
            id="company-city"
            name="city"
            minLength={2}
            maxLength={100}
            autoComplete="address-level2"
            required
            value={address.city}
            onChange={(e) => change("city", e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="company-state">UF</label>
          <select
            id="company-state"
            name="state"
            autoComplete="address-level1"
            required
            value={address.state}
            onChange={(e) => change("state", e.target.value)}
          >
            <option value="">Selecione</option>
            {STATES.map((state) => (
              <option key={state}>{state}</option>
            ))}
          </select>
        </div>
      </div>
      {notice && (
        <p className="form-help" role="status">
          {notice}
        </p>
      )}
    </fieldset>
  );
}
