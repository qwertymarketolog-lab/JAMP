import { useState } from "react";

type IconName = "grid" | "scan" | "store" | "telegram" | "network" | "archive" | "settings";

const navigation: { label: string; icon: IconName; section: string; active?: boolean; planned?: boolean }[] = [
  { label: "Обзор", icon: "grid", section: "Рабочее пространство", active: true },
  { label: "Проверка утверждений", icon: "scan", section: "Рабочее пространство" },
  { label: "Маркетплейс", icon: "store", section: "Экосистема", planned: true },
  { label: "Telegram", icon: "telegram", section: "Экосистема", planned: true },
  { label: "Модели и провайдеры", icon: "network", section: "Инфраструктура", planned: true },
  { label: "Evidence Vault", icon: "archive", section: "Инфраструктура", planned: true },
  { label: "Настройки", icon: "settings", section: "Система", planned: true },
];

function Icon({ name, className = "h-5 w-5" }: { name: IconName; className?: string }) {
  const paths: Record<IconName, React.ReactNode> = {
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

function App() {
  const [active, setActive] = useState("Обзор");
  const sections = [...new Set(navigation.map((item) => item.section))];

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
                    {item.planned && <span className="rounded-md border border-jamp-line px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-slate-500">Soon</span>}
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
            <span className="hidden rounded-full border border-jamp-amber/20 bg-jamp-amber/5 px-3 py-1.5 text-[11px] text-jamp-amber sm:inline-flex">STATIC PREVIEW · NO LIVE DATA</span>
            <button className="rounded-xl border border-jamp-line bg-jamp-panel px-3 py-2 text-xs text-slate-300">RU <span className="ml-1 text-slate-500">⌄</span></button>
          </div>
        </header>

        <div className="mx-auto max-w-[1500px] px-5 py-8 md:px-10 md:py-10">
          <div className="mb-8 flex flex-col justify-between gap-5 xl:flex-row xl:items-end">
            <div><div className="mb-3 inline-flex items-center gap-2 rounded-full border border-jamp-blue/20 bg-jamp-blue/5 px-3 py-1.5 text-[10px] font-semibold uppercase tracking-[0.18em] text-sky-300"><span className="h-1.5 w-1.5 rounded-full bg-jamp-blue" /> Evidence Infrastructure</div><h2 className="max-w-3xl text-3xl font-semibold tracking-tight text-white md:text-4xl">От утверждения —<br className="hidden sm:block" /> к проверяемому доказательству.</h2><p className="mt-3 max-w-2xl text-sm leading-6 text-slate-400">Единое рабочее пространство для проверки фактов, происхождения данных и будущих продуктов экосистемы JAMP.</p></div>
            <div className="rounded-xl border border-jamp-line bg-jamp-panel/70 px-4 py-3"><div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Состояние интерфейса</div><div className="mt-1 flex items-center gap-2 text-sm font-medium text-jamp-amber"><span className="h-2 w-2 rounded-full bg-jamp-amber" /> Каркас · интеграция впереди</div></div>
          </div>

          <section className="grid gap-4 md:grid-cols-2 2xl:grid-cols-4">
            {[
              { title: "Проверка утверждений", subtitle: "Claim verification", icon: "scan" as IconName, accent: "text-jamp-blue", note: "API существует · UI не подключён" },
              { title: "Evidence Vault", subtitle: "Источники и происхождение", icon: "archive" as IconName, accent: "text-jamp-green", note: "Экран запланирован" },
              { title: "Маркетплейс", subtitle: "Продукты и интеграции", icon: "store" as IconName, accent: "text-violet-300", note: "Продуктовый контур запланирован" },
              { title: "Telegram", subtitle: "Бот и каналы взаимодействия", icon: "telegram" as IconName, accent: "text-sky-300", note: "Интеграционный экран запланирован" },
            ].map((card) => <div key={card.title} className="panel-card group p-5"><div className="mb-5 flex items-start justify-between"><div className={`rounded-xl border border-white/5 bg-white/[0.04] p-3 ${card.accent}`}><Icon name={card.icon} className="h-5 w-5" /></div><span className="rounded-full border border-jamp-line px-2 py-1 text-[9px] uppercase tracking-wider text-slate-500">Planned</span></div><div className="text-sm font-semibold text-slate-100">{card.title}</div><div className="mt-1 text-xs text-slate-500">{card.subtitle}</div><div className="mt-5 border-t border-jamp-line/70 pt-3 text-[11px] text-slate-500">{card.note}</div></div>)}
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

          <footer className="mt-8 flex flex-col justify-between gap-2 border-t border-jamp-line/50 py-5 text-[10px] uppercase tracking-[0.13em] text-slate-600 sm:flex-row"><span>JAMP · Trust Layer</span><span>Frontend skeleton · No API calls · No live metrics</span></footer>
        </div>
      </main>
    </div>
  );
}

export default App;
