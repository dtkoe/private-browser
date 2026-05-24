import type { HealthCheckResult, Profile, Proxy, ProxyType } from "./types";

const BASE =
  typeof window !== "undefined" && (window as any).PB_API_BASE
    ? ((window as any).PB_API_BASE as string)
    : typeof window !== "undefined"
      ? window.location.origin
      : "http://127.0.0.1:8769";

let token: string | null = null;

export function setToken(t: string) {
  token = t;
  try {
    sessionStorage.setItem("pb_token", t);
  } catch {}
}

export function loadStoredToken(): string | null {
  if (token) return token;
  try {
    const t = sessionStorage.getItem("pb_token");
    if (t) {
      token = t;
      return t;
    }
  } catch {}
  if (typeof window !== "undefined") {
    const params = new URLSearchParams(window.location.search);
    const t = params.get("t");
    if (t) {
      setToken(t);
      return t;
    }
  }
  return null;
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(`HTTP ${status}: ${detail}`);
  }
}

async function req<T>(method: string, path: string, body?: any): Promise<T> {
  const t = loadStoredToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (t) headers["X-PB-Token"] = t;
  const r = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const j = await r.json();
      detail = j.detail ?? detail;
    } catch {}
    throw new ApiError(r.status, detail);
  }
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

export const api = {
  health: () => req<{ ok: boolean; unlocked: boolean }>("GET", "/healthz"),
  initialize: (password: string) => req<{ ok: boolean }>("POST", "/api/auth/initialize", { password }),
  unlock: (password: string) => req<{ ok: boolean }>("POST", "/api/auth/unlock", { password }),
  lock: () => req<{ ok: boolean }>("POST", "/api/auth/lock"),

  listProfiles: () => req<Profile[]>("GET", "/api/profiles"),
  createProfile: (data: { name: string; target_os?: "windows" | "macos" | "linux"; notes?: string }) =>
    req<Profile>("POST", "/api/profiles", data),
  updateProfile: (id: string, data: Partial<Pick<Profile, "name" | "notes" | "tags" | "color">>) =>
    req<Profile>("PATCH", `/api/profiles/${id}`, data),
  regenerateProfile: (id: string, target_os?: "windows" | "macos" | "linux") =>
    req<Profile>("POST", `/api/profiles/${id}/regenerate`, { target_os }),
  deleteProfile: (id: string) => req<void>("DELETE", `/api/profiles/${id}`),
  bindProxy: (id: string, proxy_id: string | null) =>
    req<Profile>("PATCH", `/api/profiles/${id}/proxy`, { proxy_id }),
  launchProfile: (id: string) =>
    req<{ status: string; pid: number; proxy: string | null }>("POST", `/api/profiles/${id}/launch`),
  stopProfile: (id: string) => req<{ status: string }>("POST", `/api/profiles/${id}/stop`),

  listProxies: () => req<Proxy[]>("GET", "/api/proxies"),
  createProxy: (data: {
    label: string;
    type: ProxyType;
    host: string;
    port: number;
    username?: string;
    password?: string;
  }) => req<Proxy>("POST", "/api/proxies", data),
  updateProxy: (id: string, data: Partial<Pick<Proxy, "label" | "notes" | "tags">>) =>
    req<Proxy>("PATCH", `/api/proxies/${id}`, data),
  deleteProxy: (id: string) => req<void>("DELETE", `/api/proxies/${id}`),
  checkProxy: (id: string) => req<HealthCheckResult>("POST", `/api/proxies/${id}/check`),
  batchImportProxies: (text: string, type_default: ProxyType = "http") =>
    req<{ added: number; ids: string[] }>("POST", "/api/proxies/batch", { text, type_default }),
};
