import type { BackendCart, ChatResponse, Confirmation, Product } from './types';
import { catalog } from './demoCatalog';

// Temporary frontend adapter. Set VITE_API_MODE=live after backend integration.
export const live = import.meta.env.VITE_API_MODE === 'live';
export { catalog };

async function request<T>(path: string, body?: unknown, method = 'POST'): Promise<T> {
  const response = await fetch(path, { method, credentials: 'include',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body) });
  if (!response.ok) throw new Error(`Сервер недоступен или отклонил запрос (${response.status}). Попробуйте ещё раз.`);
  return response.json();
}

let session: Promise<string> | undefined;
async function getSessionId(): Promise<string> {
  session ??= request<{ session_id: string }>('/api/v1/sessions')
    .then(response => response.session_id)
    .catch(error => { session = undefined; throw error; });
  return session;
}

export async function sendMessage(message: string): Promise<ChatResponse> {
  if (live) {
    const sessionId = await getSessionId();
    const response = await request<{
      answer: string;
      products: Array<Partial<Product> & { id: number; name: string; data_source: 'snapshot' | 'synthetic' }>;
      pending_confirmation: null | { confirmation_id: string };
    }>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/messages`, { message });
    return {
      message: response.answer,
      products: response.products.map(product => ({
        ...product,
        currency: product.currency ?? 'KZT',
        image: product.image ?? null,
        url: product.url ?? null,
        quantity: product.quantity ?? null,
        stores: product.stores ?? [],
        description: product.description ?? null,
        properties: product.properties ?? {},
        warnings: product.warnings ?? [],
      } as Product)),
      proposal: null,
      cart: null,
      cart_url: null,
      warnings: response.products.flatMap(product => product.warnings ?? []),
      data_mode: response.products.some(product => product.data_source === 'synthetic') ? 'demo' : 'snapshot',
    };
  }
  const query = message.toLowerCase().trim();
  const words = query.match(/[\p{L}\p{N}_-]+/gu)?.filter(word => word.length > 2) ?? [];
  const ranked = catalog.map(product => {
    const text = `${product.name} ${product.article} ${product.id}`.toLowerCase();
    const exact = words.includes(product.article.toLowerCase()) || words.includes(String(product.id));
    return { product, score: (exact ? 100 : 0) + words.reduce((sum, word) => sum + (text.includes(word) ? 1 : 0), 0) };
  }).filter(item => item.score > 0).sort((a, b) => b.score - a.score);
  let products = ranked.filter(item => item.score === ranked[0]?.score).slice(0, 3).map(item => item.product);
  let answer = products.length ? 'Вот совпадения в предоставленной выгрузке. Откройте карточку для подробностей. Остатки неизвестны, если их нет в данных.' : 'В локальной выборке не найдено совпадений. Попробуйте название, артикул или ID товара.';
  if (/достав|оплат|сертификат/.test(query)) {
    products = []; answer = 'В предоставленной выгрузке нет сертификатов и условий доставки или оплаты. Эти сведения нужно уточнить у менеджера.';
  } else if (/корзин|добав/.test(query)) {
    products = []; answer = 'Корзина ещё не подключена. Сейчас доступен поиск по выгрузке; добавление станет доступно после интеграции серверного подтверждения.';
  } else if (query.includes('алматы') && products.some(p => p.id === 1001)) {
    answer = 'В демо-каталоге для DEMO-BREAKER-40A в Алматы — 12 шт., цена — 26 930 ₸. Это синтетические данные для демонстрации.';
  }
  return { message: answer, products, proposal: null, cart: null, cart_url: null,
    warnings: products.flatMap(product => product.warnings), data_mode: 'demo' };
}

export async function createConfirmation(product: Product, quantity = 1): Promise<Confirmation> {
  if (!live) {
    return { confirmation_id: `demo-${product.id}-${Date.now()}`, items: [{ product_id: String(product.id), quantity, city: 'Алматы', location_id: String(product.stores[0]?.id ?? 'demo') }], expires_at: new Date(Date.now() + 5 * 60_000).toISOString() };
  }
  const sessionId = await getSessionId();
  return request<Confirmation>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/confirmations`, [{ product_id: String(product.id), quantity, city: 'Алматы', location_id: product.stores[0] ? String(product.stores[0].id) : null }]);
}

export async function confirmConfirmation(confirmationId: string): Promise<BackendCart> {
  if (!live) return { session_id: 'demo', items: [], cart_url: '#cart' };
  const sessionId = await getSessionId();
  return request<BackendCart>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/confirmations/${encodeURIComponent(confirmationId)}/confirm`);
}

export async function getCart(): Promise<BackendCart> {
  if (!live) return { session_id: 'demo', items: [], cart_url: '#cart' };
  const sessionId = await getSessionId();
  return request<BackendCart>(`/api/v1/sessions/${encodeURIComponent(sessionId)}/cart`, undefined, 'GET');
}
