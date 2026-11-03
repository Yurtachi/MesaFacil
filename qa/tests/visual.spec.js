const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const { states, adminState, shot, layoutProblems } = require('./helpers');

const S = states();
const publicPages = [
  ['01-home', '/'],
  ['02-mesa-livre', '/mesa/01'],
  ['03-aguardando-pagamento', `/mesa/02?pedido=${S.aguardando}`],
  ['04-processando', `/mesa/03?pedido=${S.processando}`],
  ['05-enviando-credito', `/mesa/04?pedido=${S.credito}`],
  ['06-aperte-o-botao', `/mesa/05?pedido=${S.botao}`],
  ['07-liberada', `/mesa/06?pedido=${S.concluido}`],
  ['08-recusado', `/mesa/07?pedido=${S.recusado}`],
  ['09-em-analise', `/mesa/08?pedido=${S.analise}`],
  ['10-mesa-em-uso', '/mesa/02'],
  ['11-mesa-inexistente', '/mesa/77'],
  ['12-admin-login', '/admin'],
];
const adminPages = [
  ['13-admin-mesas', '/admin#mesas'], ['14-admin-historico', '/admin#historico'],
  ['15-admin-auditoria', '/admin#auditoria'], ['16-admin-ajustes', '/admin#ajustes'], ['17-placas', '/admin/placas'],
];

async function check(page, project, name) {
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);
  await page.waitForFunction(() => document.getAnimations().filter(a => a.playState === 'running' && a.effect?.getComputedTiming().iterations !== Infinity).length === 0, null, { timeout: 6000 }).catch(() => {});
  await page.waitForTimeout(400); // fim das animacoes de entrada
  const problems = await layoutProblems(page);
  await shot(page, project, name);
  const axe = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa']).analyze();
  const bad = axe.violations.map(v => `${v.id} (${v.impact}): ${v.nodes.slice(0, 2).map(n => n.target.join(' ')).join(' | ')}`);
  expect(problems, `layout em ${name}`).toEqual([]);
  expect(bad, `axe em ${name}`).toEqual([]);
}

for (const [name, url] of publicPages) {
  test(`publico ${name}`, async ({ page }, info) => {
    await page.goto(url);
    await expect(page.locator('main')).toBeVisible();
    await check(page, info.project.name, name);
  });
}

test.describe('admin', () => {
  test.use({ storageState: adminState });
  for (const [name, url] of adminPages) {
    test(`admin ${name}`, async ({ page }, info) => {
      await page.goto(url);
      await expect(page.locator('main')).toBeVisible();
      await check(page, info.project.name, name);
    });
  }
});
