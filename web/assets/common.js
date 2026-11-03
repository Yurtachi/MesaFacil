'use strict';
/* Utilitários compartilhados. Regra: dados nunca entram via innerHTML, só via textContent/atributos. */
const app = document.getElementById('app');

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}

const money = c => (c / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const when = s => (s ? new Date(s).toLocaleString('pt-BR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—');
const short = id => String(id || '').slice(0, 8).toUpperCase();
const plural = (n, one, many) => `${n} ${new Intl.PluralRules('pt-BR').select(n) === 'one' ? one : many}`;
function ago(s) {
  if (!s) return 'nunca';
  const sec = Math.max(0, Math.round((Date.now() - new Date(s)) / 1000));
  if (sec < 60) return `há ${sec} s`;
  if (sec < 3600) return `há ${Math.round(sec / 60)} min`;
  if (sec < 86400) return `há ${Math.round(sec / 3600)} h`;
  return when(s);
}

const ICONS = {
  check: 'M5 13l4 4L19 7',
  x: 'M6 6l12 12M18 6L6 18',
  clock: 'M12 7v5l3 2M12 3a9 9 0 100 18 9 9 0 000-18z',
  alert: 'M12 8v5M12 17h.01M10.3 4.2L2.8 17.5A2 2 0 004.5 20.5h15a2 2 0 001.7-3L13.7 4.2a2 2 0 00-3.4 0z',
  spinner: 'M12 3a9 9 0 019 9',
  button: 'M12 9a3 3 0 100 6 3 3 0 000-6zM12 3a9 9 0 100 18 9 9 0 000-18z',
  wifi: 'M5 12.5a10 10 0 0114 0M8.5 16a5 5 0 017 0M12 19.5h.01',
  qr: 'M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h3v3h-3zM20 14v6h-3',
};
function icon(name) {
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  for (const [k, v] of Object.entries({ viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': '2', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' })) svg.setAttribute(k, v);
  const path = document.createElementNS(ns, 'path');
  path.setAttribute('d', ICONS[name]);
  svg.append(path);
  return svg;
}

async function api(path, body, opts = {}) {
  const init = { method: body === undefined ? 'GET' : 'POST', headers: {}, cache: 'no-store' };
  if (body !== undefined) { init.headers['Content-Type'] = 'application/json'; init.body = JSON.stringify(body); }
  if (opts.csrf) init.headers['X-CSRF-Token'] = opts.csrf;
  let res;
  try { res = await fetch(path, init); } catch { throw Object.assign(new Error('Sem conexão com o servidor. Verifique o Wi-Fi e tente de novo.'), { status: 0 }); }
  let data = null;
  try { data = await res.json(); } catch { /* corpo vazio */ }
  if (!res.ok) throw Object.assign(new Error((data && data.erro) || `Erro ${res.status}`), { status: res.status });
  return data;
}

function brand(subtitle, href = '/') {
  return h('a', { class: 'brand', href },
    h('img', { class: 'brand-mark', src: '/assets/favicon.svg', alt: '', width: 36, height: 36 }),
    h('span', null, h('b', null, 'MesaFácil'), h('small', null, subtitle)));
}

function demoBanner() {
  return h('p', { class: 'demo-pill', role: 'note' }, 'Demonstração: nenhum pagamento real, nenhuma mesa física');
}

let toastTimer;
function toast(message, bad = false) {
  document.querySelector('.toast')?.remove();
  const el = h('div', { class: 'toast' + (bad ? ' bad' : ''), role: bad ? 'alert' : 'status' }, message);
  document.body.append(el);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.remove(), 4000);
}

/* Polling que pausa com a aba oculta, recua o ritmo quando nada muda e para quando fn retorna false. */
function poll(fn, { base = 2000, slow = 6000, slowAfter = 120000 } = {}) {
  let stopped = false, timer, since = Date.now();
  const tick = async () => {
    if (stopped) return;
    if (document.visibilityState === 'visible') {
      try { if ((await fn()) === false) return; } catch { /* tenta de novo */ }
    }
    timer = setTimeout(tick, Date.now() - since > slowAfter ? slow : base);
  };
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && !stopped) { clearTimeout(timer); since = Date.now(); tick(); } });
  timer = setTimeout(tick, base);
  return () => { stopped = true; clearTimeout(timer); };
}

function mount(...nodes) {
  app.replaceChildren(...nodes);
  app.querySelector('[aria-busy]')?.removeAttribute('aria-busy');
}
