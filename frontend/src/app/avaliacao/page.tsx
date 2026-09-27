import clsx from "clsx";
import { backendJson } from "@/lib/backend";
import type { BiasAudit, EvaluationReport } from "@/lib/types";
import { BiasAuditView } from "@/components/bias-audit";

const pct = (v: number) => `${Math.round(v * 100)}%`;
const num = (v: number | null | undefined, digits = 1) =>
  v == null
    ? "—"
    : v.toLocaleString("pt-BR", { minimumFractionDigits: digits, maximumFractionDigits: digits });

type Row = {
  label: string;
  note: string;
  value: (r: EvaluationReport) => number | null | undefined;
  format: (v: number | null | undefined) => string;
  better: "higher" | "lower";
};

const ROWS: Row[] = [
  {
    label: "Acerto do 1º lugar",
    note: "Candidato esperado pelos sócios em primeiro",
    value: (r) => r.summary.hit_at_1,
    format: (v) => (v == null ? "—" : pct(v)),
    better: "higher",
  },
  {
    label: "MRR",
    note: "1,00 = esperado sempre em 1º",
    value: (r) => r.summary.mrr,
    format: (v) => num(v, 2),
    better: "higher",
  },
  {
    label: "Evidências confirmadas",
    note: "Citações encontradas literalmente no CV",
    value: (r) => r.summary.grounding_rate,
    format: (v) => (v == null ? "—" : pct(v)),
    better: "higher",
  },
  {
    label: "Tom executivo",
    note: "Juiz, 1 a 5",
    value: (r) => r.summary.judge_executive_tone,
    format: (v) => num(v),
    better: "higher",
  },
  {
    label: "Utilidade para decisão",
    note: "Juiz, 1 a 5",
    value: (r) => r.summary.judge_decision_usefulness,
    format: (v) => num(v),
    better: "higher",
  },
  {
    label: "Fidelidade aos CVs",
    note: "Juiz, 1 a 5",
    value: (r) => r.summary.judge_factual_consistency,
    format: (v) => num(v),
    better: "higher",
  },
  {
    label: "Tempo por análise",
    note: "Segundos, 4 candidatos",
    value: (r) => r.summary.avg_elapsed_s,
    format: (v) => (v == null ? "—" : `${num(v)} s`),
    better: "lower",
  },
  {
    label: "Custo por análise",
    note: "Preço de tabela, US$",
    value: (r) => r.summary.avg_cost_usd,
    format: (v) => (v == null ? "—" : `US$ ${num(v, 3)}`),
    better: "lower",
  },
];

function best(reports: EvaluationReport[], row: Row): number | null {
  const values = reports.map(row.value).filter((v): v is number => v != null);
  if (values.length < 2) return null;
  const target = row.better === "higher" ? Math.max(...values) : Math.min(...values);
  return values.filter((v) => v === target).length === values.length ? null : target;
}

export default async function EvaluationPage() {
  const [reports, audit] = await Promise.all([
    backendJson<EvaluationReport[]>("/v1/evaluation").then((r) => r ?? []),
    backendJson<BiasAudit>("/v1/bias-audit"),
  ]);
  const judge = reports.find((r) => r.judge_model)?.judge_model;

  return (
    <main className="mx-auto max-w-[1320px] px-4 py-10 sm:px-8 lg:py-14">
      <header className="max-w-2xl">
        <h1 className="font-display text-[30px] font-semibold tracking-[-0.03em]">
          Avaliação do modelo
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-soft">
          As vagas de referência do desafio, com o resultado esperado pelos sócios. Cada modelo
          roda o mesmo pipeline (mesma busca, mesmos prompts, mesma verificação) e é avaliado pelo
          mesmo juiz, então a diferença é só o modelo.
        </p>
      </header>

      {reports.length === 0 ? (
        <p className="mt-10 rounded-lg border border-rule bg-paper px-4 py-3 text-sm text-ink-soft">
          Nenhuma avaliação publicada ainda. Rode{" "}
          <code className="font-mono">curator evaluate --provider anthropic</code> no backend.
        </p>
      ) : (
        <>
          <section className="mt-10 overflow-x-auto rounded-xl border border-rule bg-paper">
            <table className="w-full min-w-[560px] text-sm">
              <thead>
                <tr className="border-b border-rule text-left">
                  <th className="px-5 py-4 font-medium text-ink-soft">Métrica</th>
                  {reports.map((r) => (
                    <th key={r.model} className="px-5 py-4 text-right font-mono text-xs font-medium">
                      {r.model}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-rule">
                {ROWS.map((row) => {
                  const winner = best(reports, row);
                  return (
                    <tr key={row.label}>
                      <td className="px-5 py-3">
                        <span className="font-medium">{row.label}</span>
                        <span className="block text-xs text-muted">{row.note}</span>
                      </td>
                      {reports.map((r) => {
                        const v = row.value(r);
                        return (
                          <td
                            key={r.model}
                            className={clsx(
                              "px-5 py-3 text-right font-mono text-[15px]",
                              winner !== null && v === winner && "text-verdigris",
                            )}
                          >
                            {row.format(v)}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="border-t border-rule px-5 py-3 text-xs text-muted">
              Em verde, o melhor resultado quando há diferença.
              {judge && ` Juiz: ${judge}, com rubrica de sócio sênior.`} Com dois casos, as notas do
              juiz variam cerca de 0,5 entre execuções.
            </p>
          </section>

          {audit && <BiasAuditView audit={audit} />}

          {reports.map((report) => (
            <section key={report.model} className="mt-12">
              <h2 className="font-mono text-xs uppercase tracking-[0.14em] text-muted">
                {report.model} · {new Date(report.generated_at).toLocaleString("pt-BR")}
              </h2>
              <div className="mt-4 grid gap-6 lg:grid-cols-2">
                {report.cases.map((c) => (
                  <article key={c.case_id} className="rounded-xl border border-rule bg-paper">
                    <header className="flex flex-wrap items-center gap-3 border-b border-rule px-6 py-4">
                      <span
                        className={clsx(
                          "rounded px-2 py-0.5 font-mono text-[11px] text-paper",
                          c.hit_at_1 ? "bg-verdigris" : "bg-oxide",
                        )}
                      >
                        {c.hit_at_1 ? "ACERTO" : "ERRO"}
                      </span>
                      <h3 className="font-display text-lg font-semibold">{c.title}</h3>
                    </header>
                    <div className="space-y-4 px-6 py-5">
                      <ol className="space-y-1.5 text-sm">
                        {c.report.top_candidates.map((cand) => (
                          <li key={cand.candidate_id} className="flex gap-3">
                            <span className="w-4 font-mono text-muted">{cand.rank}</span>
                            <span className={clsx(cand.candidate_id === c.expected_top && "font-medium")}>
                              {cand.name}
                            </span>
                            <span className="ml-auto font-mono text-muted">
                              {Math.round(cand.final_score)}
                            </span>
                          </li>
                        ))}
                      </ol>
                      <p className="font-serif text-[14.5px] leading-[1.65] text-ink-soft">
                        {c.report.executive_summary}
                      </p>
                      {c.judge && (
                        <p className="border-l-2 border-rule pl-3 text-[13px] leading-relaxed text-muted">
                          <span className="font-medium text-ink-soft">
                            Juiz {c.judge.executive_tone}/{c.judge.decision_usefulness}/
                            {c.judge.factual_consistency}:{" "}
                          </span>
                          {c.judge.critique}
                        </p>
                      )}
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))}
        </>
      )}
    </main>
  );
}
