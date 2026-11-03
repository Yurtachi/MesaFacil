'use strict';
(() => {
/* Arte própria do MesaFácil (SVG gerado em JS, sem imagens): bolas numeradas, mesas vistas de cima, taco, logotipo.
   Cores das bolas seguem a convenção de bilhar (1 amarela, 2 azul, 3 vermelha, 4 roxa, 5 laranja, 6 verde, 7 grená, 8 preta; 9–15 listradas). */
const NS = 'http://www.w3.org/2000/svg';
const BALL_COLORS = { 1: '#f2c230', 2: '#1f5fb4', 3: '#d2342b', 4: '#5b2a86', 5: '#ee7a1c', 6: '#1f8a4c', 7: '#7a1f1f', 8: '#15171a' };
const CREAM = '#f4eedd';

function S(tag, attrs, ...kids) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v != null && v !== false) el.setAttribute(k, v);
  for (const kid of kids.flat()) if (kid) el.append(kid);
  return el;
}

/* Gradientes compartilhados: criados uma vez por página. */
function mountDefs() {
  if (document.getElementById('art-defs')) return;
  const defs = S('defs', null,
    S('radialGradient', { id: 'ballShade', cx: '.38', cy: '.34', r: '.75' }, S('stop', { offset: '0', 'stop-color': '#fff', 'stop-opacity': '0' }), S('stop', { offset: '.6', 'stop-color': '#000', 'stop-opacity': '.05' }), S('stop', { offset: '1', 'stop-color': '#000', 'stop-opacity': '.5' })),
    S('radialGradient', { id: 'ballSpec', cx: '.5', cy: '.5', r: '.5' }, S('stop', { offset: '0', 'stop-color': '#fff', 'stop-opacity': '.95' }), S('stop', { offset: '1', 'stop-color': '#fff', 'stop-opacity': '0' })),
    S('radialGradient', { id: 'lampGlow', cx: '.5', cy: '.5', r: '.6' }, S('stop', { offset: '0', 'stop-color': '#fff6d6', 'stop-opacity': '.34' }), S('stop', { offset: '1', 'stop-color': '#fff6d6', 'stop-opacity': '0' })),
    S('radialGradient', { id: 'feltLight', cx: '.5', cy: '.45', r: '.75' }, S('stop', { offset: '0', 'stop-color': '#2aa774', 'stop-opacity': '.45' }), S('stop', { offset: '1', 'stop-color': '#04281c', 'stop-opacity': '.35' })));
  const holder = S('svg', { id: 'art-defs', width: 0, height: 0, 'aria-hidden': 'true', focusable: 'false' }, defs);
  holder.setAttribute('class', 'sr-only');
  document.body.prepend(holder);
}

/* Bola em coordenadas locais de raio 18. `body` gira ao rolar; `shine` (brilho/sombra) fica parado. */
function ballParts(n) {
  const stripe = n >= 9;
  const color = n === 0 ? CREAM : BALL_COLORS[stripe ? n - 8 : n];
  const body = S('g', { class: 'b-body' },
    S('circle', { r: 18, fill: stripe || n === 0 ? CREAM : color }),
    stripe && S('path', { d: 'M-15.59,-9 L15.59,-9 A18,18 0 0 1 15.59,9 L-15.59,9 A18,18 0 0 1 -15.59,-9 Z', fill: color }),
    n > 0 && S('circle', { r: 7.6, fill: CREAM }),
    n > 0 && S('text', { 'text-anchor': 'middle', y: 3.6, 'font-size': 10.5, 'font-weight': 800, 'font-family': 'Manrope,sans-serif', fill: '#111' }, String(n)),
    n === 0 && S('circle', { r: 1.6, cx: 0, cy: -9, fill: '#d2342b' }));
  const shine = S('g', { class: 'b-shine' },
    S('circle', { r: 18, fill: 'url(#ballShade)' }),
    S('ellipse', { cx: -6, cy: -7, rx: 5.5, ry: 3.4, fill: 'url(#ballSpec)', transform: 'rotate(-30 -6 -7)' }));
  return { body, shine };
}

function ball(n, size = 32) {
  const { body, shine } = ballParts(n);
  return S('svg', { class: 'ball', viewBox: '-19 -19 38 38', width: size, height: size, role: 'img', 'aria-label': n ? `Bola ${n}` : 'Bola branca' }, body, shine);
}

/* Bola posicionável dentro de outro SVG (raio r). */
function ballAt(n, x, y, r = 11) {
  const { body, shine } = ballParts(n);
  const k = r / 18;
  const spin = S('g', { class: 'spin' }, S('g', { transform: `scale(${k})` }, body));
  const g = S('g', { class: 'ballg', transform: `translate(${x} ${y})` }, S('ellipse', { cx: 1.5, cy: 3, rx: r * 0.95, ry: r * 0.6, fill: '#000', opacity: 0.28 }), spin, S('g', { transform: `scale(${k})` }, shine));
  g._spin = spin;
  return g;
}

/* Taco horizontal: ponta em (0,0), corpo para a esquerda. */
function cue() {
  return S('g', { class: 'cue' },
    S('polygon', { points: '-230,-4.2 -120,-2.8 -120,2.8 -230,4.2', fill: '#3b2113' }),
    S('polygon', { points: '-230,-4.2 -200,-3.9 -200,3.9 -230,4.2', fill: '#1b1b1d' }),
    S('rect', { x: -123, y: -3.1, width: 4, height: 6.2, fill: '#dcb86f' }),
    S('polygon', { points: '-120,-2.8 -16,-1.8 -16,1.8 -120,2.8', fill: '#e9d3a0' }),
    S('rect', { x: -16, y: -1.9, width: 11, height: 3.8, fill: CREAM }),
    S('rect', { x: -5, y: -1.9, width: 5, height: 3.8, rx: 1, fill: '#5aa8e0' }));
}

function diamonds(w, h) {
  const d = (x, y) => S('rect', { class: 't-diamond', x: x - 2.2, y: y - 2.2, width: 4.4, height: 4.4, transform: `rotate(45 ${x} ${y})` });
  const out = [];
  for (const x of [58, 104, 196, 242]) { out.push(d(x, 8), d(x, h - 8)); }
  for (const y of [52, 98]) { out.push(d(8, y), d(w - 8, y)); }
  return out;
}

/* Mesa vista de cima para cartões: estado 'free' (bolas no triângulo, luz acesa), 'busy', 'off'. */
function tableSVG(id, state, label) {
  const W = 300, H = 150;
  const svg = S('svg', { class: 'tbl ' + state, viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': label });
  svg.append(
    S('rect', { class: 't-wood', width: W, height: H, rx: 16 }),
    S('rect', { class: 't-wood-hi', x: 4, y: 4, width: W - 8, height: H - 8, rx: 13, fill: 'none', stroke: '#8d5a33', 'stroke-width': 1.2 }),
    S('rect', { class: 't-felt', x: 18, y: 18, width: W - 36, height: H - 36, rx: 5 }),
    S('rect', { x: 18, y: 18, width: W - 36, height: H - 36, rx: 5, fill: 'url(#feltLight)' }),
    ...diamonds(W, H));
  for (const [x, y, r] of [[18, 18, 10], [W - 18, 18, 10], [18, H - 18, 10], [W - 18, H - 18, 10], [W / 2, 15, 8.5], [W / 2, H - 15, 8.5]]) svg.append(S('circle', { class: 't-pocket', cx: x, cy: y, r }));
  svg.append(S('text', { class: 't-num', x: W / 2, y: 98 }, id));
  if (state === 'free') {
    svg.append(S('ellipse', { class: 't-lamp', cx: W / 2, cy: H / 2, rx: 130, ry: 70 }), ballAt(0, 64, 75, 9));
    [[206, 75, 3], [220, 66, 1], [220, 84, 5], [234, 57, 2], [234, 75, 8], [234, 93, 4]].forEach(([x, y, n]) => svg.append(ballAt(n, x, y, 9)));
  } else if (state === 'busy') {
    [[0, 112, 112], [3, 86, 62], [6, 180, 98], [1, 214, 52], [9, 244, 110], [8, 150, 56]].forEach(([n, x, y]) => svg.append(ballAt(n, x, y, 9)));
  } else {
    svg.append(S('rect', { class: 't-cover', x: 0, y: 0, width: W, height: H, rx: 16 }));
  }
  return svg;
}

/* Marca: bola 8 com anel de latão. */
function logo(size = 40) {
  const svg = S('svg', { class: 'brand-mark', viewBox: '-22 -22 44 44', width: size, height: size, 'aria-hidden': 'true' },
    S('circle', { r: 21, fill: '#dcb86f' }), S('circle', { r: 18.5, fill: '#15171a' }),
    S('circle', { r: 8, fill: CREAM }), S('text', { 'text-anchor': 'middle', y: 4.2, 'font-size': 12, 'font-weight': 800, 'font-family': 'Manrope,sans-serif', fill: '#111' }, '8'),
    S('ellipse', { cx: -7, cy: -9, rx: 6, ry: 3.4, fill: '#fff', opacity: 0.35, transform: 'rotate(-30 -7 -9)' }));
  return svg;
}

/* Botão físico da mesa (instrução "aperte o botão"). waiting = sem pulso de anéis. */
function buttonArt() {
  return S('svg', { viewBox: '0 0 92 92', 'aria-hidden': 'true', focusable: 'false' },
    S('rect', { class: 'base', x: 8, y: 8, width: 76, height: 76, rx: 14 }),
    S('circle', { class: 'ring', cx: 46, cy: 46, r: 30 }), S('circle', { class: 'ring r2', cx: 46, cy: 46, r: 30 }),
    S('circle', { class: 'cap-rim', cx: 46, cy: 49, r: 24 }), S('circle', { class: 'cap-btn', cx: 46, cy: 45, r: 24 }),
    S('ellipse', { class: 'cap-hi', cx: 38, cy: 35, rx: 9, ry: 5, transform: 'rotate(-30 38 35)' }));
}

mountDefs();
window.Art = { S, mountDefs, ball, ballAt, ballParts, cue, tableSVG, logo, buttonArt, BALL_COLORS };
})();
