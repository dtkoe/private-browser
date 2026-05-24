"use client";
import { useEffect, useState } from "react";

import { LoginScreen } from "@/components/LoginScreen";
import { ProfileDetail } from "@/components/ProfileDetail";
import { ProxyPanel } from "@/components/ProxyPanel";
import { SettingsPanel } from "@/components/SettingsPanel";
import { Sidebar } from "@/components/Sidebar";
import { api } from "@/lib/api";
import type { Profile } from "@/lib/types";
import { subscribeEvents } from "@/lib/ws";

type Tab = "profiles" | "proxies" | "settings";

export default function Page() {
  const [unlocked, setUnlocked] = useState(false);
  const [tab, setTab] = useState<Tab>("profiles");
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    (async () => {
      try {
        const h = await api.health();
        setUnlocked(h.unlocked);
      } catch {}
    })();
  }, []);

  async function refreshProfiles() {
    try {
      const list = await api.listProfiles();
      setProfiles(list);
    } catch {}
  }

  useEffect(() => {
    if (unlocked) refreshProfiles();
  }, [unlocked]);

  useEffect(() => {
    if (!unlocked) return;
    return subscribeEvents((e) => {
      if (
        e.event === "profile_status_changed" ||
        e.event === "profile_created" ||
        e.event === "profile_updated" ||
        e.event === "profile_deleted"
      ) {
        refreshProfiles();
      }
    });
  }, [unlocked]);

  if (!unlocked) return <LoginScreen onUnlocked={() => setUnlocked(true)} />;

  const selected = profiles.find((p) => p.id === selectedId) ?? null;

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center justify-between border-b border-bg-border bg-bg-elevated px-4 py-2">
        <div className="flex items-center gap-2">
          <span className="font-semibold">Private Browser</span>
          <span className="text-xs text-muted">v0.7.0</span>
        </div>
        <nav className="flex gap-1">
          <TabBtn current={tab} value="profiles" onClick={() => setTab("profiles")}>
            Profiles
          </TabBtn>
          <TabBtn current={tab} value="proxies" onClick={() => setTab("proxies")}>
            Proxies
          </TabBtn>
          <TabBtn current={tab} value="settings" onClick={() => setTab("settings")}>
            Settings
          </TabBtn>
        </nav>
        <div className="flex items-center gap-2">
          <label className="cursor-pointer rounded border border-bg-border px-2 py-1 text-xs text-muted hover:text-white">
            Import
            <input
              type="file"
              accept=".pbprof"
              hidden
              onChange={async (e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                const pw = window.prompt("Import password:");
                if (!pw) {
                  e.target.value = "";
                  return;
                }
                try {
                  await api.importProfile(pw, f);
                  refreshProfiles();
                } catch (ex: any) {
                  window.alert(ex?.detail ?? String(ex));
                }
                e.target.value = "";
              }}
            />
          </label>
          <button
            className="rounded border border-bg-border px-2 py-1 text-xs text-muted hover:text-white"
            onClick={async () => {
              await api.lock();
              setUnlocked(false);
            }}
          >
            Lock
          </button>
        </div>
      </header>
      <main className="flex flex-1 overflow-hidden">
        {tab === "profiles" && (
          <>
            <Sidebar
              profiles={profiles}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onCreated={refreshProfiles}
              selectedIds={selectedIds}
              onToggleSelect={(id) => {
                setSelectedIds((prev) => {
                  const next = new Set(prev);
                  if (next.has(id)) next.delete(id);
                  else next.add(id);
                  return next;
                });
              }}
              onClearSelection={() => setSelectedIds(new Set())}
              onBulkDeleted={() => {
                setSelectedId(null);
                refreshProfiles();
              }}
            />
            <ProfileDetail
              profile={selected}
              onChanged={refreshProfiles}
              onDeleted={() => {
                setSelectedId(null);
                refreshProfiles();
              }}
            />
          </>
        )}
        {tab === "proxies" && <ProxyPanel />}
        {tab === "settings" && <SettingsPanel />}
      </main>
    </div>
  );
}

function TabBtn({
  current,
  value,
  onClick,
  children,
}: {
  current: string;
  value: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  const active = current === value;
  return (
    <button
      onClick={onClick}
      className={`rounded px-3 py-1 text-sm ${active ? "bg-accent text-white" : "text-muted hover:text-white"}`}
    >
      {children}
    </button>
  );
}
