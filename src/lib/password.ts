import bcrypt from "bcryptjs";

export const hashPassword = (p: string) => bcrypt.hash(p, 12);
export const checkPassword = (p: string, hash: string) => bcrypt.compare(p, hash);

export function passwordProblem(p: string): string | null {
  if (p.length < 8) return "Пароль має бути щонайменше 8 символів";
  if (!/[a-zA-Zа-яА-Я]/.test(p) || !/[0-9]/.test(p)) return "Додай хоча б одну літеру і одну цифру";
  return null;
}
