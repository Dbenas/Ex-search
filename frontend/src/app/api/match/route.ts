import { backendFetch } from "@/lib/backend";

// The agent makes several model calls; give the stream room to finish.
export const maxDuration = 300;

export async function POST(request: Request) {
  let upstream: Response;
  try {
    upstream = await backendFetch("/v1/match/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: await request.text(),
      signal: request.signal,
    });
  } catch {
    return Response.json(
      { message: "O serviço de análise está indisponível. Tente novamente em instantes." },
      { status: 503 },
    );
  }

  if (!upstream.ok || !upstream.body) {
    const detail = await upstream.json().catch(() => null);
    const message =
      upstream.status === 422
        ? "A descrição da vaga precisa ter entre 80 e 8.000 caracteres."
        : upstream.status === 429
          ? "Limite de análises por minuto atingido. Aguarde um instante."
          : (detail?.detail ?? "Não foi possível iniciar a análise.");
    return Response.json({ message }, { status: upstream.status });
  }

  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
