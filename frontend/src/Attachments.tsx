import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import {
  Download,
  ImagePlus,
  LoaderCircle,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { api, downloadAttachment } from "./api";
import { dateTime } from "./operationTypes";
import { errorMessage, Loading, Notice } from "./ui";

type Attachment = {
  id: string;
  filename: string;
  content_type: string;
  byte_size: number;
  visibility: string;
  uploader_name: string;
  created_at: string;
  can_remove: boolean;
};
type Data = { items: Attachment[]; can_upload: boolean; can_internal: boolean };

export function Attachments({
  base,
  revision = 0,
  onChanged,
}: {
  base: string;
  revision?: number;
  onChanged?: () => void;
}) {
  const [data, setData] = useState<Data | null>(null);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState("");
  const [removing, setRemoving] = useState<Attachment | null>(null),
    [file, setFile] = useState<File | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const id = useId();
  const path = base + "/attachments";
  useEffect(() => {
    const abort = new AbortController();
    setData(null);
    setError("");
    setRemoving(null);
    setFile(null);
    void api<Data>(path, "GET", undefined, abort.signal)
      .then(setData)
      .catch((error) => {
        if (!abort.signal.aborted) setError(errorMessage(error));
      });
    return () => abort.abort();
  }, [path, revision]);
  async function reload() {
    setData(await api<Data>(path));
  }
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    if (
      !["image/jpeg", "image/png"].includes(file.type) ||
      file.size > 5 * 1024 * 1024 ||
      !file.size
    ) {
      setError("Escolha uma foto JPEG ou PNG de até 5 MiB.");
      return;
    }
    const form = new FormData(event.currentTarget);
    setBusy("upload");
    setError("");
    setNotice("");
    try {
      await api(
        path + "?visibility=" + (form.get("visibility") ?? "shared"),
        "POST",
        file,
      );
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      await reload();
      onChanged?.();
      setNotice(
        "Imagem registrada. Reenvios da mesma foto não criam outro anexo com a mesma visibilidade.",
      );
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy("");
    }
  }
  async function download(item: Attachment) {
    setBusy(item.id);
    setError("");
    try {
      await downloadAttachment(path + "/" + item.id, item.filename);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy("");
    }
  }
  async function remove(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!removing) return;
    const form = new FormData(event.currentTarget);
    setBusy("remove");
    setError("");
    setNotice("");
    try {
      await api(path + "/" + removing.id, "DELETE", {
        note: form.get("note") ?? "",
      });
      setRemoving(null);
      await reload();
      onChanged?.();
      setNotice("Imagem removida. A ação permanece na auditoria.");
      fileInput.current?.focus();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy("");
    }
  }
  return (
    <section
      className="order-section attachment-section"
      aria-labelledby={id + "-title"}
    >
      <h3 id={id + "-title"}>
        <ImagePlus size={18} aria-hidden="true" /> Fotos de evidência
      </h3>
      <p className="form-help">
        JPEG ou PNG, até 5 MiB e 16 megapixels. Até dez imagens por registro.
        Evite rostos, documentos e dados pessoais desnecessários. Os metadados
        da foto são removidos.
      </p>
      {error && <Notice error>{error}</Notice>}
      {notice && <Notice>{notice}</Notice>}
      {!data ? (
        error ? (
          <button
            type="button"
            className="button secondary"
            onClick={() =>
              void reload()
                .then(() => setError(""))
                .catch((error) => setError(errorMessage(error)))
            }
          >
            Recarregar anexos
          </button>
        ) : (
          <Loading />
        )
      ) : (
        <>
          {data.items.length ? (
            <ul className="attachment-list">
              {data.items.map((item) => (
                <li key={item.id}>
                  <div className="attachment-info">
                    <strong>{item.filename}</strong>
                    <small>
                      {Math.ceil(item.byte_size / 1024)} KiB ·{" "}
                      {item.uploader_name} · {dateTime(item.created_at)}
                    </small>
                    {item.visibility === "internal" && (
                      <span className="internal-label">
                        <ShieldCheck size={13} aria-hidden="true" /> Anexo
                        interno
                      </span>
                    )}
                  </div>
                  <div className="row-actions">
                    <button
                      type="button"
                      className="button secondary compact"
                      aria-label={"Baixar " + item.filename}
                      disabled={!!busy}
                      onClick={() => void download(item)}
                    >
                      <Download size={15} aria-hidden="true" /> Baixar
                    </button>
                    {item.can_remove && (
                      <button
                        type="button"
                        className="icon-button"
                        aria-label={"Remover " + item.filename}
                        disabled={!!busy}
                        onClick={() => setRemoving(item)}
                      >
                        <Trash2 size={16} aria-hidden="true" />
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="form-help">
              Nenhuma imagem disponível no seu acesso.
            </p>
          )}
          {removing && (
            <form onSubmit={remove} className="attachment-removal">
              <fieldset className="plain-fieldset" disabled={!!busy}>
                <p>
                  Remover <strong>{removing.filename}</strong>? O arquivo será
                  excluído; a ação permanece registrada.
                </p>
                {base.includes("/orders/") && (
                  <div className="field">
                    <label htmlFor={id + "-removal"}>Motivo da remoção</label>
                    <textarea
                      id={id + "-removal"}
                      name="note"
                      required
                      minLength={10}
                      maxLength={1000}
                      rows={2}
                      autoFocus
                    />
                  </div>
                )}
                <div className="row-actions">
                  <button
                    className="button secondary"
                    type="button"
                    onClick={() => setRemoving(null)}
                  >
                    Manter imagem
                  </button>
                  <button className="button primary">Confirmar remoção</button>
                </div>
              </fieldset>
            </form>
          )}
          {data.can_upload && (
            <form onSubmit={upload}>
              <fieldset className="plain-fieldset" disabled={!!busy}>
                <div className="field">
                  <label htmlFor={id + "-file"}>Selecionar foto</label>
                  <input
                    id={id + "-file"}
                    type="file"
                    accept="image/jpeg,image/png"
                    required
                    ref={fileInput}
                    onChange={(event) => {
                      setFile(event.target.files?.[0] ?? null);
                      setError("");
                    }}
                  />
                </div>
                {data.can_internal ? (
                  <div className="field">
                    <label htmlFor={id + "-visibility"}>
                      Quem pode acessar a imagem
                    </label>
                    <select
                      id={id + "-visibility"}
                      name="visibility"
                      defaultValue="shared"
                    >
                      <option value="shared">
                        Compartilhada com os participantes
                      </option>
                      <option value="internal">Somente equipe interna</option>
                    </select>
                  </div>
                ) : (
                  <p className="form-help">
                    {base.includes("/occurrences/")
                      ? "A foto deste relato fica disponível para você e para os responsáveis pela triagem. Ela não é compartilhada com outros solicitantes."
                      : "A foto será compartilhada com a equipe e os solicitantes vinculados a esta ordem."}
                  </p>
                )}
                <button className="button secondary" disabled={!!busy || !file}>
                  {busy === "upload" && (
                    <LoaderCircle
                      size={16}
                      className="spin"
                      aria-hidden="true"
                    />
                  )}{" "}
                  Enviar imagem
                </button>
              </fieldset>
            </form>
          )}
        </>
      )}
    </section>
  );
}
