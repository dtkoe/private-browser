"use client";
import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import { getLang, setLang, t, useLang, type Lang } from "@/lib/i18n";

interface UpdateInfo {
  current_version: string;
  latest_version: string | null;
  has_update: boolean;
  release_url: string | null;
}

export function SettingsPanel() {
  const lang = useLang();
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
      <h2 className="mb-4 text-xl font-semibold">{t("settings.title")}</h2>

      <div className="mb-4 rounded border border-bg-border bg-bg-elevated p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="text-xs uppercase text-muted">{t("settings.language")}</div>
            <div className="mt-1 flex gap-2 text-sm">
              <button
                onClick={() => setLang("en")}
                className={`rounded border px-3 py-1 text-xs ${
                  lang === "en"
                    ? "border-accent bg-accent text-white"
                    : "border-bg-border text-muted hover:text-white"
                }`}
              >
                English
              </button>
              <button
                onClick={() => setLang("ru")}
                className={`rounded border px-3 py-1 text-xs ${
                  lang === "ru"
                    ? "border-accent bg-accent text-white"
                    : "border-bg-border text-muted hover:text-white"
                }`}
              >
                Русский
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="mb-4 rounded border border-bg-border bg-bg-elevated p-4">
        <div className="mb-3 flex items-center justify-between">
          <div>
            <div className="text-xs uppercase text-muted">{t("settings.version")}</div>
            <div className="mt-1 text-sm">{info?.version ?? "?"}</div>
          </div>
          <button
            onClick={checkForUpdates}
            disabled={checking}
            className="rounded border border-bg-border px-3 py-1 text-sm hover:bg-bg-border/40 disabled:opacity-50"
          >
            {checking ? t("settings.checking") : t("settings.check_updates")}
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
                <span className="font-semibold">{t("settings.update_available")}: v{update.latest_version}</span>
                {update.release_url && (
                  <>
                    {" — "}
                    <a className="underline" href={update.release_url} target="_blank" rel="noreferrer">
                      {t("settings.release_notes")}
                    </a>
                  </>
                )}
              </>
            ) : update.latest_version ? (
              <>{t("settings.up_to_date")} (latest: v{update.latest_version}).</>
            ) : (
              <>{t("settings.no_update_server")}</>
            )}
          </div>
        )}
      </div>

      <div className="rounded border border-bg-border bg-bg-elevated p-4">
        <div className="mb-3">
          <div className="text-xs uppercase text-muted">{t("settings.theme")}</div>
          <div className="mt-1 text-sm">{t("settings.theme_dark_only")}</div>
        </div>
        <div>
          <div className="text-xs uppercase text-muted">{t("settings.backend")}</div>
          <div className="mt-1 text-sm">http://127.0.0.1:8769</div>
        </div>
      </div>
    </section>
  );
}
