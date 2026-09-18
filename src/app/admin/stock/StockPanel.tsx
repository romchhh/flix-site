"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";

type ProductRow = {
  id: string;
  name: string;
  autoIssue: boolean;
  stockFree: number;
};

type CredentialRow = {
  id: string;
  productId: string;
  login: string;
  hasTotp: boolean;
  slotsTotal: number;
  slotsUsed: number;
  slotsFree: number;
  note: string;
  active: boolean;
};

async function api(path: string, init?: RequestInit) {
  const res = await fetch(path, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers || {}) },
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || "Помилка запиту");
  return data;
}

export function StockPanel({
  products,
  credentials: initial,
  filterProductId,
}: {
  products: ProductRow[];
  credentials: CredentialRow[];
  filterProductId?: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [productId, setProductId] = useState(filterProductId || products[0]?.id || "");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [totpSecret, setTotpSecret] = useState("");
  const [slotsTotal, setSlotsTotal] = useState(1);
  const [note, setNote] = useState("");

  const selected = products.find((p) => p.id === productId);
  const rows = productId ? initial.filter((c) => c.productId === productId) : initial;

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Помилка");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {error && <div className="warn-box" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 17, fontWeight: 800, marginBottom: 14 }}>Автовидача по товарах</h2>
        <div className="tw">
          <table>
            <thead>
              <tr><th>Товар</th><th>На складі</th><th>Автовидача</th></tr>
            </thead>
            <tbody>
              {products.map((p) => (
                <tr key={p.id}>
                  <td><b>{p.name}</b></td>
                  <td className="n">{p.stockFree}</td>
                  <td>
                    <label style={{ display: "inline-flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                      <input
                        type="checkbox"
                        checked={p.autoIssue}
                        disabled={busy}
                        onChange={() => run(async () => {
                          await api(`/api/admin/stock/products/${p.id}`, {
                            method: "POST",
                            body: JSON.stringify({ autoIssue: !p.autoIssue }),
                          });
                        })}
                      />
                      {p.autoIssue ? "увімкнено" : "вручну"}
                    </label>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 17, fontWeight: 800, marginBottom: 14 }}>Додати акаунт</h2>
        <div className="f2">
          <div className="field">
            <label>Товар</label>
            <select value={productId} onChange={(e) => setProductId(e.target.value)}>
              {products.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label>Слотів</label>
            <input type="number" min={1} value={slotsTotal} onChange={(e) => setSlotsTotal(Number(e.target.value) || 1)} />
          </div>
        </div>
        <div className="f2">
          <div className="field">
            <label>Логін</label>
            <input value={login} onChange={(e) => setLogin(e.target.value)} placeholder="email@example.com" />
          </div>
          <div className="field">
            <label>Пароль</label>
            <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
          </div>
        </div>
        <div className="field">
          <label>2FA ключ (base32, опційно)</label>
          <input value={totpSecret} onChange={(e) => setTotpSecret(e.target.value)} placeholder="JBSWY3DPEHPK3PXP" />
          <p className="muted" style={{ marginTop: 6 }}>Для ChatGPT та інших — клієнт отримає тимчасовий код у кабінеті.</p>
        </div>
        <div className="field">
          <label>Примітка</label>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="спільний акаунт, 4 користувача…" />
        </div>
        <button
          className="btn sm"
          type="button"
          disabled={busy || !productId || !login || !password}
          onClick={() => run(async () => {
            await api("/api/admin/stock/credentials", {
              method: "POST",
              body: JSON.stringify({
                productId,
                login,
                password,
                totpSecret,
                slotsTotal,
                note,
              }),
            });
            setLogin("");
            setPassword("");
            setTotpSecret("");
            setNote("");
            setSlotsTotal(1);
          })}
        >
          Додати на склад
        </button>
        {selected && (
          <p className="muted" style={{ marginTop: 10 }}>
            {selected.autoIssue
              ? "Після оплати логін і пароль зʼявляться в кабінеті одразу."
              : "Автовидача вимкнена — доступ видає менеджер."}
          </p>
        )}
      </div>

      <div className="panel">
        <h2 style={{ fontSize: 17, fontWeight: 800, marginBottom: 14 }}>
          Акаунти{selected ? `: ${selected.name}` : ""}
        </h2>
        {rows.length === 0 ? (
          <p className="muted">На складі порожньо.</p>
        ) : (
          <div className="tw">
            <table>
              <thead>
                <tr><th>Логін</th><th>2FA</th><th>Слоти</th><th>Статус</th><th>Примітка</th><th></th></tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.id}>
                    <td><b>{c.login}</b></td>
                    <td>{c.hasTotp ? "є" : "—"}</td>
                    <td className="n">{c.slotsUsed}/{c.slotsTotal}</td>
                    <td>{c.active ? "активний" : "вимкнений"}</td>
                    <td className="muted">{c.note || "—"}</td>
                    <td>
                      <button
                        className="btn sm ghost"
                        type="button"
                        disabled={busy}
                        onClick={() => run(async () => {
                          await api(`/api/admin/stock/credentials/${c.id}`, { method: "DELETE" });
                        })}
                      >
                        Видалити
                      </button>
                    </td>
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
