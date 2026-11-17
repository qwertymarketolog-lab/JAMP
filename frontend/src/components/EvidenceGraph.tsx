import type { EvidenceGraphResponse } from "../types/api";

export function EvidenceGraph({ graph }: { graph: EvidenceGraphResponse }) {
  const verdict = graph.nodes.find((node) => node.type === "verdict");
  const evidence = graph.nodes.filter((node) => node.type === "evidence");
  const height = Math.max(180, 150 + evidence.length * 112);
  const evidenceY = (index: number) => 28 + index * 112;
  const verdictY = Math.max(28, (height - 112) / 2);
  const knownIds = new Set(graph.nodes.map((node) => node.id));
  const edges = graph.edges.filter((edge) => knownIds.has(edge.source) && knownIds.has(edge.target));
  return <div className="overflow-x-auto rounded-xl border border-jamp-line bg-[#080d18] p-3">
    <svg role="img" aria-label="Граф сохранённых доказательств" viewBox={"0 0 760 " + height} className="min-w-[680px] w-full">
      {edges.map((edge) => { const index = evidence.findIndex((node) => node.id === edge.source); if (index < 0 || edge.target !== verdict?.id) return null; const y1 = evidenceY(index) + 42; return <g key={edge.id}><line x1="390" y1={y1} x2="290" y2={verdictY + 56} stroke="#64748b" strokeWidth="1.5" /><text x="330" y={(y1 + verdictY + 56) / 2 - 5} fill="#94a3b8" fontSize="10" textAnchor="middle">{edge.relation}</text></g>; })}
      {verdict && <g><rect x="20" y={verdictY} width="270" height="112" rx="12" fill="#172554" stroke="#60a5fa" /><text x="36" y={verdictY + 23} fill="#bfdbfe" fontSize="12" fontWeight="600">verdict · {verdict.status ?? "UNKNOWN"}</text><text x="36" y={verdictY + 43} fill="#e2e8f0" fontSize="11">{(verdict.package ?? verdict.id).slice(0, 34)}</text><text x="36" y={verdictY + 66} fill="#94a3b8" fontSize="9">code SHA-256</text><text x="36" y={verdictY + 82} fill="#cbd5e1" fontSize="9">{verdict.code_hash ?? "UNKNOWN"}</text></g>}
      {evidence.map((node, index) => <g key={node.id}><rect x="390" y={evidenceY(index)} width="340" height="84" rx="12" fill="#052e2b" stroke="#34d399" /><text x="406" y={evidenceY(index) + 22} fill="#a7f3d0" fontSize="12" fontWeight="600">evidence · {node.evidence_type ?? "UNKNOWN"}</text><text x="406" y={evidenceY(index) + 43} fill="#94a3b8" fontSize="9">payload SHA-256</text><text x="406" y={evidenceY(index) + 60} fill="#cbd5e1" fontSize="9">{node.payload_hash ?? "UNKNOWN"}</text></g>)}
    </svg>
    <div className="mt-3 flex flex-wrap gap-3 text-[11px] text-slate-400"><span>{graph.nodes.length} сохранённых узлов</span><span>{edges.length} сохранённых связей</span><span>Отображаются только типы и хеши; payload не раскрывается.</span></div>
  </div>;
}
