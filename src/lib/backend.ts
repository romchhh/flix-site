import { cookies } from "next/headers";

const BACKEND = process.env.SITE_BACKEND_URL || "http://127.0.0.1:8000";

export async function backend(path: string, init: RequestInit = {}) {
  const jar = await cookies();
  const headers = new Headers(init.headers);
  const cookie = jar.toString();
  if (cookie) headers.set("cookie", cookie);
  if (!headers.has("content-type") && init.body) headers.set("content-type", "application/json");
  const res = await fetch(`${BACKEND}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  return res;
}

export async function backendJson<T>(path: string, init: RequestInit = {}): Promise<T | null> {
  try {
    const res = await backend(path, init);
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
