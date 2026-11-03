const { test, expect } = require('@playwright/test');
const { shot } = require('./helpers');

// QA de animação (390 px). Verifica pose do palco, ordem causal (caçapa só após ACK), interrupções, movimento reduzido,
// rede, cliques múltiplos, redimensionamento, paisagem e fluidez (frames/longtasks).
const keys = () => require('../.tmp/keys.json');
const dev = m => ({ Authorization: `Bearer ${keys()[m]}` });
const pose = page => page.evaluate(() => {
  const g = document.querySelectorAll('.stage .ballg'); const el = g[g.length - 1];
  const m = new DOMMatrix(getComputedStyle(el).transform); const o = getComputedStyle(el).opacity;
  return { x: Math.round(m.m41), y: Math.round(m.m42), opacity: Number(o), etapa: document.querySelector('.stage').dataset.etapa };
});
const running = page => page.evaluate(() => document.getAnimations().filter(a => a.playState === 'running' && a.effect?.target?.closest?.('.stage')).length);
async function openAndOrder(page, mesa) {
  await page.goto(`/mesa/${mesa}`);
  await page.getByRole('button', { name: /Pagar/ }).click();
  await expect(page.getByRole('heading', { name: 'Aguardando o pagamento' })).toBeVisible();
}
const ack = async (request, mesa) => {
  const cmd = (await (await request.get(`/api/dispositivos/${mesa}/proximo.txt`, { headers: dev(mesa) })).text()).trim();
  await request.post(`/api/dispositivos/${mesa}/confirmar`, { data: { comando: cmd, duracao_ms: 350 }, headers: dev(mesa) });
};

test.beforeEach(({}, info) => test.skip(info.project.name !== 'w390', 'animação validada em 390 px'));

test('tacada após aprovação: bola vai ao ponto do botão e NÃO à caçapa; caçapa só após ACK', async ({ page, request }) => {
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  await openAndOrder(page, '01');
  await page.getByRole('button', { name: 'Simular pagamento aprovado' }).click();
  await expect(page.getByRole('heading', { name: 'Pagamento aprovado' })).toBeVisible();
  await expect.poll(() => running(page), { timeout: 1500 }).toBeGreaterThan(0);
  await page.waitForTimeout(2300);
  let p = await pose(page);
  expect(p.etapa).toBe('aguardando_botao');
  expect(Math.abs(p.x - 190)).toBeLessThanOrEqual(2); expect(p.opacity).toBe(1);
  expect(await running(page)).toBe(0);
  await shot(page, 'animacao', 'bola-no-ponto-do-botao');
  await ack(request, '01');
  await expect(page.getByRole('heading', { name: 'Mesa liberada' })).toBeVisible({ timeout: 8000 });
  await page.waitForTimeout(1800);
  p = await pose(page);
  expect(p.etapa).toBe('concluido'); expect(p.opacity).toBe(0);
  await shot(page, 'animacao', 'bola-na-cacapa');
  expect(errors).toEqual([]);
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Mesa liberada' })).toBeVisible();
  expect(await running(page)).toBe(0);
  expect((await pose(page)).opacity).toBe(0);
});

test('interrupção: ACK chega durante a tacada, pose final consistente e sem animações órfãs', async ({ page, request }) => {
  await openAndOrder(page, '12');
  await page.getByRole('button', { name: 'Simular pagamento aprovado' }).click();
  await page.waitForTimeout(250);
  await ack(request, '12');
  await expect(page.getByRole('heading', { name: 'Mesa liberada' })).toBeVisible({ timeout: 8000 });
  await expect.poll(() => running(page), { timeout: 5000 }).toBe(0);
  const p = await pose(page);
  expect(p.etapa).toBe('concluido'); expect(p.opacity).toBe(0);
});

test('movimento reduzido: estado final imediato, nenhuma animação do palco', async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: 'reduce', viewport: { width: 390, height: 800 } });
  const page = await ctx.newPage();
  await openAndOrder(page, '13');
  await page.getByRole('button', { name: 'Simular pagamento aprovado' }).click();
  await expect(page.getByRole('heading', { name: 'Pagamento aprovado' })).toBeVisible();
  await page.waitForTimeout(150);
  expect(await running(page)).toBe(0);
  expect(Math.abs((await pose(page)).x - 190)).toBeLessThanOrEqual(2);
  await ctx.close();
});

test('cliques múltiplos em aprovar geram uma única requisição; rede cai durante a transição sem erro', async ({ page }) => {
  const errors = []; page.on('pageerror', e => errors.push(e.message));
  let pays = 0; await page.route('**/api/demo/pagar', r => { pays++; r.continue(); });
  await openAndOrder(page, '14');
  const b = page.getByRole('button', { name: 'Simular pagamento aprovado' });
  await b.dblclick(); await b.click({ force: true, timeout: 500 }).catch(() => {});
  await expect(page.getByRole('heading', { name: 'Pagamento aprovado' })).toBeVisible();
  expect(pays).toBe(1);
  await page.context().setOffline(true);
  await expect(page.getByText('Sem conexão com o servidor')).toBeVisible({ timeout: 8000 });
  await page.setViewportSize({ width: 360, height: 780 });
  await page.context().setOffline(false);
  await page.waitForTimeout(2500);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  expect(errors).toEqual([]);
});

test('paisagem em celular: conteúdo acessível e sem rolagem horizontal', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 844, height: 390 }, hasTouch: true });
  const page = await ctx.newPage();
  await page.goto('/mesa/05');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await shot(page, 'animacao', 'paisagem-844x390');
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await ctx.close();
});

test('abertura da home: tacada roda uma vez por sessão, não bloqueia cliques e fica estática depois', async ({ page }) => {
  await page.goto('/');
  await expect.poll(() => running(page), { timeout: 1500 }).toBeGreaterThan(0);
  await page.getByRole('link', { name: /Mesa 08/ }).click();
  await expect(page).toHaveURL(/\/mesa\/08/);
  await page.goto('/');
  await page.waitForTimeout(500);
  expect(await running(page)).toBe(0);
});

test('fluidez da sequência: sem tarefas longas e sem lacunas grandes entre quadros', async ({ page }) => {
  await openAndOrder(page, '15');
  await page.evaluate(() => {
    window.__frames = []; window.__long = 0;
    new PerformanceObserver(l => { window.__long += l.getEntries().length; }).observe({ entryTypes: ['longtask'] });
    let last = performance.now(); const t0 = last;
    const loop = t => { window.__frames.push(t - last); last = t; if (t - t0 < 2600) requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  });
  await page.getByRole('button', { name: 'Simular pagamento aprovado' }).click();
  await page.waitForTimeout(2800);
  const r = await page.evaluate(() => ({ quadros: window.__frames.length, maxMs: Math.round(Math.max(...window.__frames)), tarefasLongas: window.__long, mediaMs: +(window.__frames.reduce((a, b) => a + b, 0) / window.__frames.length).toFixed(1) }));
  console.log('FLUIDEZ', JSON.stringify(r));
  expect(r.quadros).toBeGreaterThan(60); expect(r.maxMs).toBeLessThan(250); expect(r.tarefasLongas).toBeLessThanOrEqual(1);
});
