const { test, expect } = require('@playwright/test');
const { adminState, shot } = require('./helpers');

// Jornada completa no navegador (modo demonstracao) + seguranca de interface.
test('cliente: pagar (simulado) -> aguardar botao -> mesa liberada', async ({ page, request }, info) => {
  test.skip(info.project.name !== 'w390', 'jornada executada em 390px');
  const keys = require('../.tmp/keys.json');
  const dev = { Authorization: `Bearer ${keys['01']}` };
  await page.goto('/mesa/01');
  const cta = page.getByRole('button', { name: /Pagar R\$ 5,00/ });
  await expect(cta).toBeVisible();
  const box = await cta.boundingBox();
  expect(box.y + box.height).toBeLessThanOrEqual(800); // CTA na primeira tela
  await cta.click();
  await expect(page.getByRole('heading', { name: 'Aguardando o pagamento' })).toBeVisible();
  await page.getByRole('button', { name: 'Simular pagamento aprovado' }).click();
  await expect(page.getByRole('heading', { name: 'Pagamento aprovado' })).toBeVisible();
  // controlador busca o credito e depois conclui o pulso
  const cmd = (await (await request.get('/api/dispositivos/01/proximo.txt', { headers: dev })).text()).trim();
  await expect(page.getByText('Mesa pronta')).toBeVisible({ timeout: 8000 });
  await expect(page.getByRole('heading', { name: 'Mesa liberada' })).toHaveCount(0); // 200 de entrega nao e liberacao
  await request.post('/api/dispositivos/01/confirmar', { data: { comando: cmd, duracao_ms: 350 }, headers: dev });
  await expect(page.getByRole('heading', { name: 'Mesa liberada' })).toBeVisible({ timeout: 8000 });
  await shot(page, 'fluxo', 'cliente-liberada');
  await page.reload(); // estado vem do servidor
  await expect(page.getByRole('heading', { name: 'Mesa liberada' })).toBeVisible();
});

test('cliente: pagamento recusado permite tentar de novo', async ({ page }, info) => {
  test.skip(info.project.name !== 'w390');
  await page.goto('/mesa/02?pedido=');
  await page.goto('/mesa/10');
  await page.getByRole('button', { name: /Pagar/ }).click();
  await page.getByRole('button', { name: 'Simular recusa' }).click();
  await expect(page.getByRole('heading', { name: 'Pagamento recusado' })).toBeVisible();
  await page.getByRole('button', { name: 'Tentar de novo' }).click();
  await expect(page.getByRole('button', { name: /Pagar/ })).toBeVisible();
});

test('sem rolagem horizontal ao dar zoom 200% e teclado navega o checkout', async ({ page }, info) => {
  test.skip(info.project.name !== 'w390');
  await page.goto('/mesa/07');
  await page.keyboard.press('Tab');
  await expect(page.locator('.skip')).toBeFocused();
  for (let i = 0; i < 3; i++) await page.keyboard.press('Tab');
  const focused = await page.evaluate(() => document.activeElement.tagName);
  expect(['A', 'BUTTON']).toContain(focused);
});

test('conteudo hostil e escapado (XSS) no painel e na home', async ({ page, browser }, info) => {
  test.skip(info.project.name !== 'w390');
  let dialogs = 0;
  page.on('dialog', d => { dialogs++; d.dismiss(); });
  await page.goto('/mesa/10');
  await expect(page.getByText('<img src=x onerror=alert(1)>').first()).toBeVisible();
  const ctx = await browser.newContext({ storageState: adminState });
  const p2 = await ctx.newPage();
  p2.on('dialog', d => { dialogs++; d.dismiss(); });
  await p2.goto('/admin');
  await expect(p2.getByText('<img src=x onerror=alert(1)>').first()).toBeVisible();
  expect(await p2.locator('img[src="x"]').count()).toBe(0);
  expect(dialogs).toBe(0);
  await ctx.close();
});

test('admin: login pela interface, erro de senha, liberacao manual com motivo e logout', async ({ page }, info) => {
  test.skip(info.project.name !== 'w390');
  await page.goto('/admin');
  await page.getByLabel('Senha').fill('senha errada');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page.getByRole('alert')).toContainText('Senha incorreta');
  await page.getByLabel('Senha').fill('qa-senha-123');
  await page.getByRole('button', { name: 'Entrar' }).click();
  await expect(page.getByRole('heading', { name: /mesas/ })).toBeVisible();
  const card = page.getByRole('article', { name: 'Mesa 11 reserva' });
  await card.getByRole('button', { name: 'Liberar' }).click();
  await page.getByRole('button', { name: 'Autorizar liberação' }).click(); // motivo obrigatorio: nao envia vazio
  await expect(page.getByLabel('Motivo')).toBeFocused();
  await page.getByLabel('Motivo').fill('teste automatizado de liberação');
  await page.getByRole('button', { name: 'Autorizar liberação' }).click();
  await expect(page.getByText('Crédito criado')).toBeVisible();
  await page.goto('/admin#auditoria');
  await expect(page.getByText('teste automatizado de liberação')).toBeVisible();
  await shot(page, 'fluxo', 'admin-auditoria');
  await page.getByRole('button', { name: 'Sair' }).click();
  await expect(page.getByRole('heading', { name: 'Entrar' })).toBeVisible();
});

test('admin sem sessao: rotas e placas redirecionam ao login', async ({ page, request }) => {
  test.skip(test.info().project.name !== 'w390');
  expect((await request.get('/api/admin/resumo')).status()).toBe(401);
  await page.goto('/admin/placas');
  await expect(page).toHaveURL(/\/admin$/);
});

test('modo reduzido de movimento nao esconde conteudo', async ({ browser }, info) => {
  test.skip(info.project.name !== 'w390');
  const ctx = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 390, height: 800 } });
  const page = await ctx.newPage();
  await page.goto('/mesa/05');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await ctx.close();
});
