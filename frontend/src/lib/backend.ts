import "server-only";

// The browser never talks to the Python API directly: route handlers attach the
// API key server-side, so it is never shipped in the client bundle.

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const BACKEND_API_KEY = process.env.BACKEND_API_KEY ?? "";

export function backendFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (BACKEND_API_KEY) headers.set("X-API-Key", BACKEND_API_KEY);
  return fetch(`${BACKEND_URL}${path}`, { ...init, headers, cache: "no-store" });
}

export async function backendJson<T>(path: string): Promise<T | null> {
  try {
    const res = await backendFetch(path);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
