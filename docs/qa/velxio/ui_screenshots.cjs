// Sessao na UI do Velxio (Playwright): monta o circuito (botao em D27/GND), cola o sketch gerado, compila e executa pelo botao Run,
// aperta o botao VIRTUAL com o mouse e captura telas SEM o editor de codigo (o sketch contem o token da mesa).
// Uso: node ui_screenshots.js <sketch.ino> <saida_dir> <base_api>   ; pedidos sao criados via HTTP no backend (127.0.0.1).
const { chromium } = require('../../../qa/node_modules/playwright');
const fs = require('fs');
const [sketchPath, outDir, api] = process.argv.slice(2);
const sketch = fs.readFileSync(sketchPath, 'utf8');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
async function j(method, path, body) {
  const r = await fetch(api + path, { method, headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined });
  return r.json();
}
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1500, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'] });
  const p = await ctx.newPage();
  const shot = (name, clip) => p.screenshot({ path: `${outDir}/${name}.png`, clip: clip || { x: 680, y: 44, width: 820, height: 856 } });
  await p.goto('http://localhost:3080/editor', { waitUntil: 'networkidle' });
  await sleep(1500);
  await p.getByText('ESP32 DevKit V1').first().click();
  await sleep(3000);
  await p.getByRole('button', { name: 'Add' }).click();
  await sleep(800);
  await p.getByPlaceholder('Search components...').fill('push');
  await sleep(600);
  await p.getByText(/Push ?button/i).first().click();
  await sleep(2000);
  async function link(x1, y1, x2, y2) {
    await p.mouse.move(x1, y1); await sleep(500); await p.mouse.click(x1, y1); await sleep(400);
    await p.mouse.move((x1 + x2) / 2, (y1 + y2) / 2, { steps: 8 }); await p.mouse.move(x2, y2, { steps: 8 }); await sleep(500);
    await p.mouse.click(x2, y2); await sleep(700);
  }
  await link(748, 124, 861, 484);   // botao -> D27
  await link(748, 142, 861, 534);   // botao -> GND
  await p.mouse.click(1100, 200); await sleep(500);
  // substitui o codigo (via area de transferencia do navegador de teste; o token nunca vai para arquivo/imagem)
  await p.evaluate((s) => navigator.clipboard.writeText(s), sketch);
  await p.mouse.click(400, 300);
  await p.keyboard.press('Control+A');
  await p.keyboard.press('Control+V');
  await sleep(1000);
  await shot('ui_01_circuito');
  // Run: compila no backend do Velxio e inicia o ESP32 emulado
  await p.locator('[title="Run"], [aria-label="Run"], [title^="Run"]').first().click().catch(async () => { await p.mouse.click(675, 22); });
  await sleep(500);
  await p.getByRole('button', { name: 'Serial' }).click().catch(() => {});
  let tries = 0; let txt = '';
  while (tries++ < 60) { await sleep(2000); txt = await p.evaluate(() => document.body.innerText); if (txt.includes('WiFi conectado')) break; }
  console.log('wifi no serial:', txt.includes('WiFi conectado'), '| v0.4:', txt.includes('MesaFacil v0.4'));
  await sleep(3000);
  await shot('ui_02_serial_wifi');
  // pagamento demo -> comando
  const ped = await j('POST', '/api/pedidos', { mesa: '01' });
  const oid = ped.pedido;
  console.log('pedido', oid.slice(0, 8), (await j('POST', '/api/demo/pagar', { pedido: oid, resultado: 'aprovado' })).status);
  for (let i = 0; i < 20; i++) { await sleep(1000); txt = await p.evaluate(() => document.body.innerText); if (txt.includes('Pressione o botao')) break; }
  console.log('credito no serial:', txt.includes('Pressione o botao'));
  await shot('ui_03_pagamento_recebido');
  // clique no botao virtual (segura 700 ms)
  const box = await p.locator('wokwi-pushbutton').first().boundingBox();
  await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await p.mouse.down(); await sleep(700);
  await shot('ui_04_botao_pressionado');
  await p.mouse.up();
  for (let i = 0; i < 20; i++) { await sleep(1000); txt = await p.evaluate(() => document.body.innerText); if (txt.includes('Mesa liberada confirmada')) break; }
  console.log('ack no serial:', txt.includes('Mesa liberada confirmada'));
  await sleep(1000);
  await shot('ui_05_ack_liberado');
  const o = await j('GET', '/api/pedidos/' + oid);
  console.log('pedido final:', o.status, o.comando);
  fs.writeFileSync(`${outDir}/ui_serial_dom.txt`, txt.replace(/[\w-]{43}/g, '<TOKEN>'));
  await b.close();
})();
