import type { MatchReport } from "@/lib/types";
import { CandidateDossier } from "./candidate-dossier";

function Chips({ items, tone }: { items: { name: string; importance: string }[]; tone: string }) {
  return (
    <ul className="flex flex-wrap gap-1.5">
      {items.map((r) => (
        <li
          key={r.name}
          title={r.importance === "essencial" ? "Essencial" : "Desejável"}
          className={
            r.importance === "essencial"
              ? `rounded px-2 py-0.5 text-xs ${tone}`
              : "rounded border border-rule px-2 py-0.5 text-xs text-ink-soft"
          }
        >
          {r.name}
        </li>
      ))}
    </ul>
  );
}

export function MatchReportView({ report }: { report: MatchReport }) {
  const { job, metadata } = report;

  return (
    <div className="space-y-6">
      <section className="animate-rise rounded-xl border border-rule bg-paper px-5 py-6 sm:px-7">
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
          Mandato · {job.role_title}
        </p>
        <p className="mt-2 font-display text-[21px] font-medium leading-snug tracking-[-0.015em]">
          {job.mandate}
        </p>
        <p className="mt-1.5 text-sm text-muted">{job.company_context}</p>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <div>
            <p className="mb-2 text-xs font-medium text-ink-soft">Requisitos técnicos</p>
            <Chips items={job.hard_requirements} tone="bg-ink text-paper" />
          </div>
          <div>
            <p className="mb-2 text-xs font-medium text-ink-soft">Requisitos comportamentais</p>
            <Chips items={job.soft_requirements} tone="bg-ink-soft text-paper" />
          </div>
        </div>
        <p className="mt-3 text-[11px] text-muted">
          Preenchido: essencial · contorno: desejável
        </p>
      </section>

      <section className="animate-rise border-l-2 border-ink py-1 pl-5 sm:pl-7" style={{ animationDelay: "60ms" }}>
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
          Leitura do shortlist
        </p>
        <p className="mt-2 max-w-[68ch] font-serif text-[18px] leading-[1.65]">
          {report.executive_summary}
        </p>
        {report.next_steps.length > 0 && (
          <div className="mt-5">
            <p className="text-xs font-medium text-ink-soft">Próximos passos sugeridos</p>
            <ol className="mt-2 max-w-[72ch] space-y-1.5 text-[14px] leading-relaxed text-ink-soft">
              {report.next_steps.map((step, i) => (
                <li key={i} className="flex gap-3">
                  <span className="font-mono text-xs leading-6 text-muted">{i + 1}</span>
                  {step}
                </li>
              ))}
            </ol>
          </div>
        )}
      </section>

      {report.top_candidates.map((c, i) => (
        <CandidateDossier key={c.candidate_id} candidate={c} runId={metadata.run_id} index={i + 1} />
      ))}

      {report.also_considered.length > 0 && (
        <section className="rounded-xl border border-dashed border-rule px-5 py-5 sm:px-7">
          <h3 className="text-sm font-medium">Também avaliados</h3>
          <ul className="mt-3 divide-y divide-rule">
            {report.also_considered.map((c) => (
              <li key={c.candidate_id} className="flex gap-4 py-3 text-sm">
                <span className="w-10 shrink-0 font-mono text-muted">{Math.round(c.final_score)}</span>
                <span>
                  <span className="font-medium">{c.name}</span>
                  <span className="block text-ink-soft">{c.reason}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer className="flex flex-wrap gap-x-6 gap-y-1 px-1 font-mono text-[11px] text-muted">
        <span>modelo {metadata.model}</span>
        <span>{metadata.candidates_screened} perfis na base</span>
        <span>{metadata.llm_calls} chamadas ao modelo</span>
        <span>{metadata.pii_redactions} dado(s) pessoal(is) removido(s) da vaga</span>
        <span>{(metadata.elapsed_ms / 1000).toFixed(1)}s</span>
        <span>execução {metadata.run_id}</span>
      </footer>
    </div>
  );
}
