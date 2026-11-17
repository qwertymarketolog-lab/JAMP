import { useEffect, useState } from "react";
import { Providers } from "./Providers";
import type { DashboardSessionResponse } from "../types/anomalies";

export function Settings() {
  const [session, setSession] = useState<DashboardSessionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const response = await fetch("/api/session", { credentials: "same-origin" });
        if (response.status === 401) {
          window.location.assign("/dashboard/login");
          return;
        }
        const payload: unknown = await response.json();
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        if (typeof payload !== "object" || payload === null
          || (payload as DashboardSessionResponse).authenticated !== true
          || typeof (payload as DashboardSessionResponse).org_id !== "string"
          || typeof (payload as DashboardSessionResponse).session_expires_at !== "string") {
          throw new Error("Некорректный ответ /api/session.");
        }
        if (!cancelled) setSession(payload as DashboardSessionResponse);
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Не удалось получить сессию.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => { cancelled = true; };
  }, []);

  return (
    <section aria-label="Настройки" className="space-y-7">
      <div>
        <div className="text-xs uppercase tracking-[0.18em] text-sky-300">Organization · session · configuration</div>
        <h2 className="mt-2 text-2xl font-semibold text-white">Настройки</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">Только параметры, которые подтверждаются текущим серверным контрактом.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <article className="rounded-2xl border border-jamp-line bg-jamp-panel/60 p-5">
          <h3 className="text-sm font-semibold text-slate-200">Организация</h3>
          {loading && <p role="status" className="mt-3 text-sm text-slate-400">Проверяем сессию…</p>}
          {error && <p role="alert" className="mt-3 text-sm text-rose-300">Сессия недоступна: {error}</p>}
          {session && (
            <>
              <div className="mt-3 break-all font-mono text-sm text-slate-100" data-testid="organization-id">{session.org_id}</div>
              <div className="mt-2 text-xs text-slate-500">Сессия действительна до {session.session_expires_at}</div>
            </>
          )}
        </article>
        <article className="rounded-2xl border border-jamp-line bg-jamp-panel/60 p-5">
          <h3 className="text-sm font-semibold text-slate-200">API Key status</h3>
          <div className="mt-3 inline-flex rounded-full border border-amber-400/30 bg-amber-400/[0.05] px-3 py-1 text-xs text-amber-200">NOT_IMPLEMENTED</div>
          <p className="mt-2 text-sm text-slate-400">Управление ключами — в разработке.</p>
        </article>
      </div>

      <article className="rounded-2xl border border-jamp-line bg-jamp-panel/60 p-5">
        <h3 className="mb-4 text-sm font-semibold text-slate-200">Frozen Core</h3>
        <div className="inline-flex rounded-full border border-amber-400/30 bg-amber-400/[0.05] px-3 py-1 text-xs font-semibold text-amber-200">
          NOT_VERIFIED_IN_UI
        </div>
        <p className="mt-2 text-sm text-slate-400">
          Интерфейс не проверяет blob SHA src/jamp/run.py. Для доказательства Δ=0 используйте успешный G1 Trusted Lineage artifact.
        </p>
      </article>

      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-semibold text-slate-200">Integrations</h3>
          <p className="mt-1 text-xs text-slate-500">Те же статусы и evidence-срез, что и во вкладке «Модели и провайдеры».</p>
        </div>
        <Providers />
      </div>
    </section>
  );
}
