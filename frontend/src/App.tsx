import { useEffect, useState, type ReactNode } from "react";
import { ClaimCard } from "./components/ClaimCard";
import type { DashboardStats, EvidenceGraphResponse, PersistedVerdict, VerdictListResponse, VerifyTextResponse } from "./types/api";
import { EvidenceGraph } from "./components/EvidenceGraph";
import { Providers } from "./components/Providers";

type IconName = "grid" | "scan" | "store" | "telegram" | "network" | "archive" | "settings";

const navigation: { label: string; icon: IconName; section: string; active?: boolean; planned?: boolean }[] = [
  { label: "Обзор", icon: "grid", section: "Рабочее пространство", active: true },
  { label: "Проверка утверждений", icon: "scan", section: "Рабочее пространство" },
  { label: "История", icon: "archive", section: "Рабочее пространство" },
  { label: "Маркетплейс", icon: "store", section: "Экосистема", planned: true },
  { label: "Telegram", icon: "telegram", section: "Экосистема", planned: true },
  { label: "Модели и провайдеры", icon: "network", section: "Инфраструктура" },
  { label: "Evidence Vault", icon: "archive", section: "Инфраструктура", planned: true },
  { label: "Настройки", icon: "settings", section: "Система", planned: true },
];

function Icon({ name, className = "h-5 w-5" }: { name: IconName; className?: string }) {
  const paths: Record<IconName, ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></>,
    scan: <><path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3" /><path d="m8 12 2.5 2.5L16 9" /></>,
    store: <><path d="M3 10h18l-1.5-6h-15L3 10Z" /><path d="M5 10v10h14V10M9 20v-6h6v6" /></>,
    telegram: <><path d="m21 3-7.5 18-3.8-7.7L2 9.5 21 3Z" /><path d="m9.7 13.3 5-4.5" /></>,
    network: <><circle cx="12" cy="5" r="2.5" /><circle cx="5" cy="18" r="2.5" /><circle cx="19" cy="18" r="2.5" /><path d="m10.8 7.2-4.5 8.5m7-8.5 4.5 8.5M7.5 18h9" /></>,
    archive: <><rect x="3" y="4" width="18" height="4" rx="1" /><path d="M5 8v12h14V8m-8 4h2" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="m19.4 15 .1.1 1.1 1.9-2 3.4-2.2-.5a8 8 0 0 1-1.7 1l-.4 2.1h-4l-.4-2.1a8 8 0 0 1-1.7-1l-2.2.5-2-3.4 1.1-1.9a8 8 0 0 1 0-2l-1.1-1.9 2-3.4 2.2.5a8 8 0 0 1 1.7-1L10.3 5h4l.4 2.1a8 8 0 0 1 1.7 1l2.2-.5 2 3.4-1.1 1.9a8 8 0 0 1-.1 2.1Z" transform="translate(0 -2) scale(.9)" /></>,
  };
  return <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function PersistedVerdictRow({ item, onShowGraph }: { item: PersistedVerdict; onShowGraph: (verdictId: string) => void }) {
  const style = item.status === "HALLUCINATION_CAUGHT" || item.status === "INTEGRITY_VIOLATED"
    ? "border-rose-400/30 text-rose-300"
    : item.status === "INCONCLUSIVE" || item.status === "SUSPICIOUS"
      ? "border-amber-400/30 text-amber-200"
      : "border-emerald-400/30 text-emerald-300";
  const label = item.status === "CLEAN" ? "CLEAN · не эквивалент VERIFIED" : item.status;
  return <article className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-jamp-line bg-black/10 p-4">
    <div className="min-w-0"><div className="text-sm font-medium text-slate-200">{item.package ?? "Package: UNKNOWN"}</div><div className="mt-1 break-all font-mono text-[10px] text-slate-500">{item.verdict_id}</div><div className="mt-1 text-xs text-slate-500">{item.created_at}</div><div className="mt-1 break-all font-mono text-[10px] text-slate-600">SHA-256 · {item.code_hash}</div></div>
    <div className="flex items-center gap-2"><span className={`rounded-full border px-3 py-1 text-[10px] font-semibold ${style}`}>{label}</span><button type="button" onClick={() => onShowGraph(item.verdict_id)} className="rounded-lg border border-jamp-blue/30 px-3 py-2 text-xs text-sky-200 hover:bg-jamp-blue/10">Показать граф доказательств</button></div>
  </article>;
}

function App() {
  const [active, setActive] = useState("Обзор");
  const sections = [...new Set(navigation.map((item) => item.section))];
  const [inputText, setInputText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<VerifyTextResponse | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [statsError, setStatsError] = useState<string | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [history, setHistory] = useState<VerdictListResponse | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historySearch, setHistorySearch] = useState("");
  const [historyQuery, setHistoryQuery] = useState("");
  const [selectedGraph, setSelectedGraph] = useState<EvidenceGraphResponse | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [graphError, setGraphError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setStatsLoading(true); setStatsError(null);
      try {
        const response = await fetch("/v1/stats", { credentials: "same-origin" });
        if (response.status === 401) { window.location.assign("/dashboard/login"); return; }
        const payload = await response.json();
        if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : `HTTP ${response.status}`);
        if (!cancelled) setStats(payload as DashboardStats);
      } catch (error) {
        if (!cancelled) setStatsError(error instanceof Error ? error.message : "Stats request failed");
      } finally { if (!cancelled) setStatsLoading(false); }
    };
    void load();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (active !== "История") return;
    let cancelled = false;
    const load = async () => {
      setHistoryLoading(true); setHistoryError(null);
      try {
        const params = new URLSearchParams({ limit: "20", offset: "0" });
        if (historyQuery) params.set("q", historyQuery);
        const response = await fetch(`/v1/verdicts?${params.toString()}`, { credentials: "same-origin" });
        if (response.status === 401) { window.location.assign("/dashboard/login"); return; }
        const payload = await response.json();
        if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : `HTTP ${response.status}`);
        if (!cancelled) setHistory(payload as VerdictListResponse);
      } catch (error) {
        if (!cancelled) setHistoryError(error instanceof Error ? error.message : "History request failed");
      } finally { if (!cancelled) setHistoryLoading(false); }
    };
    void load();
    return () => { cancelled = true; };
  }, [active, historyQuery]);

  const loadEvidenceGraph = async (verdictId: string) => {
    setSelectedGraph(null); setGraphError(null); setGraphLoading(true);
    try {
      const response = await fetch(`/v1/verdicts/${encodeURIComponent(verdictId)}/graph`, { credentials: "same-origin" });
      if (response.status === 401) { window.location.assign("/dashboard/login"); return; }
      const payload = await response.json();
      if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : `HTTP ${response.status}`);
      if (!payload || !Array.isArray(payload.nodes) || !Array.isArray(payload.edges)) throw new Error("Invalid evidence graph response");
      setSelectedGraph(payload as EvidenceGraphResponse);
    } catch (error) { setGraphError(error instanceof Error ? error.message : "Evidence graph request failed"); }
    finally { setGraphLoading(false); }
  };

  const readCookie = (name: string): string | null => {
    const prefix = `${name}=`;
    const cookie = document.cookie.split("; ").find((entry) => entry.startsWith(prefix));
    return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
  };

  const handleVerify = async () => {
    if (!inputText.trim() || loading) return;
    setLoading(true);
    setResult(null);
    setRequestError(null);
    try {
      const csrfToken = readCookie("jamp_dashboard_csrf");
      if (!csrfToken) {
        window.location.assign("/dashboard/login");
        return;
      }
      const response = await fetch("/api/ui_verify", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({ text: inputText }),
      });
      if (response.status === 401) {
        window.location.assign("/dashboard/login");
        return;
      }
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(
          typeof payload.detail === "string" ? payload.detail : `HTTP ${response.status}`,
        );
      }
      setResult(payload as VerifyTextResponse);
    } catch (error) {
      setRequestError(error instanceof Error ? error.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-jamp-base text-slate-100">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-72 flex-col border-r border-jamp-line/70 bg-[#0b1220] lg:flex">
        <div className="flex h-20 items-center gap-3 border-b border-jamp-line/60 px-7">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-jamp-blue/30 bg-jamp-blue/10 text-lg font-black text-jamp-blue shadow-glow">J</div>
          <div><div className="text-lg font-bold tracking-[0.18em]">JAMP</div><div className="text-[10px] uppercase tracking-[0.22em] text-jamp-muted">Trust Layer</div></div>
        </div>
        <div className="px-5 pt-7">
          <div className="mb-3 px-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">Навигация</div>
          {sections.map((section) => (
            <div key={section} className="mb-6">
              <div className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">{section}</div>
              <div className="space-y-1">
                {navigation.filter((item) => item.section === section).map((item) => (
                  <button key={item.label} onClick={() => !item.planned && setActive(item.label)} className={`group flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm transition ${active === item.label ? "border border-jamp-blue/20 bg-jamp-blue/10 text-sky-300" : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200"} ${item.planned ? "cursor-default opacity-60" : ""}`}>
                    <Icon name={item.icon} className="h-[18px] w-[18px]" />
                    <span className="flex-1">{item.label}</span>
                    {item.active && active === item.label && <span className="h-1.5 w-1.5 rounded-full bg-jamp-blue shadow-[0_0_10px_#38bdf8]" />}
                    {item.planned && <span className="rounded-md border border-jamp-line px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-slate-500">NOT_CONNECTED</span>}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="mt-auto p-5">
          <div className="rounded-2xl border border-jamp-line bg-jamp-panel/70 p-4">
            <div className="mb-2 flex items-center gap-2"><span className="h-2 w-2 rounded-full bg-jamp-amber" /><span className="text-xs font-semibold text-slate-300">Режим разработки</span></div>
            <p className="text-xs leading-5 text-slate-500">Интерфейсный каркас. Источники данных пока не подключены.</p>
          </div>
          <div className="mt-4 flex items-center gap-3 px-1">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-sky-500/30 to-emerald-400/20 text-xs font-bold text-sky-200">JL</div>
            <div><div className="text-xs font-medium text-slate-300">JAMP Operator</div><div className="text-[10px] text-slate-500">Local workspace</div></div>
          </div>
        </div>
      </aside>

      <main className="min-h-screen lg:pl-72">
        <header className="sticky top-0 z-10 flex h-20 items-center justify-between border-b border-jamp-line/60 bg-jamp-base/85 px-5 backdrop-blur-xl md:px-10">
          <div><div className="text-xs text-slate-500">JAMP / Workspace</div><h1 className="mt-1 text-lg font-semibold tracking-tight">{active}</h1></div>
          <div className="flex items-center gap-3">
            <span className="hidden rounded-full border border-jamp-amber/20 bg-jamp-amber/5 px-3 py-1.5 text-[11px] text-jamp-amber sm:inline-flex">BFF API · SERVER-SIDE AUTH</span>
            <button className="rounded-xl border border-jamp-line bg-jamp-panel px-3 py-2 text-xs text-slate-300">RU <span className="ml-1 text-slate-500">⌄</span></button>
          </div>
        </header>

        <div className={`mx-auto max-w-[1500px] px-5 py-8 md:px-10 md:py-10 ${active === "Модели и провайдеры" ? "hidden" : ""}`}>
          <div className="mb-8 flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
            <div><div className="mb-3 inline-flex items-center gap-2 rounded-full border border-jamp-blue/20 bg-jamp-blue/5 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-sky-300"><span className="h-1.5 w-1.5 rounded-full bg-jamp-blue" /> Evidence Infrastructure</div><h2 className="max-w-3xl text-3xl font-semibold tracking-tight text-white md:text-4xl">От утверждения —<br className="hidden sm:block" /> к проверяемому доказательству.</h2><p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">Единое рабочее пространство для проверки фактов, происхождения данных и будущих продуктов экосистемы JAMP.</p></div>
            <div className="rounded-xl border border-jamp-line bg-jamp-panel/70 px-4 py-3"><div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Состояние интерфейса</div><div className="mt-1 flex items-center gap-2 text-sm font-medium text-jamp-amber"><span className="h-2 w-2 rounded-full bg-jamp-amber" /> BFF · API integration</div></div>
          </div>

          <section aria-label="Статистика JAMP" className="mb-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {statsLoading ? <div className="panel-card p-5 text-sm text-slate-400" role="status">Загружаем статистику…</div>
            : statsError ? <div className="panel-card p-5 text-sm text-rose-300" role="alert">Статистика недоступна: {statsError}</div>
            : stats ? <>
              <div className="panel-card p-5"><div className="text-xs text-slate-500">Всего сохранённых проверок</div><div className="mt-2 text-2xl font-semibold text-slate-100">{stats.total_checks}</div><div className="mt-1 text-[10px] text-slate-500">Persisted verdict rows · all time</div></div>
              <div className="panel-card p-5"><div className="text-xs text-slate-500">HALLUCINATION_CAUGHT</div><div className="mt-2 text-2xl font-semibold text-rose-300">{stats.hallucinations_caught}</div></div>
              <div className="panel-card p-5"><div className="text-xs text-slate-500">INCONCLUSIVE</div><div className="mt-2 text-2xl font-semibold text-amber-200">{stats.inconclusive}</div></div>
              <div className="panel-card p-5"><div className="text-xs text-slate-500">CLEAN</div><div className="mt-2 text-2xl font-semibold text-emerald-300">{stats.status_counts.CLEAN}</div><div className="mt-1 text-[10px] text-slate-500">Не эквивалент VERIFIED</div></div>
            </> : <div className="panel-card p-5 text-sm text-slate-400">Статистика: UNKNOWN</div>}
          </section>
          {active === "История" && <section className="panel-card mb-7 p-6" aria-label="История вердиктов">
            <div><h2 className="text-sm font-semibold text-slate-100">История сохранённых вердиктов</h2><p className="mt-1 text-xs text-slate-500">GET /v1/verdicts · поиск в текущей организации</p></div>
            <form className="mt-5 flex flex-wrap gap-2" onSubmit={(event) => { event.preventDefault(); setHistoryQuery(historySearch.trim()); setSelectedGraph(null); setGraphError(null); }}>
              <input aria-label="Поиск по verdict_id или package" value={historySearch} onChange={(event) => setHistorySearch(event.target.value)} placeholder="Поиск по verdict_id или package" maxLength={200} className="min-w-[240px] flex-1 rounded-xl border border-jamp-line bg-[#080d18] px-4 py-3 text-sm text-slate-200 outline-none focus:border-sky-400/50" />
              <button type="submit" className="rounded-xl border border-jamp-blue/30 bg-jamp-blue/10 px-4 py-3 text-sm text-sky-200">Найти</button>
              <button type="button" onClick={() => { setHistorySearch(""); setHistoryQuery(""); setSelectedGraph(null); setGraphError(null); }} className="rounded-xl border border-jamp-line px-4 py-3 text-sm text-slate-300">Сбросить</button>
            </form>
            {historyLoading && <p className="mt-5 text-sm text-slate-400" role="status">Загружаем историю…</p>}
            {historyError && <p className="mt-5 text-sm text-rose-300" role="alert">История недоступна: {historyError}</p>}
            {history && !historyLoading && history.items.length === 0 && <p className="mt-5 rounded-xl border border-dashed border-jamp-line p-5 text-sm text-slate-400">{historyQuery ? "По запросу ничего не найдено." : "Сохранённых вердиктов пока нет. Это пустая история, а не ошибка проверки."}</p>}
            {history && history.items.length > 0 && <div className="mt-5 space-y-3">{history.items.map(item => <PersistedVerdictRow key={item.verdict_id} item={item} onShowGraph={loadEvidenceGraph} />)}<p className="text-xs text-slate-500">Показано {history.items.length} из {history.total}. CLEAN не означает VERIFIED.</p></div>}
            {graphLoading && <p className="mt-5 text-sm text-slate-400" role="status">Загружаем граф доказательств…</p>}
            {graphError && <p className="mt-5 text-sm text-rose-300" role="alert">Граф недоступен: {graphError}</p>}
            {selectedGraph && <div className="mt-6"><h3 className="mb-3 text-sm font-semibold text-slate-200">Сохранённый граф доказательств</h3><EvidenceGraph graph={selectedGraph} /></div>}
          </section>}
          <section className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
            {[
              { title: "Проверка утверждений", subtitle: "Claim verification", icon: "scan" as IconName, accent: "text-jamp-blue", note: "BFF endpoint · UI connected" },
              { title: "Evidence Vault", subtitle: "Источники и происхождение", icon: "archive" as IconName, accent: "text-jamp-green", note: "Экран запланирован" },
              { title: "Маркетплейс", subtitle: "Продукты и интеграции", icon: "store" as IconName, accent: "text-violet-300", note: "Продуктовый контур запланирован" },
              { title: "Telegram", subtitle: "Бот и каналы взаимодействия", icon: "telegram" as IconName, accent: "text-sky-300", note: "Интеграционный экран запланирован" },
            ].map((card) => <div key={card.title} className="panel-card group p-5"><div className="mb-5 flex items-start justify-between"><div className={`rounded-xl border border-white/5 bg-white/[0.04] p-3 ${card.accent}`}><Icon name={card.icon} className="h-5 w-5" /></div><span className="rounded-full border border-jamp-line px-2 py-1 text-[9px] uppercase tracking-wider text-slate-500">NOT_CONNECTED</span></div><div className="text-sm font-semibold text-slate-100">{card.title}</div><div className="mt-1 text-xs text-slate-500">{card.subtitle}</div><div className="mt-5 border-t border-jamp-line/70 pt-3 text-[11px] text-slate-500">{card.note}</div></div>)}
          </section>

          <section className="panel-card mt-7 p-6 md:p-7">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-slate-100">Проверка утверждений</div>
                <div className="mt-1 text-xs text-slate-500">Текст отправляется через BFF; секреты остаются на сервере.</div>
              </div>
              <span className="rounded-lg border border-jamp-green/30 bg-jamp-green/5 px-2.5 py-1 text-[10px] text-emerald-300">SERVER-SIDE AUTH</span>
            </div>
            <textarea
              value={inputText}
              onChange={(event) => setInputText(event.target.value)}
              placeholder="Вставьте текст для проверки утверждений…"
              rows={6}
              className="mt-5 w-full resize-y rounded-xl border border-jamp-line bg-[#080d18] p-4 text-sm leading-6 text-slate-200 outline-none transition placeholder:text-slate-600 focus:border-sky-400/50 focus:ring-2 focus:ring-sky-400/10"
            />
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={handleVerify}
                disabled={loading || !inputText.trim()}
                className="inline-flex min-w-36 items-center justify-center gap-2 rounded-xl border border-sky-400/30 bg-sky-400/10 px-5 py-3 text-sm font-semibold text-sky-200 shadow-[0_0_22px_rgba(56,189,248,0.12)] transition hover:bg-sky-400/20 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {loading && <span className="h-4 w-4 animate-spin rounded-full border-2 border-sky-200/30 border-t-sky-200" />}
                {loading ? "Проверяем…" : "Проверить"}
              </button>
              <span className="text-xs text-slate-500">Результат зависит от доступности источников и полноты извлечения.</span>
            </div>
            {requestError && (
              <div role="alert" className="mt-4 rounded-xl border border-rose-400/30 bg-rose-400/5 p-4 text-sm text-rose-300">
                Не удалось выполнить проверку: {requestError}
              </div>
            )}
            {result && (
              <div className="mt-6 space-y-4" aria-live="polite">
                {result.status === "NO_CLAIMS" && (
                  <div className="rounded-xl border border-amber-400/40 bg-amber-400/10 p-4 text-sm text-amber-200 shadow-[0_0_24px_rgba(251,191,36,0.08)]">
                    <div className="font-semibold">Утверждения не обнаружены</div>
                    <div className="mt-1">Это не доказывает отсутствие фактических утверждений в тексте.</div>
                  </div>
                )}
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-400">
                  <span>Статус: <strong className="text-slate-200">{result.status}</strong></span>
                  <span>Trace: <code className="text-sky-300">{result.trace_id}</code></span>
                </div>
                {result.system_warnings.map((warning, index) => (
                  <div key={index} className="rounded-lg border border-amber-400/20 bg-amber-400/[0.04] px-3 py-2 text-xs leading-5 text-amber-200/80">{warning}</div>
                ))}
                {result.claims.length > 0 ? (
                  <div className="grid gap-3">
                    {result.claims.map((claim) => <ClaimCard key={claim.claim_id} claim={claim} />)}
                  </div>
                ) : result.status !== "NO_CLAIMS" ? (
                  <div className="rounded-xl border border-jamp-line p-4 text-sm text-slate-400">Ответ не содержит карточек утверждений.</div>
                ) : null}
                {result.provider_errors.length > 0 && (
                  <div className="rounded-xl border border-rose-400/20 bg-rose-400/[0.04] p-4">
                    <div className="text-xs font-semibold text-rose-300">Ошибки провайдеров</div>
                    {result.provider_errors.map((item, index) => (
                      <div key={index} className="mt-2 text-xs text-slate-400">{item.provider}: {item.status} — {item.message}</div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>

          <section className="mt-7 grid gap-5 xl:grid-cols-[1.45fr_1fr]">
            <div className="panel-card p-6 md:p-7">
              <div className="flex flex-wrap items-center justify-between gap-3"><div><div className="text-sm font-semibold text-slate-100">Контур доказательств</div><div className="mt-1 text-xs text-slate-500">Как данные должны проходить через JAMP</div></div><span className="rounded-lg border border-jamp-line px-2.5 py-1 text-[10px] text-slate-500">ARCHITECTURE VIEW</span></div>
              <div className="mt-8 grid gap-3 sm:grid-cols-3">
                {[
                  { n: "01", title: "INPUT", desc: "Текст, запрос или событие", color: "border-slate-600/60" },
                  { n: "02", title: "EVIDENCE", desc: "Источники, снимки, хеши", color: "border-jamp-blue/40" },
                  { n: "03", title: "VERDICT", desc: "Проверяемый результат", color: "border-jamp-green/40" },
                ].map((step, index) => <div key={step.n} className="relative"><div className={`rounded-xl border bg-white/[0.025] p-4 ${step.color}`}><div className="text-[10px] font-semibold tracking-[0.2em] text-slate-500">{step.n} / {step.title}</div><div className="mt-4 text-sm font-medium text-slate-200">{step.desc}</div></div>{index < 2 && <div className="absolute -right-3 top-1/2 z-10 hidden -translate-y-1/2 text-slate-600 sm:block">→</div>}</div>)}
              </div>
              <div className="mt-5 rounded-xl border border-dashed border-jamp-line bg-black/10 px-4 py-3 text-xs leading-5 text-slate-500">Схема показывает целевой поток. Она не является подтверждением выполнения конкретной проверки.</div>
            </div>

            <div className="panel-card p-6 md:p-7">
              <div className="text-sm font-semibold text-slate-100">Принципы Trust Layer</div><div className="mt-1 text-xs text-slate-500">Неподвижные правила интерфейса</div>
              <div className="mt-6 space-y-5">
                {[
                  { label: "Proof over confidence", detail: "Нет доказательств — нет положительного вердикта.", color: "bg-jamp-blue" },
                  { label: "Fail-closed", detail: "UNKNOWN и INCONCLUSIVE не маскируются под PASS.", color: "bg-jamp-amber" },
                  { label: "Raw before derived", detail: "Производные выводы не заменяют исходные данные.", color: "bg-jamp-green" },
                ].map((item) => <div key={item.label} className="flex gap-3"><span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${item.color} shadow-glow`} /><div><div className="text-xs font-semibold text-slate-200">{item.label}</div><div className="mt-1 text-xs leading-5 text-slate-500">{item.detail}</div></div></div>)}
              </div>
            </div>
          </section>

          <footer className="mt-8 flex flex-col justify-between gap-2 border-t border-jamp-line/50 py-5 text-[10px] uppercase tracking-[0.13em] text-slate-600 sm:flex-row"><span>JAMP · Trust Layer</span><span>BFF integration · API responses rendered from server evidence</span></footer>
        </div>
        {active === "Модели и провайдеры" && <div className="mx-auto max-w-[1500px] px-5 py-8 md:px-10 md:py-10"><Providers /></div>}
      </main>
    </div>
  );
}

export default App;
