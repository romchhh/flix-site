import { backendJson } from "@/lib/backend";
import { dateUk } from "@/lib/display";

export const dynamic = "force-dynamic";

type Overview = {
  users: Array<{
    user_id: number; user_name: string | null; email: string | null;
    source: string | null; join_date: string | null; partner_balance?: number;
  }>;
};

export default async function AdminClients() {
  const data = await backendJson<Overview>("/api/admin/overview");
  const users = data?.users ?? [];

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Клієнти</h1>
          <p className="adm-sub">{users.length} у базі бота</p>
        </div>
      </div>
      <div className="panel">
        {users.length === 0 ? (
          <p className="muted">Ще ніхто не зареєструвався.</p>
        ) : (
          <div className="tw">
            <table>
              <thead>
                <tr><th>Клієнт</th><th>Джерело</th><th>Пошта</th><th>Telegram ID</th><th>З</th></tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.user_id}>
                    <td><b>{u.user_name ? `@${u.user_name}` : u.email ?? u.user_id}</b></td>
                    <td><span className="tag t-new">{u.source || "telegram"}</span></td>
                    <td className="muted">{u.email ?? "—"}</td>
                    <td className="n">{u.user_id}</td>
                    <td className="muted">{u.join_date ? dateUk(new Date(u.join_date)) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
