import { useState } from "react";
import type { VerifiedClaim } from "../types/api";

const verdictStyles = {
  VERIFIED:
    "border-emerald-400/40 bg-emerald-400/[0.06] text-emerald-300 shadow-[0_0_24px_rgba(52,211,153,0.10)]",
  CONTRADICTED:
    "border-rose-400/40 bg-rose-400/[0.06] text-rose-300 shadow-[0_0_24px_rgba(251,113,133,0.10)]",
  INCONCLUSIVE:
    "border-amber-400/40 bg-amber-400/[0.06] text-amber-200 shadow-[0_0_24px_rgba(251,191,36,0.08)]",
} as const;

export function ClaimCard({ claim }: { claim: VerifiedClaim }) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const style = verdictStyles[claim.verdict] ?? verdictStyles.INCONCLUSIVE;

  return (
    <article className={`rounded-xl border bg-[#0b1220] p-4 ${style}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em] opacity-75">
            {claim.type} · {claim.claim_id}
          </div>
          <p className="mt-2 text-sm leading-6 text-slate-100">{claim.raw_text}</p>
          <div className="mt-2 text-xs text-slate-400">
            Извлечённое значение: {claim.extracted_value ?? "UNKNOWN"} {claim.unit}
          </div>
          {claim.reason && <div className="mt-2 text-xs text-amber-200/80">Причина: {claim.reason}</div>}
        </div>
        <span className="rounded-full border border-current/30 px-3 py-1 text-[10px] font-bold tracking-wider">
          {claim.verdict}
        </span>
      </div>

      <div className="mt-4 border-t border-white/10 pt-3">
        <button
          type="button"
          onClick={() => setEvidenceOpen((open) => !open)}
          aria-expanded={evidenceOpen}
          className="text-xs font-semibold text-sky-300 transition hover:text-sky-200"
        >
          {evidenceOpen ? "Скрыть Evidence" : `Evidence · ${claim.evidence.length}`}
        </button>
        {evidenceOpen && (
          <div className="mt-3 space-y-3">
            {claim.evidence.length === 0 ? (
              <p className="text-xs text-slate-500">Evidence отсутствует. Положительный вывод из этого не следует.</p>
            ) : claim.evidence.map((item, index) => (
              <div key={`${item.raw_sha256 ?? "no-hash"}-${index}`} className="rounded-lg border border-white/10 bg-black/20 p-3">
                <dl className="grid gap-3 text-xs sm:grid-cols-3">
                  <div>
                    <dt className="text-slate-500">timestamp_utc</dt>
                    <dd className="mt-1 break-all text-slate-200">{item.timestamp_utc || "UNKNOWN"}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">source</dt>
                    <dd className="mt-1 break-all text-slate-200">{item.source || "UNKNOWN"}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">raw_sha256</dt>
                    <dd className="mt-1 break-all font-mono text-slate-200">{item.raw_sha256 || "UNKNOWN"}</dd>
                  </div>
                </dl>
              </div>
            ))}
          </div>
        )}
      </div>
    </article>
  );
}
