export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
): Promise<T> {
  const csrf =
    document.cookie
      .split("; ")
      .find((c) => c.startsWith("facilities_csrf="))
      ?.split("=")[1] ?? "";
  const response = await fetch(`/api/v1${path}`, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(method !== "GET" ? { "X-CSRF-Token": decodeURIComponent(csrf) } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
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
  return response.status === 204 ? (undefined as T) : response.json();
}
