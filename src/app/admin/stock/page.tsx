import { backendJson } from "@/lib/backend";
import { StockPanel } from "./StockPanel";

export const dynamic = "force-dynamic";

type StockData = {
  products: Array<{ id: string; name: string; autoIssue: boolean; stockFree: number; needsProfilePin?: boolean }>;
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
    profileSlots?: Array<{ num: string }>;
  }>;
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
      />
    </>
  );
}
