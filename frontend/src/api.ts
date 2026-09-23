import page1 from '../../api_products.json';
import page2 from '../../api_products_page2.json';
import detail from '../../api_products_detail.json';
import type { ChatResponse, Product } from './types';

// Temporary frontend adapter. Set VITE_API_MODE=live after backend integration.
export const live = import.meta.env.VITE_API_MODE === 'live';
export const catalog: Product[] = [...page1.items, ...page2.items].map(item => {
  const full = item.id === detail.id ? detail : null;
  return { ...item, currency: 'KZT', quantity: full?.quantity ?? null,
    stores: full?.stores ?? [], description: full?.description ?? null,
    properties: full?.properties ?? {}, data_source: 'snapshot',
    warnings: full ? ['Расхождение данных: в названии и описании — 160 А, в свойствах — 250 А. Требуется уточнение.'] : [],
  };
});

async function request<T>(path: string, body: object): Promise<T> {
  const response = await fetch(path, { method: 'POST', credentials: 'include',
    headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!response.ok) throw new Error(`Сервер недоступен или отклонил запрос (${response.status}). Попробуйте ещё раз.`);
  return response.json();
}

let session: Promise<unknown> | undefined;
export async function sendMessage(message: string): Promise<ChatResponse> {
  if (live) {
    session ??= request('/api/session', {}).catch(error => { session = undefined; throw error; });
    await session;
    return request<ChatResponse>('/api/chat', { message });
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
  } else if (query.includes('алматы') && products.some(p => p.id === detail.id)) {
    answer = 'По выгрузке для артикула 200300285_ в Алматы — 5 шт., цена — 64 920 ₸. Это сохранённые данные, актуальность нужно уточнить.';
  }
  return { message: answer, products, proposal: null, cart: null, cart_url: null,
    warnings: products.flatMap(product => product.warnings), data_mode: 'snapshot' };
}
