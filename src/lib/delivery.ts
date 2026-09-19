export const DELIVERY_NOTE_AUTO = "Доступ одразу після оплати";
export const DELIVERY_NOTE_MANUAL = "Після оплати менеджер надішле доступ у Telegram";

export function deliveryNote(autoIssue: boolean): string {
  return autoIssue ? DELIVERY_NOTE_AUTO : DELIVERY_NOTE_MANUAL;
}
