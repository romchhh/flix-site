import { backendJson } from "./backend";
import type { SiteUser } from "./types";

export async function currentUser(): Promise<SiteUser | null> {
  return backendJson<SiteUser>("/api/me");
}

export async function requireUser() {
  const u = await currentUser();
  if (!u) throw new Response("Unauthorized", { status: 401 });
  return u;
}

export async function requireAdmin() {
  const u = await currentUser();
  if (!u || !u.isAdmin) throw new Response("Forbidden", { status: 403 });
  return u;
}
