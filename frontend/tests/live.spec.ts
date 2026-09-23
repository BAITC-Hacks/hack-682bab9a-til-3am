import { test, expect, type Page } from '@playwright/test';

// End-to-end demo scenario against the real backend.
// Run: start the backend on :8000, set VITE_API_MODE=live in frontend/.env.local, then
//   $env:E2E_LIVE="1"; npx playwright test tests/live.spec.ts
test.skip(!process.env.E2E_LIVE, 'Set E2E_LIVE=1 with the backend running on :8000');

async function ask(page: Page, text: string) {
  const before = await page.locator('.message.assistant').count();
  await page.getByLabel('Ваш вопрос').fill(text);
  await page.getByLabel('Ваш вопрос').press('Enter');
  await expect(page.locator('.message.assistant')).toHaveCount(before + 1, { timeout: 20_000 });
  return page.locator('.message.assistant').last();
}

test('stock, specs, conflict warning and certificate', async ({ page }) => {
  await page.goto('/');
  const answer = await ask(page, 'Есть 027228 в Алматы?');
  await expect(answer).toContainText('64 920');
  await expect(answer).toContainText('5 шт.');
  await expect(answer.locator('.warning').first()).toBeVisible();
  const certificate = await ask(page, 'покажи сертификат');
  await expect(certificate).toContainText('не приложен');
});

test('cart changes only after the confirmation button', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'Есть 027228 в Алматы?');
  const proposal = await ask(page, 'добавь 2 штуки');
  await expect(proposal).toContainText('129 840');
  await expect(page.locator('#cart')).toHaveCount(0);
  await page.getByRole('button', { name: 'Да, добавить' }).last().click();
  await expect(page.locator('#cart')).toContainText('2 шт.');
  await expect(page.locator('#cart .cart-link')).toBeVisible();
});

test('text confirmation and stock limit', async ({ page }) => {
  await page.goto('/');
  await ask(page, 'Есть 027228 в Алматы?');
  await ask(page, 'добавь 4 штуки');
  await ask(page, 'да, добавь');
  await expect(page.locator('#cart')).toContainText('4 шт.');
  const refused = await ask(page, 'добавь 2 штуки');
  await expect(refused).toContainText('Добавить не получится');
});

test('out-of-stock item gets an explained analog', async ({ page }) => {
  await page.goto('/');
  const answer = await ask(page, 'Нужен 027230');
  await expect(answer).toContainText('нет в наличии');
  await expect(answer.locator('.match-reason').first()).toContainText('совпадает');
});

test('purchase terms and mobile layout', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  const answer = await ask(page, 'Условия доставки и оплаты?');
  await expect(answer).toContainText('Доставка');
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  expect(overflow).toBe(false);
  await page.screenshot({ path: 'screenshots/mobile-live.png', fullPage: true });
});
