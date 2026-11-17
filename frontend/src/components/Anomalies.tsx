import { useEffect, useState } from "react";
import type {
  AnomalyRecord,
  AnomalyStatsResponse,
  AnomalyVerdictListResponse,
} from "../types/anomalies";

const PAGE_SIZE = 100;

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { credentials: "same-origin" });
  if (response.status === 401) {
    window.location.assign("/dashboard/login");
    throw new Error("Требуется повторный вход.");
  }
  const payload: unknown = await response.json();
  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null && "detail" in payload
      ? String((payload as { detail: unknown }).detail)
      : `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return payload as T;
}

function AnomalyCard({ item }: { item: AnomalyRecord }) {
  const suspicious = item.status === "SUSPICIOUS";
  return (
    <article data-anomaly-status={item.status} className="rounded-xl border border-jamp-line bg-black/10 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-sm font-medium text-slate-100">{item.package ?? "Package: UNKNOWN"}</div>
          <div className="mt-1 break-all font-mono text-[10px] text-slate-500">{item.verdict_id}</div>
          <time className="mt-1 block text-xs text-slate-500" dateTime={item.created_at}>{item.created_at}</time>
        </div>
        <span className={`rounded-full border px-3 py-1 text-[10px] font-semibold ${suspicious ? "border-rose-400/30 text-rose-300" : "border-amber-400/30 text-amber-200"}`}>
          {item.status}
        </span>
      </div>
      <div className="mt-3 break-all font-mono text-[10px] text-slate-600">SHA-256 · {item.code_hash}</div>
    </article>
  );
}

export function Anomalies() {
  const [stats, setStats] = useState<AnomalyStatsResponse | null>(null);
  const [inconclusive, setInconclusive] = useState<AnomalyVerdictListResponse | null>(null);
  const [suspicious, setSuspicious] = useState<AnomalyVerdictListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [statsPayload, inconclusivePayload, suspiciousPayload] = await Promise.all([
          getJson<AnomalyStatsResponse>("/v1/stats"),
          getJson<AnomalyVerdictListResponse>(`/v1/verdicts?status=INCONCLUSIVE&limit=${PAGE_SIZE}&offset=0`),
          getJson<AnomalyVerdictListResponse>(`/v1/verdicts?status=SUSPICIOUS&limit=${PAGE_SIZE}&offset=0`),
        ]);
        if (!Number.isInteger(statsPayload.inconclusive) || statsPayload.inconclusive < 0
          || !Number.isInteger(inconclusivePayload.total) || inconclusivePayload.total < 0
          || !Number.isInteger(suspiciousPayload.total) || suspiciousPayload.total < 0
          || !Array.isArray(inconclusivePayload.items) || !Array.isArray(suspiciousPayload.items)) {
          throw new Error("API вернул некорректную структуру аномалий.");
        }
        if (!cancelled) {
          setStats(statsPayload);
          setInconclusive(inconclusivePayload);
          setSuspicious(suspiciousPayload);
        }
      } catch (cause) {
        if (!cancelled) setError(cause instanceof Error ? cause.message : "Не удалось загрузить аномалии.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => { cancelled = true; };
  }, []);

  const inconclusiveTotal = stats?.inconclusive ?? 0;
  const suspiciousTotal = suspicious?.total ?? 0;
  const records = [...(inconclusive?.items ?? []), ...(suspicious?.items ?? [])]
    .sort((left, right) => right.created_at.localeCompare(left.created_at));
  const inconclusiveCountMismatch = inconclusive !== null && inconclusive.total !== inconclusiveTotal;

  return (
    <section aria-label="Аномалии" className="space-y-6">
      <div>
        <div className="text-xs uppercase tracking-[0.18em] text-amber-200">Persisted verdicts · evidence state</div>
        <h2 className="mt-2 text-2xl font-semibold text-white">Аномалии</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
          Здесь отображаются только сохранённые вердикты INCONCLUSIVE и SUSPICIOUS. Это не очередь AMBIGUOUS и не запросы на решение человеком.
        </p>
      </div>

      {loading && <p role="status" className="rounded-xl border border-jamp-line p-5 text-sm text-slate-400">Загружаем сохранённые аномалии…</p>}
      {error && <p role="alert" className="rounded-xl border border-rose-400/30 p-5 text-sm text-rose-300">Аномалии недоступны: {error}</p>}

      {!loading && !error && stats && inconclusive && suspicious && (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-2xl border border-jamp-line bg-jamp-panel/60 p-5">
              <div className="text-xs text-slate-500">Total INCONCLUSIVE · /v1/stats</div>
              <div className="mt-2 text-3xl font-semibold text-amber-200">{inconclusiveTotal}</div>
            </div>
            <div className="rounded-2xl border border-jamp-line bg-jamp-panel/60 p-5">
              <div className="text-xs text-slate-500">Total SUSPICIOUS · /v1/verdicts</div>
              <div className="mt-2 text-3xl font-semibold text-rose-300">{suspiciousTotal}</div>
            </div>
          </div>

          {inconclusiveCountMismatch && (
            <p role="alert" className="rounded-xl border border-amber-400/30 bg-amber-400/[0.04] p-4 text-xs leading-5 text-amber-100">
              DATA_MISMATCH: счётчики расходятся — /v1/stats сообщает {inconclusiveTotal}, а фильтр INCONCLUSIVE сообщает {inconclusive.total}. Расхождение сохранено, автоматическое согласование не выполняется.
            </p>
          )}

          {inconclusiveTotal + suspiciousTotal === 0 ? (
            <p className="rounded-xl border border-dashed border-jamp-line p-6 text-sm text-slate-400">
              Аномалий не обнаружено.
            </p>
          ) : records.length > 0 ? (
            <div className="space-y-3">
              {records.map((item) => <AnomalyCard key={item.verdict_id} item={item} />)}
              <p className="text-xs text-slate-500">
                Показано {records.length} из {inconclusiveTotal + suspiciousTotal} записей. Лимит API: {PAGE_SIZE} записей на статус.
              </p>
            </div>
          ) : (
            <p className="rounded-xl border border-jamp-line p-5 text-sm text-slate-400">
              Счётчики ненулевые, но записи на первой странице не получены. Данные не интерпретируются как пустое состояние.
            </p>
          )}
        </>
      )}
    </section>
  );
}
