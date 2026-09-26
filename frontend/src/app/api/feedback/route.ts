import { backendFetch } from "@/lib/backend";

export async function POST(request: Request) {
  try {
    const upstream = await backendFetch("/v1/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: await request.text(),
    });
    return new Response(null, { status: upstream.ok ? 204 : upstream.status });
  } catch {
    return new Response(null, { status: 503 });
  }
}
