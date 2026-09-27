"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import { ArrowDown, ArrowUp, RotateCcw } from "lucide-react";
import { leadershipShare, rerank } from "@/lib/ranking";
import type { CandidateScores, Dimension, ScoreWeights } from "@/lib/types";

const DIMENSIONS: { key: Dimension; label: string }[] = [
  { key: "hard_skills", label: "Hard skills" },
  { key: "soft_skills", label: "Soft skills" },
  { key: "context_fit", label: "Fit de contexto" },
];

const PRESETS: { label: string; weights: ScoreWeights }[] = [
  { label: "Trajetória técnica", weights: { hard_skills: 0.6, soft_skills: 0.2, context_fit: 0.2 } },
  { label: "Cultura e momento", weights: { hard_skills: 0.2, soft_skills: 0.4, context_fit: 0.4 } },
  { label: "Equilibrado", weights: { hard_skills: 1 / 3, soft_skills: 1 / 3, context_fit: 1 / 3 } },
];

const toPercent = (w: ScoreWeights): ScoreWeights => {
  const total = w.hard_skills + w.soft_skills + w.context_fit || 1;
  return {
    hard_skills: Math.round((w.hard_skills / total) * 100),
    soft_skills: Math.round((w.soft_skills / total) * 100),
    context_fit: Math.round((w.context_fit / total) * 100),
  };
};

const sameWeights = (a: ScoreWeights, b: ScoreWeights) => {
  const pa = toPercent(a);
  const pb = toPercent(b);
  return DIMENSIONS.every(({ key }) => pa[key] === pb[key]);
};

type Props = {
  assessed: CandidateScores[];
  reportWeights: ScoreWeights;
  onRerun: (weights: ScoreWeights) => void;
  rerunning: boolean;
};

export function WeightTuner({ assessed, reportWeights, onRerun, rerunning }: Props) {
  const [weights, setWeights] = useState<ScoreWeights>(() => toPercent(reportWeights));
  const originalRank = useMemo(
    () => new Map(assessed.map((c, i) => [c.candidate_id, i + 1])),
    [assessed],
  );
  const simulated = useMemo(() => rerank(assessed, weights), [assessed, weights]);
  const share = useMemo(() => leadershipShare(assessed), [assessed]);
  const changed = !sameWeights(weights, reportWeights);
  const leader = assessed[0];
  const leaderShare = leader ? (share.get(leader.candidate_id) ?? 0) : 0;
  const pct = toPercent(weights);

  if (assessed.length < 2) return null;

  return (
    <section
      aria-labelledby="weights-title"
      className="animate-rise rounded-xl border border-rule bg-paper"
      style={{ animationDelay: "90ms" }}
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-rule px-5 py-4 sm:px-7">
        <h3 id="weights-title" className="font-display text-[17px] font-semibold tracking-[-0.01em]">
          E se o critério fosse outro?
        </h3>
        <p className="text-xs text-muted">
          Simulação instantânea com as notas já atribuídas. Nenhuma nova chamada ao modelo.
        </p>
      </header>

      <div className="grid gap-8 px-5 py-6 sm:px-7 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="space-y-5">
          {DIMENSIONS.map(({ key, label }) => (
            <label key={key} className="block">
              <span className="flex items-baseline justify-between text-sm">
                <span className="font-medium">{label}</span>
                <span className="font-mono text-xs text-ink-soft">{pct[key]}%</span>
              </span>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={weights[key]}
                onChange={(e) => setWeights({ ...weights, [key]: Number(e.target.value) })}
                className="mt-2 w-full accent-[var(--ink)]"
              />
            </label>
          ))}

          <div className="flex flex-wrap gap-2 text-xs">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => setWeights(toPercent(p.weights))}
                className="rounded-full border border-rule px-2.5 py-1 text-ink-soft hover:border-ink hover:text-ink"
              >
                {p.label}
              </button>
            ))}
            <button
              type="button"
              onClick={() => setWeights(toPercent(reportWeights))}
              className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-muted hover:text-ink"
            >
              <RotateCcw className="size-3" aria-hidden /> Critério do parecer
            </button>
          </div>

          {leader && (
            <p className="rounded-lg bg-mist px-4 py-3 text-[13.5px] leading-relaxed text-ink-soft">
              <span className="font-mono text-[15px] font-medium text-ink">
                {Math.round(leaderShare * 100)}%
              </span>{" "}
              das combinações de pesos mantêm <span className="font-medium text-ink">{leader.name}</span>{" "}
              em primeiro.{" "}
              {leaderShare >= 0.8
                ? "A indicação não depende do critério escolhido."
                : leaderShare >= 0.5
                  ? "A indicação é sólida, mas sensível ao critério; vale alinhar prioridades com o cliente."
                  : "A indicação depende do critério; a decisão é do sócio, não do modelo."}
            </p>
          )}
        </div>

        <div>
          <ol className="divide-y divide-rule rounded-lg border border-rule">
            {simulated.map((c, i) => {
              const before = originalRank.get(c.candidate_id) ?? i + 1;
              const delta = before - (i + 1);
              return (
                <li key={c.candidate_id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <span className="w-4 font-mono text-muted">{i + 1}</span>
                  <span className="flex-1 font-medium">{c.name}</span>
                  <span
                    className={clsx(
                      "inline-flex w-10 items-center justify-end gap-0.5 font-mono text-xs",
                      delta > 0 && "text-verdigris",
                      delta < 0 && "text-oxide",
                      delta === 0 && "text-muted/50",
                    )}
                    aria-label={delta === 0 ? "mesma posição" : `${Math.abs(delta)} posição(ões) ${delta > 0 ? "acima" : "abaixo"}`}
                  >
                    {delta > 0 && <ArrowUp className="size-3" aria-hidden />}
                    {delta < 0 && <ArrowDown className="size-3" aria-hidden />}
                    {delta === 0 ? "—" : Math.abs(delta)}
                  </span>
                  <span className="w-10 text-right font-mono">{Math.round(c.simulated)}</span>
                </li>
              );
            })}
          </ol>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-xs text-muted">
              O parecer acima foi redigido com {toPercent(reportWeights).hard_skills}/
              {toPercent(reportWeights).soft_skills}/{toPercent(reportWeights).context_fit}.
            </p>
            <button
              type="button"
              disabled={!changed || rerunning}
              onClick={() => onRerun(toPercent(weights))}
              className="rounded-md bg-ink px-3 py-1.5 text-xs font-medium text-paper transition-opacity disabled:opacity-40"
            >
              Refazer parecer com este critério
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
