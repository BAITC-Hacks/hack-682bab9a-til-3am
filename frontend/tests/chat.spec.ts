import { test, expect } from '@playwright/test';

test('desktop layout and exact article with stock warning', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: /Подберём/ })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Отправить сообщение' })).toBeDisabled();
  await page.screenshot({ path: 'screenshots/desktop.png', fullPage: true });
  await page.getByRole('button', { name: '200300285_ в Алматы ↗' }).click();
  await expect(page.locator('.messages')).toContainText('в Алматы — 5 шт.');
  await expect(page.locator('.warning')).toContainText('250 А');
  await expect(page.locator('.messages .product')).toHaveCount(1);
  await page.screenshot({ path: 'screenshots/search.png', fullPage: true });
  expect(errors).toEqual([]);
});

test('article punctuation, missing image and unknown stock', async ({ page }) => {
  await page.route('**/upload/**', route => route.abort());
  await page.goto('/');
  await page.getByLabel('Ваш вопрос').fill('Есть 310100080_?');
  await page.getByLabel('Ваш вопрос').press('Enter');
  const product = page.locator('.messages .product');
  await expect(product).toHaveCount(1);
  await expect(product).toContainText('Наличие не уточнено');
  await expect(product).toContainText('Нет фото');
});

test('no fabricated FAQ, cart or unknown product; latest response is visible', async ({ page }) => {
  await page.goto('/');
  for (const [query, answer] of [
    ['zzzzunknown', 'не найдено совпадений'],
    ['Как оплатить?', 'нет сертификатов и условий'],
    ['Добавь в корзину', 'Корзина ещё не подключена'],
    ['200300285_', 'Вот совпадения'],
    ['200300285_', 'Вот совпадения'],
  ]) {
    await page.getByLabel('Ваш вопрос').fill(query);
    await page.getByLabel('Ваш вопрос').press('Enter');
    await expect(page.locator('.message.assistant').last()).toContainText(answer);
  }
  await expect.poll(() => page.locator('.messages').evaluate(element =>
    element.scrollHeight - element.clientHeight - element.scrollTop)).toBeLessThan(5);
});

test('mobile layout fits screen and search works', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({ path: 'screenshots/mobile.png', fullPage: true });
  await page.getByRole('button', { name: 'Реле RM17UAS16 ↗' }).click();
  await expect(page.locator('.messages .product').first()).toContainText('RM17UAS16');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);
  await page.screenshot({ path: 'screenshots/mobile-search.png', fullPage: true });
});
