import { backendJson } from "@/lib/backend";
import { dateUk } from "@/lib/display";

export const dynamic = "force-dynamic";

type Overview = {
  payments: Array<{
    payment_id: string; invoice_id: string; user_id: number; product_id: number;
    months: number; amount: number; status: string; payment_type: string; source: string; created_at: string;
  }>;
  products: Array<{ id: string; botId?: number; name: string }>;
};

const TAG: Record<string, string> = {
  pending: "t-wait", success: "t-ok", failed: "t-bad",
};
const NAME: Record<string, string> = {
  pending: "чекає оплату", success: "оплачено", failed: "не вдалось",
};

export default async function AdminOrders() {
  const data = await backendJson<Overview>("/api/admin/overview");
  const orders = data?.payments ?? [];
  const names = new Map((data?.products ?? []).map((p) => [String(p.botId ?? p.id), p.name]));

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Платежі</h1>
          <p className="adm-sub">Усі рахунки з бази бота</p>
        </div>
      </div>

      <div className="panel">
        <div className="warn-box">
          Оплата й автосписання обробляються ботом. Після успішної оплати менеджер підключає доступ у Telegram.
        </div>
        {orders.length === 0 ? (
          <p className="muted">Поки порожньо.</p>
        ) : (
          <div className="tw">
            <table>
              <thead>
                <tr><th>Номер</th><th>Клієнт</th><th>Товар</th><th>Строк</th><th>Сума</th><th>Статус</th><th>Звідки</th><th>Створено</th></tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.invoice_id}>
                    <td className="n">{o.payment_id}</td>
                    <td>{o.user_id}</td>
                    <td>{names.get(String(o.product_id)) || o.product_id}</td>
                    <td className="muted">{o.months} міс</td>
                    <td className="n">{o.amount} ₴</td>
                    <td><span className={`tag ${TAG[o.status] || "t-wait"}`}>{NAME[o.status] || o.status}</span></td>
                    <td className="muted">{o.source || "bot"}</td>
                    <td className="muted">{o.created_at ? dateUk(new Date(o.created_at)) : "—"}</td>
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
