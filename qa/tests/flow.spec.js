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
  await expect(page.getByText('Aperte o botão da mesa 01')).toBeVisible({ timeout: 8000 });
  await expect(page.getByRole('heading', { name: 'Mesa liberada' })).toHaveCount(0); // 200 de entrega nao e liberacao
  await request.post('/api/dispositivos/01/confirmar', { data: { comando: cmd, duracao_ms: 350 }, headers: dev });
  await expect(page.getByRole('heading', { name: 'Mesa liberada' })).toBeVisible({ timeout: 8000 });
  await page.waitForTimeout(1800);
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

test('teclado: skip link primeiro e Tab alcança o botão principal do checkout', async ({ page }, info) => {
  test.skip(info.project.name !== 'w390');
  await page.goto('/mesa/07');
  const cta = page.getByRole('button', { name: /Pagar/ });
  await expect(cta).toBeVisible(); // espera a tela montar antes de tabular (evita corrida em CI)
  await page.keyboard.press('Tab');
  await expect(page.locator('.skip')).toBeFocused();
  for (let i = 0; i < 8 && !(await cta.evaluate(el => el === document.activeElement)); i++) await page.keyboard.press('Tab');
  await expect(cta).toBeFocused();
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

test('seguranca do frontend: sem violacao de CSP, sem requisicao externa, sem token em respostas publicas', async ({ page, browser }, info) => {
  test.skip(info.project.name !== 'w390');
  const external = [], problems = [];
  const origin = new URL(info.config.projects[0].use.baseURL || 'http://127.0.0.1:8791').origin;
  for (const p of [page]) {
    p.on('request', r => { if (!r.url().startsWith(origin) && !r.url().startsWith('data:') && !r.url().startsWith('blob:')) external.push(r.url()); });
    p.on('console', m => { if (['error', 'warning'].includes(m.type())) problems.push(m.text()); });
    p.on('pageerror', e => problems.push(e.message));
  }
  for (const url of ['/', '/mesa/01', '/mesa/77', '/admin']) { await page.goto(url); await page.waitForLoadState('networkidle'); await page.waitForTimeout(500); }
  const bodies = [];
  page.on('response', async r => { if (r.url().includes('/api/') && !r.url().includes('/api/admin')) bodies.push(await r.text().catch(() => '')); });
  await page.goto('/mesa/01'); await page.waitForTimeout(800);
  const keys = Object.values(require('../.tmp/keys.json'));
  for (const b of bodies) for (const k of keys) expect(b).not.toContain(k);
  expect(external).toEqual([]);
  expect(problems.filter(t => !t.includes('404'))).toEqual([]); // 404 esperado em /mesa/77
});

test('admin: API administrativa nao responde sem sessao mesmo com o frontend novo', async ({ request }, info) => {
  test.skip(info.project.name !== 'w390');
  for (const path of ['/api/admin/resumo', '/api/admin/auditoria', '/api/admin/backup']) expect((await request.get(path)).status()).toBe(401);
  expect((await request.post('/api/admin/mesas/01/liberar', { data: { motivo: 'sem sessao' } })).status()).toBe(401);
  const r = await request.get('/api/admin/estado');
  expect(await r.json()).toEqual({ autenticado: false });
});
