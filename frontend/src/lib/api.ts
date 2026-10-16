import type { SessionData, UserView } from "./api-types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

export async function read<T>(path: string): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    credentials: "include",
    cache: "no-store",
  });
  const body = await response.json();
  if (!response.ok)
    throw new ApiError(response.status, body.error?.code ?? "REQUEST_FAILED");
  return body.data as T;
}

export async function mutate<T>(path: string, payload: object): Promise<T> {
  return write<T>(path, payload);
}

export async function write<T>(
  path: string,
  payload: object,
  options: {
    method?: "POST" | "PATCH" | "DELETE";
    idempotencyKey?: string;
  } = {},
): Promise<T> {
  const bootstrap = await read<{ csrf_token: string }>("/auth/csrf");
  const response = await fetch(`/api/v1${path}`, {
    method: options.method ?? "POST",
    credentials: "include",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": bootstrap.csrf_token,
      ...(options.idempotencyKey
        ? { "Idempotency-Key": options.idempotencyKey }
        : {}),
    },
    body: JSON.stringify(payload),
  });
  if (response.status === 204) return undefined as T;
  const body = await response.json();
  if (!response.ok)
    throw new ApiError(response.status, body.error?.code ?? "REQUEST_FAILED");
  return body.data as T;
}

export async function readPage<T>(path: string): Promise<{
  data: T;
  meta: { request_id: string; next_cursor?: string | null };
}> {
  const response = await fetch(`/api/v1${path}`, {
    credentials: "include",
    cache: "no-store",
  });
  const body = await response.json();
  if (!response.ok)
    throw new ApiError(response.status, body.error?.code ?? "REQUEST_FAILED");
  return body;
}

export type { SessionData, UserView };
