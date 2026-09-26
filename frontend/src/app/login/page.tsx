"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    const res = await fetch("/api/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    setPending(false);
    if (!res.ok) {
      setError("Senha incorreta. Confira com quem compartilhou o acesso.");
      return;
    }
    const next = params.get("next");
    router.replace(next?.startsWith("/") ? next : "/");
  }

  return (
    <form onSubmit={submit} className="w-full max-w-sm space-y-5">
      <div>
        <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted">
          Acesso restrito
        </p>
        <h1 className="mt-2 font-display text-3xl font-semibold tracking-[-0.03em]">Curadoria</h1>
        <p className="mt-2 text-sm text-ink-soft">
          Ambiente de demonstração com dados fictícios. Informe a senha recebida.
        </p>
      </div>
      <label className="block text-sm">
        <span className="text-ink-soft">Senha</span>
        <input
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1.5 w-full rounded-md border border-rule bg-paper px-3 py-2.5 outline-none focus:border-ink"
          required
        />
      </label>
      {error && <p className="text-sm text-oxide">{error}</p>}
      <button
        type="submit"
        disabled={pending}
        className="w-full rounded-md bg-ink px-4 py-2.5 text-sm font-medium text-paper transition-opacity disabled:opacity-60"
      >
        {pending ? "Verificando…" : "Entrar"}
      </button>
    </form>
  );
}

export default function LoginPage() {
  return (
    <main className="grid min-h-screen place-items-center px-4">
      <Suspense>
        <LoginForm />
      </Suspense>
    </main>
  );
}
