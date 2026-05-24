"use client";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { Profile, Proxy } from "@/lib/types";

interface Props {
  profile: Profile | null;
  onChanged: () => void;
  onDeleted: () => void;
}

export function ProfileDetail({ profile, onChanged, onDeleted }: Props) {
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.listProxies().then(setProxies).catch(() => {});
  }, [profile?.id]);

  if (!profile) {
    return (
      <section className="flex flex-1 items-center justify-center text-muted">
        Select a profile from the sidebar.
      </section>
    );
  }

  async function action(fn: () => Promise<any>) {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      onChanged();
    } catch (e: any) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }

  const fp = profile.fingerprint || {};

  return (
    <section className="flex-1 overflow-y-auto p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">{profile.name}</h2>
          <p className="text-xs text-muted">
            {profile.status} · OS: {fp._os ?? "?"} · UA: {(fp["navigator.userAgent"] ?? "").slice(0, 60)}…
          </p>
        </div>
        <div className="flex gap-2">
          {profile.status === "running" ? (
            <button
              disabled={busy}
              onClick={() => action(() => api.stopProfile(profile.id))}
              className="rounded bg-yellow-700 px-3 py-1 text-sm text-white hover:bg-yellow-600 disabled:opacity-50"
            >
              Stop
            </button>
          ) : (
            <button
              disabled={busy}
              onClick={() => action(() => api.launchProfile(profile.id))}
              className="rounded bg-green-700 px-3 py-1 text-sm text-white hover:bg-green-600 disabled:opacity-50"
            >
              ▶ Launch
            </button>
          )}
          <button
            disabled={busy}
            onClick={() => action(() => api.regenerateProfile(profile.id))}
            className="rounded border border-bg-border px-3 py-1 text-sm hover:bg-bg-border/40 disabled:opacity-50"
          >
            Regenerate fp
          </button>
          <button
            disabled={busy}
            onClick={() => {
              if (confirm(`Delete profile "${profile.name}"? This removes its browser data too.`)) {
                action(() => api.deleteProfile(profile.id).then(onDeleted));
              }
            }}
            className="rounded border border-red-800 px-3 py-1 text-sm text-red-400 hover:bg-red-900/30 disabled:opacity-50"
          >
            Delete
          </button>
        </div>
      </div>

      {err && <div className="mb-4 rounded bg-red-900/40 px-3 py-2 text-sm text-red-300">{err}</div>}

      <div className="mb-6 rounded border border-bg-border bg-bg-elevated p-4">
        <div className="mb-2 text-xs uppercase text-muted">Proxy</div>
        <select
          value={profile.proxy_id ?? ""}
          onChange={(e) => action(() => api.bindProxy(profile.id, e.target.value || null))}
          className="w-full rounded border border-bg-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
        >
          <option value="">No proxy (WebRTC blocked)</option>
          {proxies.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label} — {p.type}://{p.host}:{p.port}
              {p.last_check_ok ? " ✓" : p.last_checked_at ? " ✗" : ""}
            </option>
          ))}
        </select>
      </div>

      <details className="rounded border border-bg-border bg-bg-elevated p-4">
        <summary className="cursor-pointer text-xs uppercase text-muted">Fingerprint (raw)</summary>
        <pre className="mt-3 overflow-x-auto text-xs">{JSON.stringify(fp, null, 2)}</pre>
      </details>
    </section>
  );
}
