import type { ProviderRecord, ProviderStatus } from "../types/providers";

const snapshotAt = "17.11.2026 21:56 UTC";

const providers: ProviderRecord[] = [
  {
    id: "moex",
    name: "MOEX",
    status: "ONLINE",
    description: "Один live E2E сценарий SBER завершился HTTP 200; это не подтверждает доступность всех инструментов MOEX.",
    evidence: {
      summary: "Docker Smoke: live SBER → MOEX verification; завершён успешно менее чем за 24 часа до снимка.",
      observedAt: "2026-11-17T10:11:58Z",
      referenceLabel: "Run #44062378956 · Job #133967269250",
      referenceUrl: "https://github.com/qwertymarketolog-lab/JAMP/actions/runs/44062378956",
      artifactId: "14317759287",
    },
  },
  {
    id: "anymodel",
    name: "AnyModel",
    status: "UNKNOWN",
    description: "Последний подтверждённый HTTP 200 устарел относительно правила свежести 24 часа.",
    evidence: {
      summary: "RAW HTTP response: 200 OK, модель ag/claude-sonnet-4-6, ответ OK. Зафиксировано 16.11.2026 04:14:52 UTC; на момент снимка старше 24 часов.",
      observedAt: "2026-11-16T04:14:52Z",
      referenceLabel: "Artifact #14197510755 · исторический транспортный факт",
      artifactId: "14197510755",
    },
  },
  {
    id: "coingecko",
    name: "CoinGecko",
    status: "UNKNOWN",
    description: "Есть только offline/mock E2E; тестовые fixtures не подтверждают live-доступность сервиса.",
    evidence: {
      summary: "PR #593 явно фиксирует offline_mock_only и monkeypatched provider calls; live-запрос не выполнялся.",
      observedAt: "2026-11-15T16:16:26Z",
      referenceLabel: "PR #593 · offline experiment",
      referenceUrl: "https://github.com/qwertymarketolog-lab/JAMP/pull/593",
    },
  },
  {
    id: "beget",
    name: "Beget",
    status: "NOT_CONNECTED",
    description: "Интеграция не реализована; задача находится в бэклоге.",
    evidence: {
      summary: "Нет подтверждённого подключения и API-ключа в рамках текущего контура.",
      referenceLabel: "Issue #616 · BACKLOG / HOLD",
      referenceUrl: "https://github.com/qwertymarketolog-lab/JAMP/issues/616",
    },
  },
  {
    id: "openrouter",
    name: "OpenRouter",
    status: "UNKNOWN",
    description: "Наличие адаптера не доказывает текущую доступность; подтверждённого live-запроса для этого снимка нет.",
    evidence: {
      summary: "Текущий статус соединения не проверялся; намеренно не выводится из наличия кода адаптера.",
      referenceLabel: "Live evidence отсутствует",
    },
  },
  {
    id: "telegram",
    name: "Telegram",
    status: "NOT_CONNECTED",
    description: "Реализация tenant binding и рабочего delivery-контура не завершена.",
    evidence: {
      summary: "ADR зафиксирован как концепция; implementation остаётся HOLD до выполнения архитектурных prerequisites.",
      referenceLabel: "PR #615 · ADR / implementation HOLD",
      referenceUrl: "https://github.com/qwertymarketolog-lab/JAMP/pull/615",
    },
  },
];

const statusStyles: Record<ProviderStatus, string> = {
  ONLINE: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  DEGRADED: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  OFFLINE: "border-rose-400/30 bg-rose-400/10 text-rose-300",
  NOT_CONNECTED: "border-slate-500/40 bg-slate-500/10 text-slate-300",
  UNKNOWN: "border-amber-400/30 bg-amber-400/5 text-amber-200",
};

function StatusBadge({ status }: { status: ProviderStatus }) {
  return <span className={`inline-flex rounded-full border px-3 py-1 text-[10px] font-semibold tracking-wide ${statusStyles[status]}`}>{status}</span>;
}

export function Providers() {
  return (
    <section aria-label="Модели и провайдеры" className="space-y-6">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
        <div>
          <div className="text-xs uppercase tracking-[0.18em] text-sky-300">Infrastructure · Evidence snapshot</div>
          <h2 className="mt-2 text-2xl font-semibold text-white">Модели и провайдеры</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">Статический снимок доказательств. Компонент не выполняет health-check и не выдаёт наличие адаптера за доступность сервиса.</p>
        </div>
        <div className="rounded-xl border border-jamp-line bg-jamp-panel/70 px-4 py-3">
          <div className="text-[10px] uppercase tracking-wide text-slate-500">Снимок состояния</div>
          <div className="mt-1 text-sm font-medium text-slate-200">{snapshotAt}</div>
        </div>
      </div>

      <div className="overflow-x-auto rounded-2xl border border-jamp-line bg-jamp-panel/60">
        <table className="w-full min-w-[760px] border-collapse text-left">
          <thead className="border-b border-jamp-line bg-black/10 text-[10px] uppercase tracking-[0.14em] text-slate-500">
            <tr><th className="px-5 py-4 font-semibold">Провайдер</th><th className="px-5 py-4 font-semibold">Статус</th><th className="px-5 py-4 font-semibold">Основание / evidence</th></tr>
          </thead>
          <tbody className="divide-y divide-jamp-line/70">
            {providers.map((provider) => (
              <tr key={provider.id} data-provider={provider.id} className="align-top">
                <th scope="row" className="px-5 py-5 text-sm font-semibold text-slate-100">{provider.name}</th>
                <td className="px-5 py-5"><StatusBadge status={provider.status} /></td>
                <td className="px-5 py-5">
                  <p className="max-w-2xl text-sm leading-5 text-slate-300">{provider.description}</p>
                  <p className="mt-2 max-w-2xl text-xs leading-5 text-slate-500">{provider.evidence.summary}</p>
                  <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-500">
                    {provider.evidence.observedAt && <time dateTime={provider.evidence.observedAt}>{provider.evidence.observedAt}</time>}
                    {provider.evidence.referenceUrl
                      ? <a className="text-sky-300 underline decoration-sky-300/30 underline-offset-2" href={provider.evidence.referenceUrl} target="_blank" rel="noreferrer">{provider.evidence.referenceLabel}</a>
                      : <span>{provider.evidence.referenceLabel}</span>}
                    {provider.evidence.artifactId && <span>Artifact ID: {provider.evidence.artifactId}</span>}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="rounded-xl border border-amber-400/20 bg-amber-400/[0.04] px-4 py-3 text-xs leading-5 text-amber-100/80">
        ONLINE относится только к доказательству в указанном временном срезе. Для подтверждения состояния здесь и сейчас нужен свежий CI (&lt; 24 ч) или live health-check; этот статический экран не обновляет статусы автоматически.
      </p>
    </section>
  );
}
