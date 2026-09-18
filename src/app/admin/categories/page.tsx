import { backendJson } from "@/lib/backend";
import type { CatalogCategory } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function AdminCategories() {
  const data = await backendJson<{ categories: CatalogCategory[] }>("/api/admin/overview");
  const categories = data?.categories ?? [];

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Категорії</h1>
          <p className="adm-sub">З каталогу бота</p>
        </div>
      </div>
      <div className="panel">
        {categories.length === 0 ? (
          <p className="muted">Порожньо.</p>
        ) : (
          <div className="tw">
            <table>
              <thead><tr><th>Назва</th><th>Товарів</th></tr></thead>
              <tbody>
                {categories.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <span className="adm-prod">
                        {c.photoUrl ? <img src={c.photoUrl} alt="" /> : null}
                        <b>{c.name}</b>
                      </span>
                    </td>
                    <td>{c.count ?? "—"}</td>
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
