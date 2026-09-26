# Curadoria · interface

Next.js (App Router) para o sócio colar a vaga e ler o shortlist.

- `src/app/api/*` são route handlers que repassam as chamadas para a API Python. A chave
  (`BACKEND_API_KEY`) fica só no servidor.
- `src/proxy.ts` protege a demo com senha (`DEMO_PASSWORD` + `SESSION_SECRET`). Se as duas
  variáveis estiverem vazias, o acesso fica aberto (uso local).
- `src/lib/use-curation.ts` consome o streaming SSE das etapas do agente.

```bash
cp .env.example .env.local
npm install
npm run dev
```

Instruções completas no [README principal](../README.md).
