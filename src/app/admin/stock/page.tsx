import { backendJson } from "@/lib/backend";
import { StockPanel } from "./StockPanel";

export const dynamic = "force-dynamic";

type StockData = {
  products: Array<{
    id: string;
    name: string;
    autoIssue: boolean;
    stockFree: number;
    needsProfilePin?: boolean;
    isBundle?: boolean;
    bundleSources?: Array<{ id: string; name: string }>;
  }>;
  credentials: Array<{
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
  }>;
  sheetsSync?: {
    at: string | null;
    ok: boolean;
    imported: number;
    deactivated: number;
    byService?: Record<string, number>;
    errors?: string[];
  };
};

export default async function AdminStock() {
  const data = await backendJson<StockData>("/api/admin/stock");

  return (
    <>
      <div className="adm-head">
        <div>
          <h1>Склад</h1>
          <p className="adm-sub">Акаунти для автовидачі: логін, пароль і 2FA-код у кабінеті після оплати</p>
        </div>
      </div>
      <StockPanel
        products={data?.products ?? []}
        credentials={data?.credentials ?? []}
        sheetsSync={data?.sheetsSync}
      />
    </>
  );
}
