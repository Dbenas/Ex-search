import { backendFetch } from "@/lib/backend";

const MAX_BYTES = 2 * 1024 * 1024;

export async function POST(request: Request) {
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return Response.json({ message: "Envio inválido." }, { status: 400 });
  }
  const file = form.get("file");
  if (file instanceof File && file.size > MAX_BYTES) {
    return Response.json({ message: "O arquivo excede 2 MB." }, { status: 413 });
  }

  try {
    const upstream = await backendFetch("/v1/candidates", { method: "POST", body: form });
    const body = await upstream.json().catch(() => null);
    if (!upstream.ok) {
      const detail = typeof body?.detail === "string" ? body.detail : null;
      return Response.json(
        { message: detail ?? "Não foi possível adicionar o currículo." },
        { status: upstream.status },
      );
    }
    return Response.json(body, { status: 201 });
  } catch {
    return Response.json({ message: "O serviço está indisponível." }, { status: 503 });
  }
}
