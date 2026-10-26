import { useEffect, useState, type FormEvent } from "react";
import { createPortal } from "react-dom";
import { Printer } from "lucide-react";
import { api } from "./api";
import { errorMessage, Modal, Notice } from "./ui";
import type { Asset } from "./operationTypes";

type Label = {
  id: string;
  code: string;
  name: string;
  location: string;
  qr_code: string;
};

function Sheet({ items }: { items: Label[] }) {
  return (
    <div className="asset-label-grid">
      {items.map((item) => (
        <article className="asset-label" key={item.id}>
          <img
            src={item.qr_code}
            width={180}
            height={180}
            alt={"QR Code do equipamento " + item.code}
          />
          <div>
            <strong>{item.code}</strong>
            <h3>{item.name}</h3>
            <p>{item.location}</p>
            <small>
              Leia com a câmera do celular e envie a mensagem no WhatsApp para
              relatar um problema.
            </small>
          </div>
        </article>
      ))}
    </div>
  );
}

export function AssetLabels({
  company,
  assets,
  onClose,
}: {
  company: string;
  assets: Asset[];
  onClose: () => void;
}) {
  const [selected, setSelected] = useState(() => assets.map((item) => item.id));
  const [phone, setPhone] = useState("");
  const [phoneLoading, setPhoneLoading] = useState(true);
  const [phoneNotice, setPhoneNotice] = useState("");
  const [items, setItems] = useState<Label[]>([]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    setPhoneLoading(true);
    setPhone("");
    setPhoneNotice("");
    void api<{ phone: string }>(
      "/operations/companies/" + company + "/assets/labels/whatsapp",
      "GET",
      undefined,
      controller.signal,
    )
      .then((result) => {
        if (controller.signal.aborted) return;
        setPhone(result.phone);
        if (!result.phone)
          setPhoneNotice(
            "O número da sessão WhatsApp não está disponível. Informe o número de atendimento manualmente.",
          );
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setPhoneNotice(
            "Não foi possível consultar o WhatsApp conectado. Informe o número de atendimento manualmente.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setPhoneLoading(false);
      });
    return () => controller.abort();
  }, [company]);
  async function generate(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setItems([]);
    try {
      const result = await api<{ items: Label[] }>(
        "/operations/companies/" + company + "/assets/labels",
        "POST",
        { asset_ids: selected, phone: phone.replace(/\D/g, "") },
      );
      setItems(result.items);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Modal
        title="Imprimir QR Codes dos equipamentos"
        onClose={onClose}
        busy={busy}
        wide
      >
        {error && <Notice error>{error}</Notice>}
        {phoneNotice && (
          <p className="form-help" role="status">
            {phoneNotice}
          </p>
        )}
        <form onSubmit={generate}>
          <div className="field">
            <label htmlFor="label-phone">
              WhatsApp de atendimento da empresa (DDI + DDD + número)
            </label>
            <input
              id="label-phone"
              value={phone}
              onChange={(event) => {
                setPhone(event.target.value);
                setItems([]);
              }}
              type="tel"
              placeholder="5511999999999"
              required
              maxLength={25}
              disabled={busy || phoneLoading}
              aria-describedby="label-phone-help"
            />
            <p className="form-help" id="label-phone-help">
              {phoneLoading
                ? "Consultando o número do WhatsApp conectado… "
                : "O campo usa o número da sessão WhatsApp desta empresa, quando disponível. Você pode ajustá-lo. "}
              Confira antes de imprimir: as etiquetas encaminharão as
              solicitações para esse número.
            </p>
          </div>
          <fieldset className="label-selection" disabled={busy}>
            <legend>
              Equipamentos do filtro atual ({selected.length}{" "}
              {selected.length === 1 ? "selecionado" : "selecionados"})
            </legend>
            <label className="checkbox">
              <input
                type="checkbox"
                checked={selected.length === assets.length}
                onChange={(event) => {
                  setSelected(
                    event.target.checked ? assets.map((item) => item.id) : [],
                  );
                  setItems([]);
                }}
              />
              Selecionar todos
            </label>
            {assets.map((item) => (
              <label className="checkbox" key={item.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(item.id)}
                  onChange={(event) => {
                    setSelected(
                      event.target.checked
                        ? [...selected, item.id]
                        : selected.filter((id) => id !== item.id),
                    );
                    setItems([]);
                  }}
                />
                {item.code} — {item.name}
              </label>
            ))}
          </fieldset>
          <p className="form-help">
            Folha A4, duas etiquetas por linha. Use escala de 100% e desative
            cabeçalhos/rodapés na impressão. A lista respeita seu acesso e o
            limite de 1.000 equipamentos do piloto.
          </p>
          <div className="detail-buttons">
            <button
              className="button secondary"
              disabled={busy || phoneLoading || !selected.length}
            >
              {busy ? "Gerando…" : "Gerar pré-visualização"}
            </button>
            {items.length > 0 && (
              <button
                type="button"
                className="button primary"
                onClick={() => window.print()}
              >
                <Printer size={17} />
                Imprimir {items.length}{" "}
                {items.length === 1 ? "etiqueta" : "etiquetas"}
              </button>
            )}
          </div>
        </form>
        {items.length > 0 && <Sheet items={items} />}
      </Modal>
      {items.length > 0 &&
        createPortal(
          <section className="asset-label-print" aria-hidden="true">
            <Sheet items={items} />
          </section>,
          document.body,
        )}
    </>
  );
}
