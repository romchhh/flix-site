export type Plan = {
  months: number;
  label: string;
  total: number;
  perMonth: number;
  off: number;
};

export type CatalogProduct = {
  id: string;
  botId: number;
  slug: string;
  name: string;
  icon: string;
  color: string;
  description: string;
  features: string;
  recurring: boolean;
  price: number;
  price3: number;
  price6: number;
  price12: number;
  faq: string;
  deliveryNote: string;
  visible: boolean;
  autoIssue: boolean;
  categoryId: string | null;
  categoryName?: string;
  photoUrl?: string | null;
  badge?: string | null;
  tariff?: string;
  paymentType: string;
  plans: Plan[];
};

export type CatalogCategory = {
  id: string;
  slug: string;
  name: string;
  icon: string;
  color: string;
  sortOrder: number;
  active: boolean;
  count?: number;
  photoUrl?: string | null;
};

export type SiteUser = {
  id: string;
  email: string | null;
  emailVerified: string | null;
  telegramId: number | null;
  telegramName: string | null;
  telegramPhoto?: string | null;
  botUserId: number | null;
  isAdmin: boolean;
  isGuest?: boolean;
};

export type BotSubscription = {
  id: string;
  botId: number;
  kind: "one_time" | "recurring";
  productId: string;
  name: string;
  price: number;
  months?: number;
  startsAt: string;
  expiresAt: string;
  nextPaymentAt?: string;
  status: string;
  paymentFailures?: number;
  source: string;
  slug: string;
  icon: string;
  color: string;
  photoUrl?: string | null;
  maskedCard?: string | null;
  cardType?: string | null;
  login?: string | null;
  password?: string | null;
  pin?: string | null;
  profileName?: string | null;
  hasTotp?: boolean;
  twoFaUrl?: string | null;
  deliveryId?: string | null;
  autoIssue?: boolean;
  isIptv?: boolean;
  playlistUrl?: string | null;
  deliveryInstructions?: string | null;
  accessParts?: Array<{
    label?: string | null;
    login?: string | null;
    password?: string | null;
    profileName?: string | null;
    pin?: string | null;
    hasTotp?: boolean;
    deliveryId?: string | null;
  }>;
};

export type BillingEntry = {
  id: string;
  kind: "purchase" | "charge";
  productName: string;
  productId?: number | null;
  months?: number | null;
  amount: number;
  status: string;
  paymentType?: string;
  source?: string;
  invoiceId?: string | null;
  subscriptionId?: number | null;
  createdAt: string;
  errorMessage?: string | null;
};
