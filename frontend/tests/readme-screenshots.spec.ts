import { test, expect, type Page } from '@playwright/test';

// Regenerates the screenshots used in README.md (docs/screenshots/*.png).
// Run with the backend on :8000 and VITE_API_MODE=live:
//   $env:SCREENSHOTS="1"; npx playwright test tests/readme-screenshots.spec.ts
test.skip(!process.env.SCREENSHOTS, 'Set SCREENSHOTS=1 with the backend running on :8000');

const out = (name: string) => `../docs/screenshots/${name}.png`;

// Let long answers render fully instead of inside the chat's scroll box.
async function open(page: Page) {
  await page.goto('/');
  await page.addStyleTag({ content: '.messages{max-height:none!important;height:auto!important;overflow:visible!important}' });
}

async function ask(page: Page, text: string) {
  const before = await page.locator('.message.assistant').count();
  await page.getByLabel('Ваш вопрос').fill(text);
  await page.getByLabel('Ваш вопрос').press('Enter');
  await expect(page.locator('.message.assistant')).toHaveCount(before + 1, { timeout: 25_000 });
  const last = page.locator('.message.assistant').last();
  await last.scrollIntoViewIfNeeded();
  return last;
}

test('desktop scenario', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.screenshot({ path: out('01-start') });
  await page.addStyleTag({ content: '.messages{max-height:none!important;height:auto!important;overflow:visible!important}' });

  const stock = await ask(page, 'Есть 027228 в Алматы?');
  await stock.screenshot({ path: out('02-stock-specs') });

  const proposal = await ask(page, 'добавь 2 штуки');
  await proposal.screenshot({ path: out('03-proposal') });

  await page.getByRole('button', { name: 'Да, добавить' }).last().click();
  await expect(page.locator('#cart')).toContainText('2 шт.');
  await page.locator('#cart').scrollIntoViewIfNeeded();
  await page.locator('#cart').screenshot({ path: out('04-cart') });

  const refused = await ask(page, 'добавь 4 штуки');
  await refused.screenshot({ path: out('05-stock-limit') });

  const analog = await ask(page, 'Нужен 027230');
  await analog.screenshot({ path: out('06-analog') });

  const faq = await ask(page, 'Условия доставки и оплаты?');
  await faq.screenshot({ path: out('07-terms') });
});

test('kazakh', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page);
  await ask(page, 'Сәлеметсіз бе! 027228 Астанада бар ма?');
  await ask(page, 'екеуін себетке қосыңызшы');
  const confirmed = await ask(page, 'иә, қосыңыз');
  await confirmed.screenshot({ path: out('08-kazakh') });
});

test('mobile', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/');
  await ask(page, 'Есть 027228 в Алматы?');
  await page.screenshot({ path: out('09-mobile') });
});
