import type { HealthCheckResult, Profile, Proxy, ProxyType } from "./types";

function resolveBase(): string {
  if (typeof window === "undefined") return "http://127.0.0.1:8769";
  // 1) Explicit override via shell injection
  const inj = (window as any).PB_API_BASE;
  if (typeof inj === "string" && inj) return inj;
  // 2) ?api=PORT in URL (set by pywebview shell)
  try {
    const params = new URLSearchParams(window.location.search);
    const apiPort = params.get("api");
    if (apiPort) return `http://127.0.0.1:${apiPort}`;
  } catch {}
  // 3) Same-origin (dev: `next dev` on backend port)
  return window.location.origin;
}

let token: string | null = null;

export function setToken(t: string) {
  token = t;
  try {
    sessionStorage.setItem("pb_token", t);
  } catch {}
}

export function loadStoredToken(): string | null {
  // URL ?t=... wins over sessionStorage so a backend restart (= new token) takes effect
  // without forcing the user to clear browser storage manually.
  if (typeof window !== "undefined") {
    try {
      const params = new URLSearchParams(window.location.search);
      const t = params.get("t");
      if (t) {
        setToken(t);
        return t;
      }
    } catch {}
  }
  if (token) return token;
  try {
    const t = sessionStorage.getItem("pb_token");
    if (t) {
      token = t;
      return t;
    }
  } catch {}
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
  const r = await fetch(`${resolveBase()}${path}`, {
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
  createProfile: (data: {
    name: string;
    target_os?: "windows" | "macos" | "linux";
    notes?: string;
    locale?: string;
    timezone?: string;
  }) => req<Profile>("POST", "/api/profiles", data),
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

  // M5: export / import / clone / bulk
  exportProfile: async (id: string, password: string, include_browser_data = true) => {
    const t = loadStoredToken();
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (t) headers["X-PB-Token"] = t;
    const r = await fetch(`${resolveBase()}/api/profiles/${id}/export`, {
      method: "POST",
      headers,
      body: JSON.stringify({ password, include_browser_data }),
    });
    if (!r.ok) {
      let detail = r.statusText;
      try {
        const j = await r.json();
        detail = j.detail ?? detail;
      } catch {}
      throw new ApiError(r.status, detail);
    }
    return r.blob();
  },
  importProfile: async (password: string, file: File) => {
    const t = loadStoredToken();
    const headers: Record<string, string> = {};
    if (t) headers["X-PB-Token"] = t;
    const fd = new FormData();
    fd.append("password", password);
    fd.append("file", file);
    const r = await fetch(`${resolveBase()}/api/import`, { method: "POST", headers, body: fd });
    if (!r.ok) {
      let detail = r.statusText;
      try {
        const j = await r.json();
        detail = j.detail ?? detail;
      } catch {}
      throw new ApiError(r.status, detail);
    }
    return r.json() as Promise<{ id: string; name: string }>;
  },
  cloneProfile: (id: string, new_name?: string, include_cookies = true) =>
    req<Profile>("POST", `/api/profiles/${id}/clone`, { new_name, include_cookies }),
  bulkDeleteProfiles: (ids: string[]) =>
    req<{ deleted: string[] }>("POST", "/api/profiles/bulk/delete", { ids }),

  // Extensions
  listExtensions: (pid: string) =>
    req<Array<{ id: string; name: string; version: string; filename: string }>>(
      "GET",
      `/api/profiles/${pid}/extensions`,
    ),
  installExtension: async (pid: string, file: File) => {
    const t = loadStoredToken();
    const headers: Record<string, string> = {};
    if (t) headers["X-PB-Token"] = t;
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(`${resolveBase()}/api/profiles/${pid}/extensions`, {
      method: "POST",
      headers,
      body: fd,
    });
    if (!r.ok) {
      let detail = r.statusText;
      try {
        const j = await r.json();
        detail = j.detail ?? detail;
      } catch {}
      throw new ApiError(r.status, detail);
    }
    return r.json();
  },
  removeExtension: (pid: string, addon_id: string) =>
    req<void>("DELETE", `/api/profiles/${pid}/extensions/${encodeURIComponent(addon_id)}`),

  // System
  systemInfo: () => req<{ version: string; name: string }>("GET", "/api/system/info"),
  checkUpdates: () =>
    req<{ current_version: string; latest_version: string | null; has_update: boolean; release_url: string | null }>(
      "GET",
      "/api/system/check-updates",
    ),
};
