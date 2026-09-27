import clsx from "clsx";
import { CircleAlert, CircleCheck } from "lucide-react";
import type { BiasAudit } from "@/lib/types";

function Check({ ok, title, children }: { ok: boolean; title: string; children: React.ReactNode }) {
  const Icon = ok ? CircleCheck : CircleAlert;
  return (
    <div className="flex gap-3">
      <Icon className={clsx("mt-0.5 size-5 shrink-0", ok ? "text-verdigris" : "text-oxide")} aria-hidden />
      <div className="min-w-0">
        <p className="font-medium">{title}</p>
        <div className="mt-1 text-[13.5px] leading-relaxed text-ink-soft">{children}</div>
      </div>
    </div>
  );
}

export function BiasAuditView({ audit }: { audit: BiasAudit }) {
  const { name_invariance: names, gender_invariance: gender } = audit;
  return (
    <section aria-labelledby="bias-title" className="mt-12 rounded-xl border border-rule bg-paper">
      <header className="border-b border-rule px-6 py-5">
        <h2 id="bias-title" className="font-display text-xl font-semibold tracking-[-0.02em]">
          Auditoria de viés
        </h2>
        <p className="mt-1 max-w-[72ch] text-sm leading-relaxed text-ink-soft">
          Em vez de medir viés só depois, o pipeline impede que nome e gênero cheguem ao modelo, e
          a auditoria prova isso comparando, byte a byte, o texto que o modelo recebe. Essas
          verificações não chamam o modelo e rodam a cada alteração do código.
        </p>
      </header>
      <div className="grid gap-8 px-6 py-6 md:grid-cols-2">
        <Check ok={names.passed} title="O nome não influencia a avaliação">
          Trocando nome e contato de cada executivo por outro de gênero oposto, o texto enviado ao
          modelo permanece idêntico.
          <ul className="mt-2 space-y-0.5 font-mono text-xs text-muted">
            {names.checks.map((c) => (
              <li key={c.original_name}>
                {c.original_name} → {c.swapped_name}: {c.identical_prompt ? "idêntico" : "DIFERENTE"}
              </li>
            ))}
          </ul>
        </Check>
        <Check ok={gender.passed} title="Marcas de gênero no currículo são neutralizadas">
          Sem o nome, o português ainda revela o gênero pela concordância. As formas femininas
          encontradas são reescritas na forma não marcada antes do envio; o sócio continua vendo o
          texto original.
          <ul className="mt-2 space-y-0.5 font-mono text-xs text-muted">
            {gender.checks.length ? (
              gender.checks.map((c) => (
                <li key={c.alias}>
                  {c.alias}: “{c.terms.join("”, “")}” — {c.identical_prompt ? "neutralizada" : "CHEGA AO MODELO"}
                </li>
              ))
            ) : (
              <li>nenhuma marca encontrada</li>
            )}
          </ul>
        </Check>
      </div>
      {audit.counterfactual && (
        <div className="border-t border-rule px-6 py-5 text-sm">
          <p className="font-medium">Teste contrafactual com o modelo, sem neutralização</p>
          <ul className="mt-2 space-y-1 text-ink-soft">
            {audit.counterfactual.results.map((r) => (
              <li key={r.alias}>
                {r.alias}: diferença média de {r.mean_delta} ponto(s), variação natural ±{r.run_to_run_sd}.{" "}
                {r.verdict}.
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
