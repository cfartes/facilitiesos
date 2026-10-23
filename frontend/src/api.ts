export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<Response> {
  const csrf =
    document.cookie
      .split("; ")
      .find((c) => c.startsWith("facilities_csrf="))
      ?.split("=")[1] ?? "";
  const response = await fetch(`/api/v1${path}`, {
    signal,
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": body instanceof File ? body.type : "application/json",
      ...(body instanceof File
        ? { "X-File-Name": encodeURIComponent(body.name) }
        : {}),
      ...(method !== "GET" ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {}),
    },
    body:
      body === undefined
        ? undefined
        : body instanceof File
          ? body
          : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if (response.status === 401 && path !== "/auth/login")
      window.dispatchEvent(new Event("session-expired"));
    throw new ApiError(
      response.status,
      typeof data.detail === "string"
        ? data.detail
        : "Não foi possível concluir a operação.",
    );
  }
  return response;
}

export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await request(path, method, body, signal);
  return response.status === 204 ? (undefined as T) : response.json();
}

export async function downloadAttachment(path: string, filename: string) {
  const response = await request(path);
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
