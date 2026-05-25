"use client";
import { useState } from "react";

import { api, ApiError } from "@/lib/api";
import { t, useLang } from "@/lib/i18n";
import type { Profile } from "@/lib/types";

interface Props {
  profiles: Profile[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onCreated: () => void;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onClearSelection: () => void;
  onBulkDeleted: () => void;
}

export function Sidebar({
  profiles,
  selectedId,
  onSelect,
  onCreated,
  selectedIds,
  onToggleSelect,
  onClearSelection,
  onBulkDeleted,
}: Props) {
  useLang();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [targetOs, setTargetOs] = useState<"" | "windows" | "macos" | "linux">("");
  const [locale, setLocale] = useState<string>("en-US");
  const [err, setErr] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  async function create() {
    setErr(null);
    try {
      await api.createProfile({
        name: name || `Profile ${Date.now()}`,
        target_os: targetOs || undefined,
        locale: locale || undefined,
      });
      setName("");
      setTargetOs("");
      setLocale("en-US");
      setCreating(false);
      onCreated();
    } catch (e: any) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    }
  }

  async function bulkDelete() {
    const ids = Array.from(selectedIds);
    if (!ids.length) return;
    if (!window.confirm(t("sidebar.bulk_delete_confirm", { n: ids.length }))) {
      return;
    }
    try {
      await api.bulkDeleteProfiles(ids);
      onClearSelection();
      onBulkDeleted();
    } catch (e: any) {
      setErr(e instanceof ApiError ? e.detail : String(e));
    }
  }

  const filtered = filter
    ? profiles.filter((p) => p.name.toLowerCase().includes(filter.toLowerCase()))
    : profiles;

  return (
    <aside className="flex w-72 flex-col border-r border-bg-border bg-bg-elevated">
      <div className="flex items-center justify-between border-b border-bg-border p-3">
        <span className="text-xs uppercase tracking-wide text-muted">
          {t("sidebar.profiles")} ({profiles.length})
        </span>
        <button
          className="rounded bg-accent px-2 py-0.5 text-xs text-white hover:bg-accent-hover"
          onClick={() => setCreating(true)}
        >
          {t("sidebar.new")}
        </button>
      </div>
      {profiles.length > 0 && (
        <div className="border-b border-bg-border p-2">
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder={t("sidebar.filter")}
            className="w-full rounded border border-bg-border bg-bg px-2 py-1 text-xs outline-none focus:border-accent"
          />
        </div>
      )}
      {selectedIds.size > 0 && (
        <div className="flex items-center justify-between border-b border-bg-border bg-accent/10 px-3 py-2 text-xs">
          <span>{selectedIds.size} {t("sidebar.selected_n")}</span>
          <div className="flex gap-2">
            <button onClick={bulkDelete} className="text-red-400 hover:underline">
              {t("sidebar.delete")}
            </button>
            <button onClick={onClearSelection} className="text-muted hover:text-white">
              {t("sidebar.clear")}
            </button>
          </div>
        </div>
      )}
      {creating && (
        <div className="border-b border-bg-border p-3">
          <input
            autoFocus
            placeholder={t("sidebar.name_placeholder")}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mb-2 w-full rounded border border-bg-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
          />
          <select
            value={targetOs}
            onChange={(e) => setTargetOs(e.target.value as any)}
            className="mb-2 w-full rounded border border-bg-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
          >
            <option value="">{t("sidebar.random_os")}</option>
            <option value="windows">Windows</option>
            <option value="macos">macOS</option>
            <option value="linux">Linux</option>
          </select>
          <select
            value={locale}
            onChange={(e) => setLocale(e.target.value)}
            title={t("sidebar.locale_label")}
            className="mb-2 w-full rounded border border-bg-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
          >
            <option value="en-US">English (US) — America/New_York</option>
            <option value="en-GB">English (UK) — Europe/London</option>
            <option value="ru-RU">Russian — Europe/Moscow</option>
            <option value="de-DE">German — Europe/Berlin</option>
            <option value="fr-FR">French — Europe/Paris</option>
            <option value="es-ES">Spanish — Europe/Madrid</option>
            <option value="it-IT">Italian — Europe/Rome</option>
            <option value="pt-BR">Portuguese (BR) — America/Sao_Paulo</option>
            <option value="ja-JP">Japanese — Asia/Tokyo</option>
            <option value="zh-CN">Chinese (CN) — Asia/Shanghai</option>
            <option value="uk-UA">Ukrainian — Europe/Kyiv</option>
            <option value="pl-PL">Polish — Europe/Warsaw</option>
            <option value="tr-TR">Turkish — Europe/Istanbul</option>
          </select>
          {err && <div className="mb-2 text-xs text-red-400">{err}</div>}
          <div className="flex gap-2">
            <button className="flex-1 rounded bg-accent px-2 py-1 text-xs text-white" onClick={create}>
              {t("sidebar.create")}
            </button>
            <button
              className="flex-1 rounded border border-bg-border px-2 py-1 text-xs"
              onClick={() => setCreating(false)}
            >
              {t("sidebar.cancel")}
            </button>
          </div>
        </div>
      )}
      <ul className="flex-1 overflow-y-auto">
        {filtered.map((p) => {
          const checked = selectedIds.has(p.id);
          return (
            <li
              key={p.id}
              className={`group flex items-center gap-2 border-b border-bg-border/50 px-2 py-1.5 text-sm transition-colors ${
                selectedId === p.id ? "bg-accent/20" : "hover:bg-bg-border/40"
              }`}
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => onToggleSelect(p.id)}
                onClick={(e) => e.stopPropagation()}
                aria-label={`select ${p.name}`}
                className="cursor-pointer accent-accent"
              />
              <button
                onClick={() => onSelect(p.id)}
                className="flex flex-1 items-center gap-2 text-left"
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
          );
        })}
        {profiles.length === 0 && (
          <li className="p-4 text-center text-sm text-muted">{t("sidebar.no_profiles")}</li>
        )}
        {profiles.length > 0 && filtered.length === 0 && (
          <li className="p-4 text-center text-sm text-muted">{t("sidebar.no_matches")} "{filter}"</li>
        )}
      </ul>
    </aside>
  );
}
