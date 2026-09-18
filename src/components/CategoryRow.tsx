import Link from "next/link";
import { CategoryIcon } from "./CategoryIcon";
import { CoverPhoto } from "./CoverPhoto";

export type CatItem = {
  id: string;
  slug: string;
  name: string;
  icon: string;
  color: string;
  photoUrl?: string | null;
};

/**
 * Стрічка категорій. Це посилання, а не фільтр на місці:
 * з головної вони ведуть у каталог, у каталозі — перемикають вибірку.
 */
export function CategoryRow({ categories, active, showAll = true }:
  { categories: CatItem[]; active?: string | null; showAll?: boolean }) {
  if (!categories.length) return null;

  return (
    <div className="cat-row">
      {showAll && (
        <Link className={`cat-chip${!active ? " on" : ""}`} href="/catalog">Усі</Link>
      )}
      {categories.map((c) => (
        <Link
          key={c.id}
          className={`cat-chip${active === c.slug ? " on" : ""}`}
          href={`/catalog?cat=${c.slug}`}
        >
          <CoverPhoto
            src={c.photoUrl}
            className="cat-chip-img"
            fallback={<CategoryIcon icon={c.icon} color={active === c.slug ? "#FFFFFF" : c.color} />}
          />
          {c.name}
        </Link>
      ))}
    </div>
  );
}
