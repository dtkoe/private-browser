"use client";

export function SettingsPanel() {
  return (
    <section className="flex-1 overflow-y-auto p-6">
      <h2 className="mb-4 text-xl font-semibold">Settings</h2>
      <div className="rounded border border-bg-border bg-bg-elevated p-4">
        <div className="mb-3">
          <div className="text-xs uppercase text-muted">Theme</div>
          <div className="mt-1 text-sm">Dark (only theme in v1)</div>
        </div>
        <div className="mb-3">
          <div className="text-xs uppercase text-muted">Backend</div>
          <div className="mt-1 text-sm">http://127.0.0.1:8769</div>
        </div>
        <div>
          <div className="text-xs uppercase text-muted">Version</div>
          <div className="mt-1 text-sm">0.4.0 (M4)</div>
        </div>
      </div>
    </section>
  );
}
