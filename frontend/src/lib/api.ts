import type { SessionData, UserView } from "./api-types";

let csrfToken: string | null = null;
let csrfTokenRequest: Promise<string> | null = null;
let csrfGeneration = 0;

function cacheCsrfToken(value: unknown) {
  if (
    typeof value === "object" &&
    value !== null &&
    "csrf_token" in value &&
    typeof value.csrf_token === "string"
  ) {
    csrfToken = value.csrf_token;
  }
}

function clearCsrfToken() {
  csrfToken = null;
  csrfGeneration += 1;
  csrfTokenRequest = null;
}

async function csrfForWrite(): Promise<string> {
  if (csrfToken) return csrfToken;
  if (!csrfTokenRequest) {
    const generation = csrfGeneration;
    const request = read<{ csrf_token: string }>("/auth/csrf").then((result) => {
      if (generation === csrfGeneration) csrfToken = result.csrf_token;
      return result.csrf_token;
    });
    csrfTokenRequest = request;
    const clearRequest = () => {
      if (csrfTokenRequest === request) csrfTokenRequest = null;
    };
    void request.then(clearRequest, clearRequest);
  }
  return csrfTokenRequest;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(code);
  }
}

export async function read<T>(path: string): Promise<T> {
  const generation = csrfGeneration;
  const response = await fetch(`/api/v1${path}`, {
    credentials: "include",
    cache: "no-store",
  });
  const body = await response.json();
  if (!response.ok) {
    if (response.status === 401 && generation === csrfGeneration)
      clearCsrfToken();
    throw new ApiError(response.status, body.error?.code ?? "REQUEST_FAILED");
  }
  if (path === "/auth/session" && generation === csrfGeneration)
    cacheCsrfToken(body.data);
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
  const isRegistration = path === "/auth/register";
  const isLogin = path === "/auth/login";
  const isLogout = path === "/auth/logout";
  if (isRegistration || isLogin) clearCsrfToken();
  const token = await csrfForWrite();
  const response = await fetch(`/api/v1${path}`, {
    method: options.method ?? "POST",
    credentials: "include",
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      "X-CSRF-Token": token,
      ...(options.idempotencyKey
        ? { "Idempotency-Key": options.idempotencyKey }
        : {}),
    },
    body: JSON.stringify(payload),
  });
  if (response.status === 204) {
    if (isLogout) clearCsrfToken();
    return undefined as T;
  }
  const body = await response.json();
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) clearCsrfToken();
    throw new ApiError(response.status, body.error?.code ?? "REQUEST_FAILED");
  }
  if (isRegistration || isLogout) clearCsrfToken();
  else if (isLogin) cacheCsrfToken(body.data);
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
