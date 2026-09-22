"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

type ProductRow = {
  id: string;
  name: string;
  autoIssue: boolean;
  stockFree: number;
  needsProfilePin?: boolean;
  isBundle?: boolean;
  bundleSources?: Array<{ id: string; name: string }>;
};

type ProfileSlot = { num: string; pin: string };

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
  fromSheets?: boolean;
  profileSlots?: Array<{ num: string }>;
};

type SheetsSyncStatus = {
  at: string | null;
  ok: boolean;
  imported: number;
  deactivated: number;
  available?: number;
  byService?: Record<string, number>;
  errors?: string[];
};

function needsProfilePin(product?: ProductRow | null) {
  if (!product || product.isBundle) return false;
  return Boolean(product.needsProfilePin || /hbo/i.test(product.name || ""));
}

function emptyProfileSlots(count: number): ProfileSlot[] {
  return Array.from({ length: Math.max(1, count) }, () => ({ num: "", pin: "" }));
}

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
  sheetsSync: initialSync,
}: {
  products: ProductRow[];
  credentials: CredentialRow[];
  filterProductId?: string;
  sheetsSync?: SheetsSyncStatus;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sheetsSync, setSheetsSync] = useState<SheetsSyncStatus | undefined>(initialSync);
  const [productId, setProductId] = useState(filterProductId || products[0]?.id || "");
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [totpSecret, setTotpSecret] = useState("");
  const [slotsTotal, setSlotsTotal] = useState(1);
  const [note, setNote] = useState("");
  const [profileSlots, setProfileSlots] = useState<ProfileSlot[]>(emptyProfileSlots(1));

  const selected = products.find((p) => p.id === productId);
  const bundleProduct = Boolean(selected?.isBundle);
  const profileProduct = needsProfilePin(selected);
  const rows = productId && !bundleProduct
    ? initial.filter((c) => c.productId === productId)
    : bundleProduct
      ? []
      : initial;

  useEffect(() => {
    setProfileSlots((prev) => {
      const next = emptyProfileSlots(slotsTotal);
      for (let i = 0; i < next.length; i += 1) {
        next[i] = prev[i] || next[i];
      }
      return next;
    });
  }, [slotsTotal]);

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

  const profileReady = !profileProduct || profileSlots.every((slot) => slot.num.trim() && slot.pin.trim());

  const syncLabel = sheetsSync?.at
    ? `Останнє оновлення: ${new Date(sheetsSync.at).toLocaleString("uk-UA")}`
    : "Ще не синхронізовано";

  return (
    <>
      {error && <div className="warn-box" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="panel" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap", marginBottom: 14 }}>
          <div>
            <h2 style={{ fontSize: 17, fontWeight: 800, marginBottom: 6 }}>Google Таблиці</h2>
            <p className="muted" style={{ margin: 0 }}>{syncLabel}</p>
            {sheetsSync?.byService && Object.keys(sheetsSync.byService).length > 0 && (
              <p className="muted" style={{ marginTop: 6, marginBottom: 0 }}>
                Імпортовано: {Object.entries(sheetsSync.byService).map(([k, v]) => `${k}: ${v}`).join(", ")}
              </p>
            )}
            {sheetsSync?.errors?.length ? (
              <p className="muted" style={{ marginTop: 6, marginBottom: 0, color: "var(--red)" }}>
                {sheetsSync.errors.join("; ")}
              </p>
            ) : null}
          </div>
          <button
            className="btn sm"
            type="button"
            disabled={busy}
            onClick={() => run(async () => {
              const data = await api("/api/admin/stock/sync-sheets", { method: "POST", body: "{}" });
              setSheetsSync(data);
            })}
          >
            Оновити з таблиць
          </button>
        </div>
        <p className="muted" style={{ margin: 0 }}>
          Netflix, Filmix, GPT, HBO, IPTV — автоматично кожну хвилину. Після видачі акаунт позначається у таблиці.
        </p>
      </div>

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
                  <td>
                    <b>{p.name}</b>
                    {p.isBundle && <small className="muted" style={{ display: "block", marginTop: 4 }}>набір</small>}
                  </td>
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
          {!bundleProduct && (
            <div className="field">
              <label>Слотів</label>
              <input type="number" min={1} value={slotsTotal} onChange={(e) => setSlotsTotal(Number(e.target.value) || 1)} />
            </div>
          )}
        </div>

        {bundleProduct && selected?.bundleSources?.length ? (
          <div className="warn-box" style={{ marginBottom: 14 }}>
            <b>Це набір — окремий склад не потрібен</b>
            <p className="muted" style={{ marginTop: 8, marginBottom: 0 }}>
              Після оплати сайт видасть доступ зі складів:{" "}
              {selected.bundleSources.map((source) => source.name).join(" + ")}.
              Додавай акаунти до цих товарів окремо — набір забере по одному з кожного складу.
            </p>
            <ul style={{ margin: "10px 0 0", paddingLeft: 18 }}>
              {selected.bundleSources.map((source) => {
                const stock = products.find((p) => p.id === source.id)?.stockFree ?? 0;
                return (
                  <li key={source.id}>
                    <button
                      type="button"
                      className="more-btn"
                      style={{ padding: 0, border: 0, background: "none", fontWeight: 800 }}
                      onClick={() => setProductId(source.id)}
                    >
                      {source.name}
                    </button>
                    {" — "}{stock} вільних слотів
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}

        {!bundleProduct && (
        <>
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

        {profileProduct && (
          <div className="field" style={{ marginTop: 4 }}>
            <label>Профілі HBO</label>
            <p className="muted" style={{ marginBottom: 10 }}>
              Для кожного слота вкажи номер профілю та PIN-код. Клієнт отримає їх разом із логіном.
            </p>
            <div style={{ display: "grid", gap: 10 }}>
              {profileSlots.map((slot, index) => (
                <div key={index} className="f2">
                  <div className="field">
                    <label>Слот {index + 1} · номер профілю</label>
                    <input
                      value={slot.num}
                      onChange={(e) => setProfileSlots((prev) => prev.map((item, i) => (
                        i === index ? { ...item, num: e.target.value } : item
                      )))}
                      placeholder="2"
                    />
                  </div>
                  <div className="field">
                    <label>Слот {index + 1} · PIN</label>
                    <input
                      value={slot.pin}
                      onChange={(e) => setProfileSlots((prev) => prev.map((item, i) => (
                        i === index ? { ...item, pin: e.target.value } : item
                      )))}
                      placeholder="1234"
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {!profileProduct && (
          <div className="field">
            <label>2FA ключ (base32, опційно)</label>
            <input value={totpSecret} onChange={(e) => setTotpSecret(e.target.value)} placeholder="JBSWY3DPEHPK3PXP" />
            <p className="muted" style={{ marginTop: 6 }}>Для ChatGPT та інших — клієнт отримає тимчасовий код у кабінеті.</p>
          </div>
        )}
        <div className="field">
          <label>Примітка</label>
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="спільний акаунт, 4 користувача…" />
        </div>
        <button
          className="btn sm"
          type="button"
          disabled={busy || !productId || !login || !password || !profileReady}
          onClick={() => run(async () => {
            await api("/api/admin/stock/credentials", {
              method: "POST",
              body: JSON.stringify({
                productId,
                login,
                password,
                totpSecret: profileProduct ? "" : totpSecret,
                slotsTotal,
                note,
                profileSlots: profileProduct
                  ? profileSlots.map((slot) => ({ num: slot.num.trim(), pin: slot.pin.trim() }))
                  : undefined,
              }),
            });
            setLogin("");
            setPassword("");
            setTotpSecret("");
            setNote("");
            setSlotsTotal(1);
            setProfileSlots(emptyProfileSlots(1));
          })}
        >
          Додати на склад
        </button>
        {selected && (
          <p className="muted" style={{ marginTop: 10 }}>
            {selected.autoIssue
              ? profileProduct
                ? "Після оплати клієнт отримає логін, пароль, номер профілю та PIN у кабінеті."
                : "Після оплати логін і пароль зʼявляться в кабінеті одразу."
              : "Автовидача вимкнена — доступ видає менеджер."}
          </p>
        )}
        </>
        )}
      </div>

      <div className="panel">
        <h2 style={{ fontSize: 17, fontWeight: 800, marginBottom: 14 }}>
          Акаунти{selected ? `: ${selected.name}` : ""}
        </h2>
        {bundleProduct ? (
          <p className="muted">
            У набору немає власного складу. Дивись акаунти в окремих товарах:{" "}
            {selected?.bundleSources?.map((source) => source.name).join(", ") || "—"}.
          </p>
        ) : rows.length === 0 ? (
          <p className="muted">На складі порожньо.</p>
        ) : (
          <div className="tw">
            <table>
              <thead>
                <tr><th>Логін</th><th>2FA</th><th>Профілі</th><th>Слоти</th><th>Джерело</th><th>Статус</th><th>Примітка</th><th></th></tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.id}>
                    <td><b>{c.login}</b></td>
                    <td>{c.hasTotp ? "є" : "—"}</td>
                    <td className="muted">
                      {c.profileSlots?.length
                        ? c.profileSlots.map((slot) => `№${slot.num}`).join(", ")
                        : "—"}
                    </td>
                    <td className="n">{c.slotsUsed}/{c.slotsTotal}</td>
                    <td className="muted">{c.fromSheets ? "таблиця" : "вручну"}</td>
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
