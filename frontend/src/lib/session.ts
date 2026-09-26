// Minimal access gate for the public demo: a password exchanged for a signed,
// httpOnly cookie. Not a user system — in production this is Google IAP / SSO.

export const SESSION_COOKIE = "curadoria_session";
export const SESSION_TTL_S = 60 * 60 * 8;

const encoder = new TextEncoder();

async function sign(value: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign("HMAC", key, encoder.encode(value));
  return Buffer.from(mac).toString("base64url");
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function accessControlEnabled(): boolean {
  return Boolean(process.env.DEMO_PASSWORD && process.env.SESSION_SECRET);
}

export async function createSessionToken(): Promise<string> {
  const expires = Math.floor(Date.now() / 1000) + SESSION_TTL_S;
  return `${expires}.${await sign(String(expires), process.env.SESSION_SECRET!)}`;
}

export async function isValidSession(token: string | undefined): Promise<boolean> {
  if (!token) return false;
  const [expires, signature] = token.split(".");
  if (!expires || !signature || Number(expires) < Date.now() / 1000) return false;
  return timingSafeEqual(signature, await sign(expires, process.env.SESSION_SECRET!));
}

export function passwordMatches(candidate: string): boolean {
  return timingSafeEqual(candidate, process.env.DEMO_PASSWORD ?? "");
}
