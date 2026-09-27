import { backendFetch } from "@/lib/backend";

export async function DELETE(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[a-z0-9-]{1,80}$/.test(id)) return new Response(null, { status: 400 });
  try {
    const upstream = await backendFetch(`/v1/candidates/${id}`, { method: "DELETE" });
    return new Response(null, { status: upstream.status });
  } catch {
    return new Response(null, { status: 503 });
  }
}
