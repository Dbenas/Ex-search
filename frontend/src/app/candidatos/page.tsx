import { backendJson } from "@/lib/backend";
import type { CandidateSummary } from "@/lib/types";

export default async function CandidatesPage() {
  const candidates = await backendJson<CandidateSummary[]>("/v1/candidates");

  return (
    <main className="mx-auto max-w-[1320px] px-4 py-10 sm:px-8 lg:py-14">
      <header className="max-w-2xl">
        <h1 className="font-display text-[30px] font-semibold tracking-[-0.03em]">Base de perfis</h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-soft">
          Perfis indexados para busca. Dados de contato ficam fora da busca, fora do modelo e fora
          desta tela: o que está aqui é o conteúdo profissional que o agente pode ler.
        </p>
      </header>

      {candidates === null ? (
        <p className="mt-10 rounded-lg border border-rule bg-paper px-4 py-3 text-sm text-ink-soft">
          Não foi possível carregar a base. Verifique se a API está em execução.
        </p>
      ) : (
        <ul className="mt-10 grid gap-4 md:grid-cols-2">
          {candidates.map((c) => (
            <li key={c.candidate_id} className="rounded-xl border border-rule bg-paper p-6">
              <p className="font-display text-lg font-semibold tracking-[-0.015em]">{c.name}</p>
              <p className="text-sm text-muted">{c.current_role}</p>
              <p className="mt-4 font-serif text-[15px] leading-[1.7] text-ink-soft">
                {c.profile_text}
              </p>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
