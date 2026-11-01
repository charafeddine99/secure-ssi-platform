/**
 * Single HTTP client for the web app.
 *
 * - Every request goes to the API Gateway; services are never called directly.
 * - Authentication: the gateway's HttpOnly session cookie (sent with
 *   `credentials: "include"` and the X-SSI-Client header the gateway requires
 *   for CSRF protection). An explicit `bearer` (e.g. the OID4VCI access token)
 *   is sent as an Authorization header instead. Requests that need a session
 *   fail *before* any network call when the user never signed in.
 * - Failures are typed so the UI can distinguish network/timeout/HTTP/schema
 *   errors and never present a failure as an empty result.
 */

import { hasSessionMarker } from "./tokenStore.ts";

const viteEnvironment = (import.meta as ImportMeta & {
  env?: { VITE_API_BASE_URL?: string; DEV?: boolean };
}).env;

// The Vite dev server proxies /api to the gateway (vite.config.ts), so development
// requests stay same-origin. Builds use VITE_API_BASE_URL.
export const GATEWAY_BASE_URL: string =
  (viteEnvironment?.VITE_API_BASE_URL || (viteEnvironment?.DEV ? "" : "http://127.0.0.1:8000")).replace(/\/+$/, "");

export const SESSION_EXPIRED_EVENT = "ssi:session-expired";
export const DEFAULT_TIMEOUT_MS = 15_000;

export type ApiErrorKind =
  | "network"
  | "timeout"
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "validation"
  | "rate_limited"
  | "server"
  | "unavailable"
  | "schema"
  | "http";

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;
  readonly code: string | null;
  /** Low-level transport message (e.g. "Failed to fetch"); never shown as the primary message. */
  readonly transportDetail: string | null;

  constructor(kind: ApiErrorKind, message: string, status: number | null = null, code: string | null = null, transportDetail: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.code = code;
    this.transportDetail = transportDetail;
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

function kindForStatus(status: number): ApiErrorKind {
  if (status === 401) return "unauthorized";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 400 || status === 422) return "validation";
  if (status === 429) return "rate_limited";
  if (status === 502 || status === 503 || status === 504) return "unavailable";
  if (status >= 500) return "server";
  return "http";
}

const SAFE_DEFAULT_MESSAGES: Record<ApiErrorKind, string> = {
  network: "The service could not be reached. Check your connection and try again.",
  timeout: "The request took too long and was stopped. Try again.",
  unauthorized: "Your session has ended. Sign in again to continue.",
  forbidden: "Your account is not allowed to perform this action.",
  not_found: "The requested record was not found or is not available to your account.",
  conflict: "The record changed or the action is no longer allowed in its current state.",
  validation: "Some information was not accepted. Review the form and try again.",
  rate_limited: "Too many requests. Wait a moment and try again.",
  server: "The service reported an internal error. No success was recorded.",
  unavailable: "A required service is currently unavailable. No success was recorded.",
  schema: "The service returned an unexpected response. The result was not trusted.",
  http: "The request could not be completed.",
};

/** Extract a short, human-readable message from common backend error envelopes. */
export function messageFromBody(body: unknown): { message: string | null; code: string | null } {
  if (!body || typeof body !== "object") return { message: null, code: null };
  const record = body as Record<string, unknown>;
  const nested = record.error && typeof record.error === "object" ? record.error as Record<string, unknown> : null;
  const candidates = [
    typeof record.detail === "string" ? record.detail : null,
    typeof record.message === "string" ? record.message : null,
    nested && typeof nested.message === "string" ? nested.message : null,
    typeof record.error_description === "string" ? record.error_description : null,
  ];
  const code =
    (nested && typeof nested.code === "string" ? nested.code : null)
    ?? (typeof record.code === "string" ? record.code : null)
    ?? (typeof record.error === "string" ? record.error : null);
  const message = candidates.find((item): item is string => Boolean(item && item.trim())) ?? null;
  // Cap length so raw stack traces or payload echoes never flood the UI.
  return { message: message ? message.slice(0, 300) : null, code };
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  form?: URLSearchParams;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  timeoutMs?: number;
  /** Do not broadcast the session-expired event (used by the session probe). */
  silentUnauthorized?: boolean;
  /**
   * "required" (default): use the session; fail before any request when not signed in.
   * "optional": use it when present. "none": no Authorization header.
   */
  auth?: "required" | "optional" | "none";
  /** Explicit bearer token (e.g. the OID4VCI access token or a token being validated). */
  bearer?: string;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json", "X-SSI-Client": "web", ...(options.headers ?? {}) };
  let body: BodyInit | undefined;
  if (options.form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    body = options.form;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }
  const authMode = options.auth ?? "required";
  if (!headers.Authorization && authMode !== "none") {
    if (options.bearer) {
      headers.Authorization = `Bearer ${options.bearer}`;
    } else if (authMode === "required" && !hasSessionMarker()) {
      throw new ApiError("unauthorized", "Sign in to continue. No request was sent.");
    }
  }

  const timeout = AbortSignal.timeout(options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const signal = options.signal ? AbortSignal.any([options.signal, timeout]) : timeout;

  let response: Response;
  try {
    response = await fetch(`${GATEWAY_BASE_URL}${path}`, {
      method,
      headers,
      body,
      signal,
      credentials: "include",
    });
  } catch (cause) {
    if (options.signal?.aborted) throw cause;
    if (timeout.aborted || (cause instanceof DOMException && cause.name === "TimeoutError")) {
      throw new ApiError("timeout", SAFE_DEFAULT_MESSAGES.timeout);
    }
    const detail = cause instanceof Error ? cause.message.slice(0, 200) : null;
    throw new ApiError("network", SAFE_DEFAULT_MESSAGES.network, null, null, detail);
  }

  const text = await response.text();
  let parsed: unknown = null;
  if (text) {
    try {
      parsed = JSON.parse(text);
    } catch {
      parsed = null;
    }
  }

  if (!response.ok) {
    const kind = kindForStatus(response.status);
    const { message, code } = messageFromBody(parsed);
    if (kind === "unauthorized" && !options.silentUnauthorized && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent(SESSION_EXPIRED_EVENT));
    }
    const safeMessage = kind === "server" || kind === "unavailable"
      ? SAFE_DEFAULT_MESSAGES[kind]
      : message ?? SAFE_DEFAULT_MESSAGES[kind];
    throw new ApiError(kind, safeMessage, response.status, code);
  }

  if (text && parsed === null) {
    throw new ApiError("schema", SAFE_DEFAULT_MESSAGES.schema, response.status);
  }
  return parsed as T;
}

/** Throw a schema error when a response does not have the expected shape. */
export function assertShape(condition: unknown, what: string): asserts condition {
  if (!condition) throw new ApiError("schema", `The service returned an invalid ${what}.`);
}

export function describeError(error: unknown): string {
  if (isApiError(error)) return error.message;
  if (error instanceof Error && error.message) return error.message.slice(0, 300);
  return SAFE_DEFAULT_MESSAGES.http;
}
