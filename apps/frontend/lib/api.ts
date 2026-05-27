/**
 * Typed fetch client for the Yurika Django backend.
 *
 * Default base: http://localhost:8000/api in the browser. Server-side
 * (SSR) calls use the internal docker hostname http://django:8000/api
 * via INTERNAL_API_BASE_URL.
 */

const BROWSER_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

const SERVER_BASE_URL =
  process.env.INTERNAL_API_BASE_URL || "http://django:8000/api";

function baseUrl(): string {
  return typeof window === "undefined" ? SERVER_BASE_URL : BROWSER_BASE_URL;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public data: unknown,
  ) {
    super(`API ${status}`);
    this.name = "ApiError";
  }
}

export function detailMessage(data: unknown): string {
  if (!data || typeof data !== "object") return "Request failed";
  const d = data as Record<string, unknown>;
  if (typeof d.detail === "string") return d.detail;
  if (Array.isArray(d.detail)) return String(d.detail[0]);
  const firstKey = Object.keys(d)[0];
  if (!firstKey) return "Request failed";
  const val = d[firstKey];
  if (Array.isArray(val)) return `${firstKey}: ${val[0]}`;
  if (typeof val === "string") return `${firstKey}: ${val}`;
  return "Request failed";
}

class ApiClient {
  private accessToken: string | null = null;

  setToken(token: string | null): void {
    this.accessToken = token;
  }

  private async request<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };
    if (this.accessToken) {
      headers.Authorization = `Bearer ${this.accessToken}`;
    }

    const res = await fetch(`${baseUrl()}${path}`, {
      ...options,
      headers,
      cache: "no-store",
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new ApiError(res.status, errorData);
    }

    if (res.status === 204) return undefined as T;
    return res.json();
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  post<T>(path: string, data?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      body: data !== undefined ? JSON.stringify(data) : undefined,
    });
  }

  patch<T>(path: string, data: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "DELETE" });
  }
}

export const api = new ApiClient();
