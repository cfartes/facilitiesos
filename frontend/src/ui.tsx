import { useEffect, useRef, type ReactNode } from "react";
import { Check, CircleHelp, LoaderCircle, X } from "lucide-react";

export const errorMessage = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Não foi possível concluir a operação.";

export function Notice({
  children,
  error = false,
}: {
  children: ReactNode;
  error?: boolean;
}) {
  return (
    <div
      className={`notice ${error ? "error" : "success"}`}
      role={error ? "alert" : "status"}
    >
      {error ? (
        <CircleHelp size={18} aria-hidden="true" />
      ) : (
        <Check size={18} aria-hidden="true" />
      )}
      <span>{children}</span>
    </div>
  );
}

export function Loading() {
  return (
    <p className="loading" role="status">
      <LoaderCircle className="spin" size={20} /> Carregando…
    </p>
  );
}

export function Modal({
  title,
  children,
  onClose,
  busy = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  busy?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    const previous = document.activeElement;
    dialog.showModal();
    dialog
      .querySelector<HTMLElement>(
        "input:not([disabled]),select:not([disabled]),textarea:not([disabled])",
      )
      ?.focus();
    return () => {
      dialog.close();
      if (previous instanceof HTMLElement && previous.isConnected)
        previous.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className="modal"
      aria-labelledby="modal-title"
      onCancel={(event) => {
        event.preventDefault();
        if (!busy) onClose();
      }}
    >
      <header>
        <h2 id="modal-title">{title}</h2>
        <button
          type="button"
          className="icon-button"
          aria-label="Fechar diálogo"
          disabled={busy}
          onClick={onClose}
        >
          <X size={19} />
        </button>
      </header>
      <div className="modal-body">{children}</div>
    </dialog>
  );
}
