import type { Product } from './types';

// Synthetic fixture for a public demo. It is not an export from ekt.kz.
export const catalog: Product[] = [
  { id: 1001, article: 'DEMO-BREAKER-40A', name: 'Демо автоматический выключатель 3P 40А', price: 26930, currency: 'KZT', image: null, url: null, quantity: 12, stores: [{ id: 1, name: 'Демо склад Алматы', quantity: 12 }], description: 'Синтетическая карточка для демонстрации поиска.', properties: { poles: 3, current: '40 A' }, data_source: 'synthetic', warnings: [] },
  { id: 1002, article: 'DEMO-RELAY-RM17', name: 'Демо реле контроля напряжения RM17', price: 49490, currency: 'KZT', image: null, url: null, quantity: null, stores: [], description: 'Синтетическая карточка; наличие не задано.', properties: { type: 'relay' }, data_source: 'synthetic', warnings: [] },
  { id: 1003, article: 'DEMO-LAMP-30W', name: 'Демо светильник LED 30W 4000K', price: 1810, currency: 'KZT', image: null, url: null, quantity: 0, stores: [{ id: 1, name: 'Демо склад Алматы', quantity: 0 }], description: 'Синтетическая карточка для сценария аналога.', properties: { power: '30 W', color: '4000 K' }, data_source: 'synthetic', warnings: [] },
];
