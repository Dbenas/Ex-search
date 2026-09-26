"use client";

import { useState } from "react";
import clsx from "clsx";
import { ArrowRight, LoaderCircle } from "lucide-react";
import { SAMPLE_JOBS } from "@/lib/sample-jobs";
import { useCuration } from "@/lib/use-curation";
import { AgentTrace } from "./agent-trace";
import { MatchReportView } from "./match-report";

const MIN_CHARS = 80;
const MAX_CHARS = 8000;

export function Workbench() {
  const [text, setText] = useState("");
  const { status, stages, report, error, run } = useCuration();
  const running = status === "running";
  const tooShort = text.trim().length < MIN_CHARS;

  return (
    <div className="mx-auto grid max-w-[1320px] gap-8 px-4 py-8 sm:px-8 lg:grid-cols-[380px_minmax(0,1fr)] lg:gap-12 lg:py-12">
      <aside className="space-y-8 lg:sticky lg:top-24 lg:self-start">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (!tooShort && !running) run(text.trim());
          }}
          className="space-y-3"
        >
          <label htmlFor="jd" className="block">
            <span className="font-display text-[26px] font-semibold leading-tight tracking-[-0.03em]">
              Qual é o mandato?
            </span>
            <span className="mt-1.5 block text-sm text-ink-soft">
              Cole a descrição da vaga. O agente busca na base, avalia cada perfil e entrega um
              shortlist com parecer e evidências.
            </span>
          </label>
          <textarea
            id="jd"
            value={text}
            onChange={(e) => setText(e.target.value.slice(0, MAX_CHARS))}
            rows={9}
            placeholder="Ex.: Empresa de tecnologia em fase de alto crescimento busca CFO para…"
            className="w-full resize-y rounded-lg border border-rule bg-paper px-3.5 py-3 text-[14.5px] leading-relaxed outline-none transition-colors placeholder:text-muted/70 focus:border-ink"
          />
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-muted">Exemplos do desafio:</span>
            {SAMPLE_JOBS.map((job) => (
              <button
                key={job.label}
                type="button"
                onClick={() => setText(job.text)}
                className="rounded-full border border-rule bg-paper px-2.5 py-1 text-ink-soft hover:border-ink hover:text-ink"
              >
                {job.label}
              </button>
            ))}
          </div>
          <button
            type="submit"
            disabled={tooShort || running}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-ink px-4 py-3 text-sm font-medium text-paper transition-opacity disabled:cursor-not-allowed disabled:opacity-50"
          >
            {running ? (
              <>
                <LoaderCircle className="size-4 animate-spin" aria-hidden /> Analisando a base…
              </>
            ) : (
              <>
                Montar shortlist <ArrowRight className="size-4" aria-hidden />
              </>
            )}
          </button>
          {tooShort && text.length > 0 && (
            <p className="text-xs text-muted">
              Descreva a vaga com pelo menos {MIN_CHARS} caracteres para uma leitura confiável.
            </p>
          )}
        </form>

        {status !== "idle" && (
          <section aria-label="Etapas do agente" className="rounded-xl border border-rule bg-paper p-5">
            <p className="mb-4 font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
              O que o agente está fazendo
            </p>
            <AgentTrace stages={stages} running={running} />
          </section>
        )}
      </aside>

      <main className="min-w-0">
        {error && (
          <div role="alert" className="mb-6 rounded-lg border border-oxide/30 bg-paper px-4 py-3 text-sm">
            <p className="font-medium text-oxide">A análise foi interrompida.</p>
            <p className="mt-0.5 text-ink-soft">{error}</p>
          </div>
        )}
        {report ? (
          <MatchReportView report={report} />
        ) : (
          <EmptyState running={running} />
        )}
      </main>
    </div>
  );
}

function EmptyState({ running }: { running: boolean }) {
  return (
    <div
      className={clsx(
        "grid min-h-[420px] place-items-center rounded-xl border border-dashed border-rule px-6 text-center",
        running && "animate-pulse motion-reduce:animate-none",
      )}
    >
      <div className="max-w-md">
        <p className="font-display text-lg font-medium">
          {running ? "Montando o shortlist" : "O shortlist aparece aqui"}
        </p>
        <p className="mt-2 text-sm leading-relaxed text-ink-soft">
          {running
            ? "Cada perfil é avaliado separadamente e toda afirmação é conferida no currículo antes de entrar no parecer."
            : "Três candidatos, com nota por dimensão, parecer consultivo e os trechos do currículo que sustentam cada afirmação."}
        </p>
      </div>
    </div>
  );
}
