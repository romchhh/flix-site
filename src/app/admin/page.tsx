import { backendJson } from "@/lib/backend";
import { uah, dateUk } from "@/lib/display";

export const dynamic = "force-dynamic";

type Overview = {
  stats: Record<string, number>;
  payments: Array<{
    payment_id: string; invoice_id: string; user_id: number; product_id: number;
    months: number; amount: number; status: string; payment_type: string; source: string; created_at: string;
  }>;
  users: Array<{ user_id: number; user_name: string | null; email: string | null; source: string; join_date: string }>;
  products: Array<{ id: string; name: string }>;
};

export default async function AdminDash() {
  const data = await backendJson<Overview>("/api/admin/overview");
  const stats = data?.stats ?? {};
  const payments = data?.payments ?? [];
  const now = new Date();

  const statusTag: Record<string, string> = {
    pending: "t-wait", success: "t-ok", failed: "t-bad", one_time: "t-new",
  };
  const statusName: Record<string, string> = {
    pending: "чекає", success: "оплачено", failed: "не вдалось",
  };

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Дашборд</h1>
          <p className="adm-sub">{dateUk(now)} · дані з бота</p>
        </div>
      </div>

      <div className="kpis">
        <div className="kpi"><small>Виручка за місяць</small><b>{Math.round(Number(stats.month_revenue || 0))} ₴</b></div>
        <div className="kpi"><small>Платежів за місяць</small><b>{stats.month_payments_count || 0}</b></div>
        <div className="kpi"><small>Активних підписок</small><b>{(stats.active_simple_subscriptions || 0) + (stats.active_recurring_subscriptions || 0)}</b></div>
        <div className="kpi"><small>Автосписань сьогодні</small><b>{stats.today_auto_payments_count || 0}</b></div>
      </div>

      <div className="panel">
        <h2>Каталог і клієнти</h2>
        <p className="muted">
          Товари, оплати й автосписання живуть у Telegram-боті. Сайт лише створює рахунок через API
          і показує той самий стан клієнту.
        </p>
        <p className="muted">Користувачів у боті: {stats.total_users || 0} · товарів: {stats.total_products || 0}</p>
      </div>

      <div className="panel">
        <h2>Останні платежі</h2>
        {payments.length === 0 ? (
          <p className="muted">Платежів поки немає, або бот API недоступне.</p>
        ) : (
          <div className="tw">
            <table>
              <thead>
                <tr><th>Номер</th><th>Користувач</th><th>Сума</th><th>Тип</th><th>Статус</th><th>Звідки</th></tr>
              </thead>
              <tbody>
                {payments.slice(0, 12).map((o) => (
                  <tr key={o.invoice_id}>
                    <td className="n">{o.payment_id}</td>
                    <td>{o.user_id}</td>
                    <td className="n">{o.amount} ₴</td>
                    <td className="muted">{o.payment_type === "subscription" ? "підписка" : "разова"}</td>
                    <td><span className={`tag ${statusTag[o.status] || "t-wait"}`}>{statusName[o.status] || o.status}</span></td>
                    <td className="muted">{o.source || "bot"}</td>
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
