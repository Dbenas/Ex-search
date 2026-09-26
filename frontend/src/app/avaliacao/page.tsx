import clsx from "clsx";
import { backendJson } from "@/lib/backend";
import type { EvaluationReport } from "@/lib/types";

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

function Metric({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="rounded-xl border border-rule bg-paper p-5">
      <dt className="text-xs font-medium text-ink-soft">{label}</dt>
      <dd className="mt-2 font-mono text-[30px] font-medium leading-none tracking-[-0.03em]">
        {value}
      </dd>
      <p className="mt-2 text-xs leading-relaxed text-muted">{note}</p>
    </div>
  );
}

export default async function EvaluationPage() {
  const report = await backendJson<EvaluationReport>("/v1/evaluation");

  return (
    <main className="mx-auto max-w-[1320px] px-4 py-10 sm:px-8 lg:py-14">
      <header className="max-w-2xl">
        <h1 className="font-display text-[30px] font-semibold tracking-[-0.03em]">
          Avaliação do modelo
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-soft">
          As vagas de referência do desafio, com o resultado esperado pelos sócios. Três camadas: o
          ranking acerta? As afirmações existem no currículo? O parecer está pronto para o cliente?
        </p>
      </header>

      {report === null ? (
        <p className="mt-10 rounded-lg border border-rule bg-paper px-4 py-3 text-sm text-ink-soft">
          Nenhuma avaliação publicada ainda. Rode <code className="font-mono">curator evaluate</code>{" "}
          no backend para gerar o relatório.
        </p>
      ) : (
        <>
          <dl className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric
              label="Acerto do 1º lugar"
              value={pct(report.summary.hit_at_1)}
              note="Candidato esperado pelos sócios aparece em primeiro."
            />
            <Metric
              label="MRR"
              value={report.summary.mrr.toFixed(2)}
              note="Posição média do candidato esperado (1,00 = sempre em 1º)."
            />
            <Metric
              label="Evidências confirmadas"
              value={pct(report.summary.grounding_rate)}
              note="Citações do modelo encontradas literalmente nos currículos."
            />
            <Metric
              label="Tom executivo (juiz)"
              value={report.summary.judge_executive_tone?.toFixed(1) ?? "—"}
              note="Nota de 1 a 5 atribuída por um revisor automático com rubrica de sócio."
            />
          </dl>

          <div className="mt-10 space-y-6">
            {report.cases.map((c) => (
              <article key={c.case_id} className="rounded-xl border border-rule bg-paper">
                <header className="flex flex-wrap items-center gap-3 border-b border-rule px-6 py-4">
                  <span
                    className={clsx(
                      "rounded px-2 py-0.5 font-mono text-[11px]",
                      c.hit_at_1 ? "bg-verdigris text-paper" : "bg-oxide text-paper",
                    )}
                  >
                    {c.hit_at_1 ? "ACERTO" : "ERRO"}
                  </span>
                  <h2 className="font-display text-lg font-semibold">{c.title}</h2>
                  <span className="ml-auto font-mono text-xs text-muted">
                    evidências {pct(c.grounding_rate)}
                  </span>
                </header>
                <div className="grid gap-6 px-6 py-5 md:grid-cols-2">
                  <div>
                    <p className="text-xs font-medium text-ink-soft">Ranking produzido</p>
                    <ol className="mt-2 space-y-1.5 text-sm">
                      {c.report.top_candidates.map((cand) => (
                        <li key={cand.candidate_id} className="flex gap-3">
                          <span className="w-4 font-mono text-muted">{cand.rank}</span>
                          <span
                            className={clsx(cand.candidate_id === c.expected_top && "font-medium")}
                          >
                            {cand.name}
                          </span>
                          <span className="ml-auto font-mono text-muted">
                            {Math.round(cand.final_score)}
                          </span>
                        </li>
                      ))}
                    </ol>
                    <p className="mt-4 font-serif text-[14.5px] leading-[1.65] text-ink-soft">
                      {c.report.executive_summary}
                    </p>
                  </div>
                  {c.judge && (
                    <div>
                      <p className="text-xs font-medium text-ink-soft">Revisão do juiz</p>
                      <dl className="mt-2 grid grid-cols-3 gap-2 text-center">
                        {(
                          [
                            ["Tom", c.judge.executive_tone],
                            ["Utilidade", c.judge.decision_usefulness],
                            ["Fidelidade", c.judge.factual_consistency],
                          ] as const
                        ).map(([label, score]) => (
                          <div key={label} className="rounded-md bg-mist py-2">
                            <dd className="font-mono text-lg">{score}/5</dd>
                            <dt className="text-[11px] text-muted">{label}</dt>
                          </div>
                        ))}
                      </dl>
                      <p className="mt-3 text-sm leading-relaxed text-ink-soft">{c.judge.critique}</p>
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>

          <p className="mt-6 font-mono text-[11px] text-muted">
            gerado em {new Date(report.generated_at).toLocaleString("pt-BR")} · modelo {report.model}
          </p>
        </>
      )}
    </main>
  );
}
