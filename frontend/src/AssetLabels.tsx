import { useState, type FormEvent } from "react";
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
  const [items, setItems] = useState<Label[]>([]);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
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
              disabled={busy}
              aria-describedby="label-phone-help"
            />
            <p className="form-help" id="label-phone-help">
              Informe o número conectado no menu WhatsApp desta empresa. Confira
              antes de imprimir: as etiquetas encaminharão as solicitações para
              esse número.
            </p>
          </div>
          <fieldset className="label-selection" disabled={busy}>
            <legend>
              Equipamentos do filtro atual ({selected.length} selecionados)
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
              disabled={busy || !selected.length}
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
                Imprimir {items.length} etiqueta(s)
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
