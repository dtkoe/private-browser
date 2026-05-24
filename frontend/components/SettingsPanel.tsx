"use client";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";

interface UpdateInfo {
  current_version: string;
  latest_version: string | null;
  has_update: boolean;
  release_url: string | null;
}

export function SettingsPanel() {
  const [info, setInfo] = useState<{ version: string; name: string } | null>(null);
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    api.systemInfo().then(setInfo).catch(() => {});
  }, []);

  async function checkForUpdates() {
    setChecking(true);
    try {
      setUpdate(await api.checkUpdates());
    } catch {
      setUpdate(null);
    } finally {
      setChecking(false);
    }
  }

  return (
    <section className="flex-1 overflow-y-auto p-6">
      <h2 className="mb-4 text-xl font-semibold">Settings</h2>

      <div className="mb-4 rounded border border-bg-border bg-bg-elevated p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="text-xs uppercase text-muted">Version</div>
            <div className="mt-1 text-sm">{info?.version ?? "?"}</div>
          </div>
          <button
            onClick={checkForUpdates}
            disabled={checking}
            className="rounded border border-bg-border px-3 py-1 text-sm hover:bg-bg-border/40 disabled:opacity-50"
          >
            {checking ? "Checking…" : "Check for updates"}
          </button>
        </div>
        {update && (
          <div
            className={`rounded px-3 py-2 text-sm ${
              update.has_update
                ? "bg-green-900/30 text-green-300"
                : "bg-bg/40 text-muted"
            }`}
          >
            {update.has_update ? (
              <>
                <span className="font-semibold">Update available: v{update.latest_version}</span>
                {update.release_url && (
                  <>
                    {" — "}
                    <a className="underline" href={update.release_url} target="_blank" rel="noreferrer">
                      release notes
                    </a>
                  </>
                )}
              </>
            ) : update.latest_version ? (
              <>You're up to date (latest: v{update.latest_version}).</>
            ) : (
              <>Could not reach update server.</>
            )}
          </div>
        )}
      </div>

      <div className="rounded border border-bg-border bg-bg-elevated p-4">
        <div className="mb-3">
          <div className="text-xs uppercase text-muted">Theme</div>
          <div className="mt-1 text-sm">Dark (only theme in v1)</div>
        </div>
        <div>
          <div className="text-xs uppercase text-muted">Backend</div>
          <div className="mt-1 text-sm">http://127.0.0.1:8769</div>
        </div>
      </div>
    </section>
  );
}
