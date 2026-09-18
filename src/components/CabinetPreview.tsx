import { ServiceIcon } from "./ServiceIcon";

/**
 * Показує, як виглядає кабінет після покупки.
 * Дані тут навмисно вигадані — це ілюстрація, а не чиїсь справжні підписки.
 */
const SAMPLE = [
  { name: "Netflix Premium", icon: "netflix", color: "#E50914", note: "Окремий профіль",
    left: "18 днів", pct: 62, warn: false },
  { name: "ChatGPT Plus", icon: "openai", color: "#10A37F", note: "Доступ у кабінеті",
    left: "4 дні", pct: 13, warn: true },
  { name: "Claude Pro", icon: "claude", color: "#D97757", note: "Підвищені ліміти",
    left: "60 днів", pct: 84, warn: false },
];

export function CabinetPreview() {
  return (
    <div className="preview" aria-hidden>
      <div className="preview-bar">
        <span className="preview-title">Мої підписки</span>
        <span className="preview-chip">@vlad_k</span>
      </div>

      {SAMPLE.map((s) => (
        <div className="preview-row" key={s.name}>
          <span className="preview-mark">
            <ServiceIcon slug={s.icon} color={s.color} letter={s.name.charAt(0)} size={30} />
          </span>
          <span className="preview-txt">
            <b>{s.name}</b>
            <small>{s.note}</small>
            <span className="preview-track">
              <i className={s.warn ? "warn" : ""} style={{ width: `${s.pct}%` }} />
            </span>
          </span>
          <span className={`preview-left${s.warn ? " warn" : ""}`}>{s.left}</span>
        </div>
      ))}

      <p className="preview-foot">Коди підтвердження — кнопкою, тут же</p>
    </div>
  );
}
