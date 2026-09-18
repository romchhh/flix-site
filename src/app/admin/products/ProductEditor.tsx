"use client";
import { useState } from "react";
import { saveProduct } from "../actions";

type P = {
  id: string; slug: string; name: string; icon: string; color: string;
  description: string; features: string; faq: string; deliveryNote: string;
  price: number; days: number;
  price3: number; price6: number; price12: number; sortOrder: number;
  visible: boolean; autoIssue: boolean; recurring: boolean; categoryId: string | null;
};

type Cat = { id: string; name: string };

export function ProductEditor({ trigger, product, categories }:
  { trigger: string; product?: P; categories: Cat[] }) {
  const [open, setOpen] = useState(false);
  if (!open) {
    return (
      <button className={`btn sm${product ? " ghost" : ""}`} onClick={() => setOpen(true)}>{trigger}</button>
    );
  }

  return (
    <>
      <div onClick={() => setOpen(false)}
        style={{ position: "fixed", inset: 0, background: "rgba(10,11,14,.42)", zIndex: 40 }} />
      <div style={{ position: "fixed", top: 0, right: 0, bottom: 0, width: "min(480px,100%)",
        background: "#fff", zIndex: 50, overflowY: "auto", padding: "24px 26px 40px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <h2 style={{ fontSize: 19, fontWeight: 800, letterSpacing: "-.02em" }}>
            {product ? product.name : "Новий товар"}
          </h2>
          <button onClick={() => setOpen(false)}
            style={{ background: "none", border: 0, cursor: "pointer", fontSize: 24, color: "var(--muted)" }}>×</button>
        </div>

        <form action={async (fd) => { await saveProduct(fd); setOpen(false); }}>
          {product && <input type="hidden" name="id" value={product.id} />}

          <div className="field"><label>Назва</label>
            <input name="name" defaultValue={product?.name} required /></div>

          <div className="f2">
            <div className="field"><label>Адреса (slug)</label>
              <input name="slug" defaultValue={product?.slug} placeholder="netflix" required /></div>
            <div className="field"><label>Порядок</label>
              <input name="sortOrder" type="number" defaultValue={product?.sortOrder ?? 0} /></div>
          </div>

          <div className="field"><label>Категорія</label>
            <select name="categoryId" defaultValue={product?.categoryId ?? ""}>
              <option value="">без категорії</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>

          <div className="field"><label>Опис у каталозі</label>
            <textarea name="description" rows={3} defaultValue={product?.description} /></div>

          <div className="field"><label>Що входить — по рядку на пункт</label>
            <textarea name="features" rows={4} defaultValue={product?.features} /></div>

          <div className="field"><label>Рядок під кнопкою оплати</label>
            <input name="deliveryNote" defaultValue={product?.deliveryNote}
              placeholder="Доступ приходить за 2–5 хвилин" /></div>

          <div className="field">
            <label>Часті питання</label>
            <textarea name="faq" rows={8} defaultValue={product?.faq}
              placeholder={"Це мій особистий акаунт?\nТак, профіль лише твій, зі своїм PIN.\n\nА якщо перестане працювати?\nЗамінимо або повернемо гроші за невикористані дні."} />
            <p className="muted" style={{ marginTop: 6 }}>
              Блоки розділяються порожнім рядком. Перший рядок блоку — питання, решта — відповідь.
            </p>
          </div>

          <div className="f3">
            <div className="field"><label>Ціна 3 міс, ₴</label>
              <input name="price3" type="number" defaultValue={product?.price3 ? product.price3 / 100 : ""} /></div>
            <div className="field"><label>Ціна 6 міс, ₴</label>
              <input name="price6" type="number" defaultValue={product?.price6 ? product.price6 / 100 : ""} /></div>
            <div className="field"><label>Ціна 12 міс, ₴</label>
              <input name="price12" type="number" defaultValue={product?.price12 ? product.price12 / 100 : ""} /></div>
          </div>
          <p className="muted" style={{ marginBottom: 16 }}>
            Порожнє поле або нуль — цей строк не продається і в каталозі не показується.
          </p>

          <div className="f2">
            <div className="field"><label>Ціна за місяць, ₴</label>
              <input name="price" type="number" defaultValue={product ? product.price / 100 : ""} /></div>
            <div className="field"><label>Днів у місяці</label>
              <input name="days" type="number" defaultValue={product?.days ?? 30} /></div>
          </div>
          <p className="muted" style={{ marginBottom: 16 }}>
            Ціна за місяць потрібна помісячному товару. Для строкового вона лише показує
            клієнту, скільки він заощаджує, беручи довший строк.
          </p>

          <label style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: "var(--ink)", marginBottom: 6 }}>
            <input type="checkbox" name="recurring" defaultChecked={product?.recurring ?? false} style={{ width: 18, height: 18 }} />
            Помісячно з автопродовженням
          </label>
          <p className="muted" style={{ marginBottom: 16 }}>
            У такого товару клієнт не обирає строк — платить ціну за місяць, далі списується щомісяця.
            Ціни за строк до нього не застосовуються.
          </p>



          <div className="f2">
            <div className="field"><label>Іконка (slug Simple Icons)</label>
              <input name="icon" defaultValue={product?.icon} placeholder="netflix" /></div>
            <div className="field"><label>Колір бренду</label>
              <input name="color" defaultValue={product?.color ?? "#2B5CF6"} placeholder="#E50914" /></div>
          </div>

          <label style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: "var(--ink)", marginBottom: 12 }}>
            <input type="checkbox" name="visible" defaultChecked={product?.visible ?? true} style={{ width: 18, height: 18 }} />
            Показувати в каталозі
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, color: "var(--ink)", marginBottom: 20 }}>
            <input type="checkbox" name="autoIssue" defaultChecked={product?.autoIssue ?? true} style={{ width: 18, height: 18 }} />
            Автовидача зі складу
          </label>

          <p className="muted" style={{ marginBottom: 16 }}>
            Без автовидачі замовлення після оплати чекатиме на тебе в розділі «Замовлення».
          </p>

          <button className="btn block" type="submit">Зберегти</button>
        </form>
      </div>
    </>
  );
}
