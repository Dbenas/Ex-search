"use client";

import { useState } from "react";
import clsx from "clsx";
import { Check, Copy } from "lucide-react";
import type { RequirementCoverage, SearchPlan } from "@/lib/types";

const STATUS: Record<RequirementCoverage["status"], { label: string; dot: string }> = {
  lider: { label: "Coberto pelo 1º colocado", dot: "bg-verdigris" },
  outros: { label: "Só em perfis secundários", dot: "bg-amber" },
  ninguem: { label: "Sem evidência na base", dot: "bg-oxide" },
};

export function CoverageMap({ coverage }: { coverage: RequirementCoverage[] }) {
  if (!coverage.length) return null;
  const uncovered = coverage.filter((c) => c.status !== "lider").length;

  return (
    <section aria-labelledby="coverage-title" className="rounded-xl border border-rule bg-paper px-5 py-6 sm:px-7">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 id="coverage-title" className="font-display text-[17px] font-semibold tracking-[-0.01em]">
          Cobertura dos requisitos essenciais
        </h3>
        <p className="text-xs text-muted">Calculada só com evidências confirmadas nos currículos</p>
      </div>
      <p className="mt-1 text-sm text-ink-soft">
        {uncovered === 0
          ? "O 1º colocado tem evidência para todos os requisitos essenciais."
          : `${uncovered} de ${coverage.length} requisitos essenciais não estão cobertos pelo 1º colocado.`}
      </p>
      <ul className="mt-4 divide-y divide-rule">
        {coverage.map((c) => (
          <li key={c.requirement} className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2.5 text-sm">
            <span className={clsx("size-2 shrink-0 rounded-full", STATUS[c.status].dot)} aria-hidden />
            <span className="min-w-0 flex-1">
              {c.requirement}
              <span className="ml-2 font-mono text-[10px] uppercase tracking-wider text-muted">
                {c.kind === "hard" ? "técnico" : "comportamental"}
              </span>
            </span>
            <span className="text-xs text-muted">
              {STATUS[c.status].label}
              {c.status === "outros" && `: ${c.covered_by.join(", ")}`}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function CopyLine({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <li className="group flex items-start gap-2 rounded-md bg-ink px-3 py-2.5">
      <code className="flex-1 break-words font-mono text-[12.5px] leading-relaxed text-paper/90">{text}</code>
      <button
        type="button"
        onClick={async () => {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        }}
        className="shrink-0 rounded p-1 text-paper/60 hover:text-paper"
        aria-label="Copiar busca"
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      </button>
    </li>
  );
}

export function SearchPlanView({ plan }: { plan: SearchPlan }) {
  return (
    <section
      id="plano-de-busca"
      aria-labelledby="plan-title"
      className="scroll-mt-24 rounded-xl border border-ink/80 bg-paper"
    >
      <header className="border-b border-rule px-5 py-5 sm:px-7">
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">Ampliar o mapeamento</p>
        <h3 id="plan-title" className="mt-1 font-display text-[21px] font-semibold tracking-[-0.02em]">
          Plano de busca
        </h3>
        <p className="mt-2 max-w-[70ch] font-serif text-[15.5px] leading-[1.7] text-ink-soft">{plan.diagnosis}</p>
      </header>

      <div className="grid gap-px bg-rule md:grid-cols-3">
        {plan.target_profiles.map((t) => (
          <article key={t.archetype} className="bg-paper px-5 py-5 sm:px-6">
            <h4 className="font-display text-[15px] font-semibold leading-snug">{t.archetype}</h4>
            <p className="mt-2 text-[13.5px] leading-relaxed text-ink-soft">{t.rationale}</p>
            <p className="mt-3 text-xs leading-relaxed text-muted">
              <span className="font-medium text-amber">Trade-off: </span>
              {t.trade_off}
            </p>
          </article>
        ))}
      </div>

      <div className="grid gap-8 border-t border-rule px-5 py-6 sm:px-7 lg:grid-cols-2">
        <div className="space-y-6">
          <div>
            <h4 className="text-xs font-medium text-ink-soft">Buscas para o LinkedIn Recruiter</h4>
            <ul className="mt-2 space-y-2">
              {plan.boolean_queries.map((q) => (
                <CopyLine key={q} text={q} />
              ))}
            </ul>
          </div>
          <div>
            <h4 className="text-xs font-medium text-ink-soft">Onde procurar</h4>
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {plan.source_segments.map((s) => (
                <li key={s} className="rounded border border-rule px-2 py-1 text-xs text-ink-soft">
                  {s}
                </li>
              ))}
            </ul>
          </div>
        </div>
        <div>
          <h4 className="text-xs font-medium text-ink-soft">Perguntas de triagem</h4>
          <ol className="mt-2 space-y-2.5 text-[14px] leading-relaxed">
            {plan.screening_questions.map((q, i) => (
              <li key={q} className="flex gap-3">
                <span className="font-mono text-xs leading-6 text-muted">{i + 1}</span>
                {q}
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
