"use client";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";

interface Props {
  onUnlocked: () => void;
}

export function LoginScreen({ onUnlocked }: Props) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [needsInit, setNeedsInit] = useState<boolean | null>(null);

  useEffect(() => {
    (async () => {
      try {
        await api.unlock("__probe_never_matches__");
      } catch (e) {
        if (e instanceof ApiError) {
          setNeedsInit(e.status === 412);
        } else {
          setNeedsInit(false);
        }
      }
    })();
  }, []);

  async function handle() {
    setError(null);
    setBusy(true);
    try {
      if (needsInit) {
        if (password.length < 12) throw new Error("password must be at least 12 characters");
        if (password !== confirm) throw new Error("passwords don't match");
        await api.initialize(password);
      }
      await api.unlock(password);
      onUnlocked();
    } catch (e: any) {
      setError(e?.detail ?? e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  if (needsInit === null) {
    return <div className="flex h-screen items-center justify-center text-muted">Loading…</div>;
  }

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="w-[400px] rounded-lg border border-bg-border bg-bg-elevated p-8 shadow-2xl">
        <h1 className="mb-2 text-2xl font-semibold">Private Browser</h1>
        <p className="mb-6 text-sm text-muted">
          {needsInit
            ? "Create a master password (≥12 chars). This encrypts your data; there is no recovery if lost."
            : "Enter your master password to unlock."}
        </p>
        <input
          type="password"
          autoFocus
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handle();
          }}
          placeholder="Master password"
          className="mb-3 w-full rounded border border-bg-border bg-bg px-3 py-2 outline-none focus:border-accent"
        />
        {needsInit && (
          <input
            type="password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handle();
            }}
            placeholder="Confirm password"
            className="mb-3 w-full rounded border border-bg-border bg-bg px-3 py-2 outline-none focus:border-accent"
          />
        )}
        {error && <div className="mb-3 rounded bg-red-900/40 px-3 py-2 text-sm text-red-300">{error}</div>}
        <button
          onClick={handle}
          disabled={busy}
          className="w-full rounded bg-accent px-3 py-2 font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {busy ? "Working…" : needsInit ? "Create & unlock" : "Unlock"}
        </button>
      </div>
    </div>
  );
}
