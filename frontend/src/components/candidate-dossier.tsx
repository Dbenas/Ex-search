"use client";

import { useState } from "react";
import clsx from "clsx";
import { CircleAlert, CircleCheck, MessageSquareText, ThumbsDown, ThumbsUp } from "lucide-react";
import type { RankedCandidate, Recommendation } from "@/lib/types";
import { MarkedProfile } from "./marked-profile";

const RECOMMENDATION: Record<Recommendation, { label: string; className: string }> = {
  avancar: { label: "Avançar", className: "bg-verdigris text-paper" },
  avancar_com_ressalvas: { label: "Avançar com ressalvas", className: "bg-amber-wash text-amber" },
  nao_priorizar: { label: "Não priorizar", className: "bg-mist text-muted" },
};

const DIMENSIONS = [
  { key: "hard_skills", label: "Hard skills" },
  { key: "soft_skills", label: "Soft skills" },
  { key: "context_fit", label: "Fit de contexto" },
] as const;

type Props = { candidate: RankedCandidate; runId: string; index: number };

export function CandidateDossier({ candidate, runId, index }: Props) {
  const [activeEvidence, setActiveEvidence] = useState<number | null>(null);
  const [tab, setTab] = useState<"evidence" | "interview">("evidence");
  const rec = RECOMMENDATION[candidate.recommendation];
  const verified = candidate.evidence.filter((e) => e.verified).length;

  return (
    <article
      className="animate-rise overflow-hidden rounded-xl border border-rule bg-paper"
      style={{ animationDelay: `${index * 90}ms` }}
      aria-labelledby={`cand-${candidate.candidate_id}`}
    >
      <header className="flex flex-wrap items-start gap-x-5 gap-y-3 border-b border-rule px-5 py-5 sm:px-7">
        <span className="font-mono text-[40px] font-medium leading-none tracking-[-0.04em] text-ink/15">
          {candidate.rank}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3
              id={`cand-${candidate.candidate_id}`}
              className="font-display text-[22px] font-semibold tracking-[-0.02em]"
            >
              {candidate.name}
            </h3>
            <span className={clsx("rounded px-2 py-0.5 text-[11px] font-medium", rec.className)}>
              {rec.label}
            </span>
          </div>
          <p className="mt-0.5 text-sm text-muted">{candidate.current_role}</p>
        </div>
        <div className="text-right">
          <p className="font-mono text-[28px] font-medium leading-none tracking-[-0.03em]">
            {Math.round(candidate.final_score)}
            <span className="text-sm text-muted">/100</span>
          </p>
          <p
            className="mt-1 cursor-help text-[11px] text-muted underline decoration-dotted underline-offset-2"
            title="40% hard skills, 30% soft skills, 30% fit de contexto. Até 25% de desconto quando parte das evidências citadas não é encontrada no currículo."
          >
            aderência ponderada
          </p>
        </div>
      </header>

      <div className="grid gap-0 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
        <section className="space-y-5 px-5 py-6 sm:px-7">
          <p className="font-display text-[17px] font-medium leading-snug tracking-[-0.01em]">
            {candidate.headline}
          </p>
          <p className="font-serif text-[15.5px] leading-[1.75] text-ink-soft">{candidate.analysis}</p>

          <dl className="space-y-3 pt-1">
            {DIMENSIONS.map(({ key, label }) => {
              const dim = candidate.scores[key];
              return (
                <div key={key} className="group">
                  <div className="flex items-baseline justify-between text-xs">
                    <dt className="font-medium text-ink-soft">{label}</dt>
                    <dd className="font-mono text-ink">{dim.score}/10</dd>
                  </div>
                  <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-mist">
                    <div
                      className="h-full rounded-full bg-ink transition-[width] duration-700"
                      style={{ width: `${dim.score * 10}%` }}
                    />
                  </div>
                  <p className="mt-1.5 text-xs leading-relaxed text-muted">{dim.rationale}</p>
                </div>
              );
            })}
          </dl>
        </section>

        <section className="border-t border-rule bg-mist/40 px-5 py-6 sm:px-7 lg:border-l lg:border-t-0">
          <div role="tablist" className="mb-4 flex gap-4 border-b border-rule text-sm">
            {(
              [
                ["evidence", `Evidências · ${verified}/${candidate.evidence.length}`],
                ["interview", "Pontos para entrevista"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                role="tab"
                aria-selected={tab === id}
                onClick={() => setTab(id)}
                className={clsx(
                  "-mb-px border-b-2 pb-2 transition-colors",
                  tab === id ? "border-ink text-ink" : "border-transparent text-muted hover:text-ink",
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === "evidence" ? (
            <div className="space-y-5">
              <MarkedProfile
                text={candidate.profile_text}
                evidence={candidate.evidence}
                active={activeEvidence}
              />
              <ul className="space-y-2">
                {candidate.evidence.map((e, i) => (
                  <li
                    key={i}
                    onMouseEnter={() => setActiveEvidence(i)}
                    onMouseLeave={() => setActiveEvidence(null)}
                    onFocus={() => setActiveEvidence(i)}
                    onBlur={() => setActiveEvidence(null)}
                    tabIndex={0}
                    className={clsx(
                      "flex gap-2.5 rounded-md border px-3 py-2 text-[13px] leading-snug outline-none",
                      e.verified
                        ? "border-rule bg-paper hover:border-verdigris focus:border-verdigris"
                        : "border-amber/30 bg-amber-wash/60",
                    )}
                  >
                    {e.verified ? (
                      <CircleCheck className="mt-0.5 size-4 shrink-0 text-verdigris" aria-label="Verificada" />
                    ) : (
                      <CircleAlert className="mt-0.5 size-4 shrink-0 text-amber" aria-label="Não verificada" />
                    )}
                    <span>
                      <span className="font-medium">{e.requirement}</span>
                      <span className="text-ink-soft"> — {e.claim}</span>
                      {!e.verified && (
                        <span className="mt-1 block text-xs text-amber">
                          Trecho não encontrado no currículo; descartado do parecer.
                        </span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <div className="space-y-5 text-[13.5px] leading-relaxed">
              <div>
                <h4 className="font-mono text-[11px] uppercase tracking-[0.12em] text-muted">
                  Aprofundar
                </h4>
                <ul className="mt-2 space-y-2">
                  {candidate.interview_focus.map((q, i) => (
                    <li key={i} className="flex gap-2">
                      <MessageSquareText className="mt-0.5 size-4 shrink-0 text-ink-soft" aria-hidden />
                      {q}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h4 className="font-mono text-[11px] uppercase tracking-[0.12em] text-muted">
                  Sem evidência no perfil
                </h4>
                <ul className="mt-2 space-y-1.5 text-ink-soft">
                  {candidate.gaps.length ? (
                    candidate.gaps.map((g, i) => <li key={i}>· {g}</li>)
                  ) : (
                    <li>Nenhuma lacuna relevante para o mandato.</li>
                  )}
                </ul>
              </div>
            </div>
          )}
        </section>
      </div>

      <Feedback runId={runId} candidateId={candidate.candidate_id} />
    </article>
  );
}

function Feedback({ runId, candidateId }: { runId: string; candidateId: string }) {
  const [sent, setSent] = useState<"agree" | "disagree" | null>(null);

  async function send(verdict: "agree" | "disagree") {
    setSent(verdict);
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: runId, candidate_id: candidateId, verdict }),
    }).catch(() => setSent(null));
  }

  return (
    <footer className="flex flex-wrap items-center gap-3 border-t border-rule px-5 py-3 text-xs text-muted sm:px-7">
      {sent ? (
        <span>Avaliação registrada. Ela alimenta a métrica de concordância com os sócios.</span>
      ) : (
        <>
          <span>Esta indicação faz sentido para o mandato?</span>
          <button
            onClick={() => send("agree")}
            className="inline-flex items-center gap-1.5 rounded-md border border-rule bg-paper px-2.5 py-1 text-ink-soft hover:border-verdigris hover:text-verdigris"
          >
            <ThumbsUp className="size-3.5" aria-hidden /> Concordo
          </button>
          <button
            onClick={() => send("disagree")}
            className="inline-flex items-center gap-1.5 rounded-md border border-rule bg-paper px-2.5 py-1 text-ink-soft hover:border-oxide hover:text-oxide"
          >
            <ThumbsDown className="size-3.5" aria-hidden /> Discordo
          </button>
        </>
      )}
    </footer>
  );
}
