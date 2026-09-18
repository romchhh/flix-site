import { backendJson } from "@/lib/backend";
import { uah } from "@/lib/display";
import type { CatalogProduct } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function AdminProducts() {
  const data = await backendJson<{ products: CatalogProduct[] }>("/api/admin/overview");
  const products = data?.products ?? [];

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Товари</h1>
          <p className="adm-sub">Каталог з бота. Редагування — в Telegram адмінці.</p>
        </div>
      </div>

      <div className="panel">
        {products.length === 0 ? (
          <p className="muted">Немає товарів або бот API недоступне.</p>
        ) : (
          <div className="tw">
            <table>
              <thead>
                <tr><th>Товар</th><th>Категорія</th><th>Режим</th><th>Від</th></tr>
              </thead>
              <tbody>
                {products.map((p) => {
                  const cheapest = p.plans?.length
                    ? [...p.plans].sort((a, b) => a.total - b.total)[0]
                    : null;
                  return (
                    <tr key={p.id}>
                      <td>
                        <span className="adm-prod">
                          {p.photoUrl ? <img src={p.photoUrl} alt="" /> : null}
                          <b>{p.name}</b>
                        </span>
                      </td>
                      <td className="muted">{p.categoryName}</td>
                      <td>{p.recurring ? "автосписання" : "разова"}</td>
                      <td className="n">{cheapest ? `${uah(cheapest.total)} ₴` : "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
