import clsx from "clsx";
import { Check } from "lucide-react";
import type { StageEvent, StageName } from "@/lib/types";

const STEPS: { stage: StageName; title: string; purpose: string }[] = [
  {
    stage: "sanitize",
    title: "Proteção de dados",
    purpose: "Contatos e nomes saem do texto antes de qualquer chamada ao modelo.",
  },
  {
    stage: "analyze_job",
    title: "Leitura do mandato",
    purpose: "Requisitos essenciais, desejáveis e implícitos da posição.",
  },
  {
    stage: "retrieve",
    title: "Busca semântica",
    purpose: "Perfis mais próximos do mandato por significado, não por palavra-chave.",
  },
  {
    stage: "assess",
    title: "Avaliação individual",
    purpose: "Cada perfil pontuado em hard skills, soft skills e fit de contexto.",
  },
  {
    stage: "rank",
    title: "Verificação de evidências",
    purpose: "Toda citação é conferida no texto original; o que não existe é descartado.",
  },
  {
    stage: "synthesize",
    title: "Parecer",
    purpose: "Memorando comparativo usando apenas evidências confirmadas.",
  },
];

// Only runs when the base does not cover the mandate; shown once it happens.
const PLAN_STEP = {
  stage: "plan_search" as const,
  title: "Plano de busca",
  purpose: "Perfis-alvo e buscas para cobrir o que a base não tem.",
};

type Props = { stages: StageEvent[]; running: boolean };

export function AgentTrace({ stages, running }: Props) {
  const done = new Set(stages.map((s) => s.stage));
  const shortlistSize = (
    stages.find((s) => s.stage === "retrieve")?.data.shortlist as unknown[] | undefined
  )?.length;
  const assessed = stages.filter((s) => s.stage === "assess").length;
  const steps = done.has("plan_search") ? [...STEPS, PLAN_STEP] : STEPS;
  const activeIndex = running ? steps.findIndex((step) => !isDone(step.stage)) : -1;

  function isDone(stage: StageName) {
    if (stage === "assess") return shortlistSize !== undefined && assessed >= shortlistSize;
    return done.has(stage);
  }

  function detail(stage: StageName): string | undefined {
    if (stage === "assess" && shortlistSize) return `${assessed} de ${shortlistSize} perfis avaliados`;
    return stages.findLast((s) => s.stage === stage)?.message;
  }

  return (
    <ol className="relative space-y-0" aria-live="polite">
      {steps.map((step, index) => {
        const complete = isDone(step.stage);
        const active = index === activeIndex;
        const info = detail(step.stage);
        return (
          <li key={step.stage} className="relative flex gap-3 pb-5 last:pb-0">
            {index < steps.length - 1 && (
              <span
                aria-hidden
                className={clsx(
                  "absolute left-[11px] top-6 h-[calc(100%-18px)] w-px",
                  complete ? "bg-verdigris" : "bg-rule",
                )}
              />
            )}
            <span
              className={clsx(
                "relative z-10 grid size-[23px] shrink-0 place-items-center rounded-full border font-mono text-[11px]",
                complete && "border-verdigris bg-verdigris text-paper",
                active && "border-ink bg-paper text-ink",
                !complete && !active && "border-rule bg-paper text-muted",
              )}
            >
              {complete ? <Check className="size-3" strokeWidth={3} /> : index + 1}
              {active && (
                <span className="absolute inset-[-4px] animate-ping rounded-full border border-ink/30 motion-reduce:hidden" />
              )}
            </span>
            <div className="min-w-0 pt-0.5">
              <p className={clsx("text-sm font-medium", !complete && !active && "text-muted")}>
                {step.title}
              </p>
              <p className="mt-0.5 text-xs leading-relaxed text-muted">
                {complete || active ? (info ?? step.purpose) : step.purpose}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
