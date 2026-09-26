import { NextResponse, type NextRequest } from "next/server";
import { SESSION_COOKIE, accessControlEnabled, isValidSession } from "@/lib/session";

export async function proxy(request: NextRequest) {
  if (!accessControlEnabled()) return NextResponse.next();
  if (await isValidSession(request.cookies.get(SESSION_COOKIE)?.value)) return NextResponse.next();

  if (request.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ message: "Sessão expirada. Entre novamente." }, { status: 401 });
  }
  const login = new URL("/login", request.url);
  login.searchParams.set("next", request.nextUrl.pathname);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/((?!login|api/session|_next/static|_next/image|favicon.ico).*)"],
};
