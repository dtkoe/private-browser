"use client";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { Proxy, ProxyType } from "@/lib/types";

export function ProxyPanel() {
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [form, setForm] = useState<{ label: string; type: ProxyType; host: string; port: string }>({
    label: "",
    type: "http",
    host: "",
    port: "",
  });
  const [batchText, setBatchText] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    try {
      setProxies(await api.listProxies());
    } catch (e: any) {
      setErr(String(e));
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function add() {
    setErr(null);
    setBusy(true);
    try {
      await api.createProxy({
        label: form.label || `${form.host}:${form.port}`,
        type: form.type,
        host: form.host,
        port: parseInt(form.port, 10),
      });
      setForm({ label: "", type: "http", host: "", port: "" });
      refresh();
    } catch (e: any) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function batch() {
    setErr(null);
    setBusy(true);
    try {
      const r = await api.batchImportProxies(batchText, "http");
      setBatchText("");
      refresh();
      alert(`Added ${r.added}`);
    } catch (e: any) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function check(id: string) {
    setBusy(true);
    try {
      await api.checkProxy(id);
      refresh();
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("Delete proxy?")) return;
    setBusy(true);
    try {
      await api.deleteProxy(id);
      refresh();
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex-1 overflow-y-auto p-6">
      <h2 className="mb-4 text-xl font-semibold">Proxies ({proxies.length})</h2>

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded border border-bg-border bg-bg-elevated p-4">
          <div className="mb-3 text-xs uppercase text-muted">Add one</div>
          <input
            placeholder="Label (optional)"
            value={form.label}
            onChange={(e) => setForm({ ...form, label: e.target.value })}
            className="mb-2 w-full rounded border border-bg-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
          />
          <div className="mb-2 flex gap-2">
            <select
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value as ProxyType })}
              className="rounded border border-bg-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
            >
              <option value="http">HTTP</option>
              <option value="https">HTTPS</option>
              <option value="socks5">SOCKS5</option>
            </select>
            <input
              placeholder="host"
              value={form.host}
              onChange={(e) => setForm({ ...form, host: e.target.value })}
              className="flex-1 rounded border border-bg-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
            />
            <input
              placeholder="port"
              value={form.port}
              onChange={(e) => setForm({ ...form, port: e.target.value })}
              className="w-20 rounded border border-bg-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
            />
          </div>
          <button
            disabled={busy || !form.host || !form.port}
            onClick={add}
            className="rounded bg-accent px-3 py-1 text-sm text-white hover:bg-accent-hover disabled:opacity-50"
          >
            Add proxy
          </button>
        </div>

        <div className="rounded border border-bg-border bg-bg-elevated p-4">
          <div className="mb-3 text-xs uppercase text-muted">
            Batch import (one per line: host:port or host:port:user:pass)
          </div>
          <textarea
            value={batchText}
            onChange={(e) => setBatchText(e.target.value)}
            rows={4}
            className="mb-2 w-full rounded border border-bg-border bg-bg px-2 py-1 font-mono text-xs outline-none focus:border-accent"
          />
          <button
            disabled={busy || !batchText.trim()}
            onClick={batch}
            className="rounded bg-accent px-3 py-1 text-sm text-white hover:bg-accent-hover disabled:opacity-50"
          >
            Import
          </button>
        </div>
      </div>

      {err && <div className="mb-4 rounded bg-red-900/40 px-3 py-2 text-sm text-red-300">{err}</div>}

      <table className="w-full overflow-hidden rounded border border-bg-border">
        <thead className="bg-bg-elevated text-left text-xs uppercase text-muted">
          <tr>
            <th className="px-3 py-2">Label</th>
            <th className="px-3 py-2">Endpoint</th>
            <th className="px-3 py-2">Last check</th>
            <th className="px-3 py-2">IP / Geo</th>
            <th className="px-3 py-2"></th>
          </tr>
        </thead>
        <tbody>
          {proxies.map((p) => (
            <tr key={p.id} className="border-t border-bg-border/50">
              <td className="px-3 py-2 text-sm">
                <EditableLabel
                  value={p.label}
                  onSave={async (v) => {
                    try {
                      await api.updateProxy(p.id, { label: v });
                      refresh();
                    } catch (e: any) {
                      setErr(e?.detail ?? String(e));
                    }
                  }}
                />
              </td>
              <td className="px-3 py-2 text-xs text-muted">
                {p.type}://{p.host}:{p.port}
              </td>
              <td className="px-3 py-2 text-xs">
                {p.last_checked_at ? (
                  <span className={p.last_check_ok ? "text-green-400" : "text-red-400"}>
                    {p.last_check_ok ? "OK" : "FAIL"} · {p.last_latency_ms}ms
                  </span>
                ) : (
                  <span className="text-muted">never</span>
                )}
              </td>
              <td className="px-3 py-2 text-xs text-muted">
                {p.last_ip ? `${p.last_ip} ${p.last_country ?? ""}` : "-"}
              </td>
              <td className="px-3 py-2 text-right">
                <button
                  onClick={() => check(p.id)}
                  disabled={busy}
                  className="mr-2 rounded border border-bg-border px-2 py-0.5 text-xs hover:bg-bg-border/40 disabled:opacity-50"
                >
                  Check
                </button>
                <button
                  onClick={() => remove(p.id)}
                  disabled={busy}
                  className="rounded border border-red-800 px-2 py-0.5 text-xs text-red-400 hover:bg-red-900/30 disabled:opacity-50"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
          {proxies.length === 0 && (
            <tr>
              <td colSpan={5} className="px-3 py-6 text-center text-sm text-muted">
                No proxies. Add some above.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}


function EditableLabel({ value, onSave }: { value: string; onSave: (v: string) => Promise<void> }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);

  if (!editing) {
    return (
      <button
        onClick={() => {
          setDraft(value);
          setEditing(true);
        }}
        className="rounded px-1 text-left hover:bg-bg-border/40"
        title="Click to rename"
      >
        {value}
      </button>
    );
  }
  return (
    <input
      autoFocus
      value={draft}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={async () => {
        setEditing(false);
        if (draft.trim() && draft.trim() !== value) await onSave(draft.trim());
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        else if (e.key === "Escape") {
          setDraft(value);
          setEditing(false);
        }
      }}
      className="w-full rounded border border-accent bg-bg px-1 py-0.5 text-sm outline-none"
    />
  );
}
