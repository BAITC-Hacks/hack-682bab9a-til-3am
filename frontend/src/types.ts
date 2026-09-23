export type Product = {
  id: number; article: string; name: string; price: number;
  currency: string; image: string | null; url: string | null;
  quantity: number | null;
  stores: { id: number | string; name: string; quantity: number }[];
  description: string | null; properties: Record<string, unknown>;
  data_source: 'snapshot' | 'synthetic'; warnings: string[]; match_reason?: string;
};
export type Cart = {
  items: { product_id: number; name: string; quantity: number; store_id: number; unit_price: number; total: number }[];
  total: number; currency: string;
};
export type ChatResponse = {
  message: string; products: Product[];
  proposal: null | { id: string; product_id: number; quantity: number; store_id: number; unit_price: number; total: number };
  cart: Cart | null; cart_url: string | null; warnings: string[];
  data_mode: 'snapshot' | 'demo';
};

export type Confirmation = {
  confirmation_id: string;
  items: { product_id: string; quantity: number; city?: string | null; location_id?: string | null }[];
  expires_at: string;
};

export type BackendCart = {
  session_id: string;
  items: { product_id: string; quantity: number; city?: string | null; location_id?: string | null }[];
  cart_url: string;
};
