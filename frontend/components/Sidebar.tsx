"use client";
import { useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { Profile } from "@/lib/types";

interface Props {
  profiles: Profile[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreated: () => void;
}

export function Sidebar({ profiles, selectedId, onSelect, onCreated }: Props) {
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [targetOs, setTargetOs] = useState<"" | "windows" | "macos" | "linux">("");
  const [err, setErr] = useState<string | null>(null);

  async function create() {
    setErr(null);
    try {
      await api.createProfile({
        name: name || `Profile ${Date.now()}`,
        target_os: targetOs || undefined,
      });
      setName("");
      setTargetOs("");
      setCreating(false);
      onCreated();
    } catch (e: any) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    }
  }

  return (
    <aside className="flex w-72 flex-col border-r border-bg-border bg-bg-elevated">
      <div className="flex items-center justify-between border-b border-bg-border p-3">
        <span className="text-xs uppercase tracking-wide text-muted">
          Profiles ({profiles.length})
        </span>
        <button
          className="rounded bg-accent px-2 py-0.5 text-xs text-white hover:bg-accent-hover"
          onClick={() => setCreating(true)}
        >
          + New
        </button>
      </div>
      {creating && (
        <div className="border-b border-bg-border p-3">
          <input
            autoFocus
            placeholder="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mb-2 w-full rounded border border-bg-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
          />
          <select
            value={targetOs}
            onChange={(e) => setTargetOs(e.target.value as any)}
            className="mb-2 w-full rounded border border-bg-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
          >
            <option value="">Random OS</option>
            <option value="windows">Windows</option>
            <option value="macos">macOS</option>
            <option value="linux">Linux</option>
          </select>
          {err && <div className="mb-2 text-xs text-red-400">{err}</div>}
          <div className="flex gap-2">
            <button className="flex-1 rounded bg-accent px-2 py-1 text-xs text-white" onClick={create}>
              Create
            </button>
            <button
              className="flex-1 rounded border border-bg-border px-2 py-1 text-xs"
              onClick={() => setCreating(false)}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      <ul className="flex-1 overflow-y-auto">
        {profiles.map((p) => (
          <li key={p.id}>
            <button
              onClick={() => onSelect(p.id)}
              className={`flex w-full items-center gap-2 border-b border-bg-border/50 px-3 py-2 text-left text-sm transition-colors ${
                selectedId === p.id ? "bg-accent/20" : "hover:bg-bg-border/40"
              }`}
            >
              <span
                className={`h-2 w-2 rounded-full ${
                  p.status === "running"
                    ? "bg-green-400"
                    : p.status === "error"
                      ? "bg-red-400"
                      : "bg-muted/40"
                }`}
              />
              <span className="flex-1 truncate">{p.name}</span>
              <span className="text-xs text-muted">{p.fingerprint?._os ?? "?"}</span>
            </button>
          </li>
        ))}
        {profiles.length === 0 && (
          <li className="p-4 text-center text-sm text-muted">No profiles yet</li>
        )}
      </ul>
    </aside>
  );
}
