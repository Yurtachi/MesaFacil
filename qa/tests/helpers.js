const fs = require('fs');
const path = require('path');

const TMP = path.join(__dirname, '..', '.tmp');
const SHOTS = path.join(__dirname, '..', '..', 'docs', 'qa', 'screenshots', 'v2');

exports.states = () => JSON.parse(fs.readFileSync(path.join(TMP, 'states.json'), 'utf8'));
exports.adminState = path.join(TMP, 'admin.json');

exports.shot = async (page, project, name) => {
  const dir = path.join(SHOTS, project);
  fs.mkdirSync(dir, { recursive: true });
  await page.screenshot({ path: path.join(dir, `${name}.png`), fullPage: true });
};

// Rolagem horizontal, elementos fora da viewport e alvos de toque pequenos.
exports.layoutProblems = page => page.evaluate(() => {
  const vw = document.documentElement.clientWidth;
  const out = [];
  if (document.documentElement.scrollWidth > vw + 1) out.push(`rolagem horizontal: ${document.documentElement.scrollWidth} > ${vw}`);
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (el.closest('.tablewrap, .nav, dialog, .skip, .sr-only, svg')) continue;
    if (r.right > vw + 1 || r.left < -1) out.push(`fora da tela: <${el.tagName.toLowerCase()} class="${el.className}"> ${Math.round(r.left)}..${Math.round(r.right)} (vw ${vw})`);
    if (['A', 'BUTTON'].includes(el.tagName) && r.height < 44 && getComputedStyle(el).display !== 'inline') out.push(`alvo de toque < 44px: "${el.textContent.trim().slice(0, 30)}" (${Math.round(r.height)}px)`);
  }
  return out.slice(0, 10);
});
