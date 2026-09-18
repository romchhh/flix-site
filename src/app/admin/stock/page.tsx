export const dynamic = "force-dynamic";

export default function AdminStock() {
  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Склад</h1>
          <p className="adm-sub">Доступи видає менеджер після оплати в боті</p>
        </div>
      </div>
      <div className="panel">
        <p className="muted">
          Склад акаунтів на сайті більше не використовується. Оплата, автосписання
          і видача доступу відбуваються в FlixMarketBot.
        </p>
      </div>
    </>
  );
}
