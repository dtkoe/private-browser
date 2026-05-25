"use client";
import { useEffect, useRef, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { t, useLang } from "@/lib/i18n";
import type { Profile, Proxy } from "@/lib/types";

interface Props {
  profile: Profile | null;
  onChanged: () => void;
  onDeleted: () => void;
}

const COLOR_SWATCHES = ["#5b9eff", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#06b6d4", "#94a3b8", null];

export function ProfileDetail({ profile, onChanged, onDeleted }: Props) {
  useLang();
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const [notesDraft, setNotesDraft] = useState("");
  const [tagsDraft, setTagsDraft] = useState("");
  const notesTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    api.listProxies().then(setProxies).catch(() => {});
    setEditingName(false);
    setNameDraft(profile?.name ?? "");
    setNotesDraft(profile?.notes ?? "");
    setTagsDraft((profile?.tags ?? []).join(", "));
    setErr(null);
  }, [profile?.id]);

  if (!profile) {
    return (
      <section className="flex flex-1 items-center justify-center text-muted">
        {t("profile.empty")}
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

  async function handleExport() {
    if (!profile) return;
    const pw = window.prompt(t("profile.export_password_prompt"));
    if (!pw) return;
    if (pw.length < 12) {
      setErr("password must be at least 12 chars");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const blob = await api.exportProfile(profile.id, pw, true);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${profile.name}.pbprof`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (e: any) {
      setErr(e?.detail ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  const fp = profile.fingerprint || {};

  async function commitName() {
    const trimmed = nameDraft.trim();
    if (!trimmed || trimmed === profile?.name) {
      setEditingName(false);
      return;
    }
    setEditingName(false);
    await action(() => api.updateProfile(profile!.id, { name: trimmed }));
  }

  async function commitNotes(value: string) {
    if (!profile) return;
    if (value === (profile.notes ?? "")) return;
    await action(() => api.updateProfile(profile.id, { notes: value }));
  }

  function scheduleNotesCommit(value: string) {
    setNotesDraft(value);
    if (notesTimerRef.current) clearTimeout(notesTimerRef.current);
    notesTimerRef.current = setTimeout(() => commitNotes(value), 600);
  }

  async function commitTags() {
    if (!profile) return;
    const parsed = tagsDraft
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const current = profile.tags ?? [];
    if (parsed.length === current.length && parsed.every((t, i) => t === current[i])) {
      return;
    }
    await action(() => api.updateProfile(profile.id, { tags: parsed }));
  }

  async function commitColor(c: string | null) {
    if (!profile) return;
    if (c === (profile.color ?? null)) return;
    await action(() => api.updateProfile(profile.id, { color: c }));
  }

  return (
    <section className="flex-1 overflow-y-auto p-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="min-w-0 flex-1 basis-64">
          {editingName ? (
            <input
              autoFocus
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              onBlur={commitName}
              onKeyDown={(e) => {
                if (e.key === "Enter") commitName();
                else if (e.key === "Escape") { setNameDraft(profile.name); setEditingName(false); }
              }}
              className="w-full rounded border border-accent bg-bg px-2 py-1 text-xl font-semibold outline-none"
            />
          ) : (
            <h2
              className="cursor-text truncate text-xl font-semibold hover:underline"
              onClick={() => { setNameDraft(profile.name); setEditingName(true); }}
              title={t("profile.click_to_rename")}
            >
              {profile.color && (
                <span
                  className="mr-2 inline-block h-3 w-3 rounded-full align-middle"
                  style={{ backgroundColor: profile.color }}
                />
              )}
              {profile.name}
            </h2>
          )}
          <p className="text-xs text-muted">
            {profile.status} · OS: {fp._os ?? "?"} · UA: {(fp["navigator.userAgent"] ?? "").slice(0, 60)}…
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {profile.status === "running" ? (
            <button
              disabled={busy}
              onClick={() => action(() => api.stopProfile(profile.id))}
              className="rounded bg-yellow-700 px-3 py-1 text-sm text-white hover:bg-yellow-600 disabled:opacity-50"
            >
              {t("profile.stop")}
            </button>
          ) : (
            <button
              disabled={busy}
              onClick={() => action(() => api.launchProfile(profile.id))}
              className="rounded bg-green-700 px-3 py-1 text-sm text-white hover:bg-green-600 disabled:opacity-50"
            >
              {t("profile.launch")}
            </button>
          )}
          <button
            disabled={busy}
            onClick={() => action(() => api.regenerateProfile(profile.id))}
            className="rounded border border-bg-border px-3 py-1 text-sm hover:bg-bg-border/40 disabled:opacity-50"
          >
            {t("profile.regenerate")}
          </button>
          <button
            disabled={busy}
            onClick={() => action(() => api.cloneProfile(profile.id, `${profile.name} (clone)`, true))}
            className="rounded border border-bg-border px-3 py-1 text-sm hover:bg-bg-border/40 disabled:opacity-50"
          >
            {t("profile.clone")}
          </button>
          <button
            disabled={busy}
            onClick={handleExport}
            className="rounded border border-bg-border px-3 py-1 text-sm hover:bg-bg-border/40 disabled:opacity-50"
          >
            {t("profile.export")}
          </button>
          <button
            disabled={busy}
            onClick={() => {
              if (window.confirm(t("profile.delete_confirm", { name: profile.name }))) {
                action(() => api.deleteProfile(profile.id).then(onDeleted));
              }
            }}
            className="rounded border border-red-800 px-3 py-1 text-sm text-red-400 hover:bg-red-900/30 disabled:opacity-50"
          >
            {t("profile.delete")}
          </button>
        </div>
      </div>

      {err && <div className="mb-4 rounded bg-red-900/40 px-3 py-2 text-sm text-red-300">{err}</div>}

      <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="rounded border border-bg-border bg-bg-elevated p-4">
          <div className="mb-2 text-xs uppercase text-muted">{t("profile.notes")}</div>
          <textarea
            value={notesDraft}
            onChange={(e) => scheduleNotesCommit(e.target.value)}
            onBlur={() => commitNotes(notesDraft)}
            placeholder={t("profile.notes_placeholder")}
            rows={3}
            className="w-full rounded border border-bg-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
          />
        </div>
        <div className="rounded border border-bg-border bg-bg-elevated p-4">
          <div className="mb-2 text-xs uppercase text-muted">{t("profile.tags")}</div>
          <input
            value={tagsDraft}
            onChange={(e) => setTagsDraft(e.target.value)}
            onBlur={commitTags}
            onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
            placeholder={t("profile.tags_placeholder")}
            className="mb-3 w-full rounded border border-bg-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
          />
          <div className="mb-1 text-xs uppercase text-muted">{t("profile.color")}</div>
          <div className="flex flex-wrap gap-1">
            {COLOR_SWATCHES.map((c, i) => (
              <button
                key={i}
                onClick={() => commitColor(c)}
                title={c ?? "none"}
                className={`h-6 w-6 rounded-full border ${
                  (profile.color ?? null) === c ? "border-white" : "border-bg-border"
                }`}
                style={{ backgroundColor: c ?? "transparent" }}
              >
                {c === null ? <span className="text-xs text-muted">×</span> : null}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mb-6 rounded border border-bg-border bg-bg-elevated p-4">
        <div className="mb-2 text-xs uppercase text-muted">{t("profile.proxy")}</div>
        <select
          value={profile.proxy_id ?? ""}
          onChange={(e) => action(() => api.bindProxy(profile.id, e.target.value || null))}
          className="w-full rounded border border-bg-border bg-bg px-2 py-1 text-sm outline-none focus:border-accent"
        >
          <option value="">{t("profile.no_proxy")}</option>
          {proxies.map((p) => (
            <option key={p.id} value={p.id}>
              {p.label} — {p.type}://{p.host}:{p.port}
              {p.last_check_ok ? " ✓" : p.last_checked_at ? " ✗" : ""}
            </option>
          ))}
        </select>
      </div>

      <ExtensionsBlock profileId={profile.id} />

      <details className="rounded border border-bg-border bg-bg-elevated p-4">
        <summary className="cursor-pointer text-xs uppercase text-muted">{t("profile.fingerprint_raw")}</summary>
        <pre className="mt-3 overflow-x-auto text-xs">{JSON.stringify(fp, null, 2)}</pre>
      </details>
    </section>
  );
}

function ExtensionsBlock({ profileId }: { profileId: string }) {
  useLang();
  const [exts, setExts] = useState<Array<{ id: string; name: string; version: string; filename: string }>>([]);
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    try {
      setExts(await api.listExtensions(profileId));
    } catch {}
  }
  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileId]);

  async function onPick(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setErr(null);
    try {
      await api.installExtension(profileId, f);
      refresh();
    } catch (ex: any) {
      setErr(ex?.detail ?? String(ex));
    }
    e.target.value = "";
  }

  return (
    <div className="mb-6 rounded border border-bg-border bg-bg-elevated p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs uppercase text-muted">{t("profile.extensions")} ({exts.length})</span>
        <label className="cursor-pointer rounded border border-bg-border px-2 py-0.5 text-xs hover:bg-bg-border/40">
          {t("profile.install_xpi")}
          <input type="file" accept=".xpi" hidden onChange={onPick} />
        </label>
      </div>
      {err && <div className="mb-2 text-xs text-red-400">{err}</div>}
      {exts.length === 0 ? (
        <div className="text-sm text-muted">{t("profile.no_extensions")}</div>
      ) : (
        <ul className="text-sm">
          {exts.map((e) => (
            <li
              key={e.id}
              className="flex items-center justify-between border-t border-bg-border/40 py-1.5 first:border-0"
            >
              <span>
                {e.name} <span className="text-xs text-muted">v{e.version}</span>
              </span>
              <button
                onClick={async () => {
                  await api.removeExtension(profileId, e.id);
                  refresh();
                }}
                className="text-xs text-red-400 hover:underline"
              >
                {t("profile.remove")}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
