export const dynamic = "force-dynamic";

export default function AdminPromo() {
  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Промокоди</h1>
          <p className="adm-sub">Знижки керуються в боті</p>
        </div>
      </div>
      <div className="panel">
        <p className="muted">Промокоди сайту вимкнені: ціна береться з тарифу в боті.</p>
      </div>
    </>
  );
}
