import { cookies } from "next/headers";
import {
  SESSION_COOKIE,
  SESSION_TTL_S,
  accessControlEnabled,
  createSessionToken,
  passwordMatches,
} from "@/lib/session";

export async function POST(request: Request) {
  if (!accessControlEnabled()) return new Response(null, { status: 204 });

  const { password } = (await request.json().catch(() => ({}))) as { password?: string };
  if (!password || !passwordMatches(password)) {
    return Response.json({ message: "Senha incorreta." }, { status: 401 });
  }

  (await cookies()).set(SESSION_COOKIE, await createSessionToken(), {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: SESSION_TTL_S,
  });
  return new Response(null, { status: 204 });
}

export async function DELETE() {
  (await cookies()).delete(SESSION_COOKIE);
  return new Response(null, { status: 204 });
}
