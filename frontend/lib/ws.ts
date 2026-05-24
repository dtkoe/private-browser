import { loadStoredToken } from "./api";

export type AppEvent =
  | { event: "profile_status_changed"; profile_id: string; status: string }
  | { event: string; [k: string]: unknown };

function resolveWsBase(): string {
  if (typeof window === "undefined") return "ws://127.0.0.1:8769";
  const inj = (window as any).PB_API_BASE;
  const base = (typeof inj === "string" && inj) ? inj : (() => {
    const p = new URLSearchParams(window.location.search).get("api");
    return p ? `http://127.0.0.1:${p}` : window.location.origin;
  })();
  return base.replace(/^http/, "ws");
}

export function subscribeEvents(onEvent: (e: AppEvent) => void): () => void {
  if (typeof window === "undefined") return () => {};
  let ws: WebSocket | null = null;
  let closed = false;
  let retry = 0;

  function connect() {
    if (closed) return;
    const t = loadStoredToken();
    if (!t) {
      setTimeout(connect, 500);
      return;
    }
    const url = `${resolveWsBase()}/ws?t=${encodeURIComponent(t)}`;
    ws = new WebSocket(url);
    ws.onmessage = (msg) => {
      try {
        onEvent(JSON.parse(msg.data));
      } catch {}
    };
    ws.onclose = () => {
      if (closed) return;
      retry = Math.min(retry + 1, 6);
      setTimeout(connect, 200 * 2 ** retry);
    };
    ws.onopen = () => {
      retry = 0;
    };
  }

  connect();

  return () => {
    closed = true;
    try {
      ws?.close();
    } catch {}
  };
}
