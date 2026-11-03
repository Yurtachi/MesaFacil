'use strict';
(() => {
/* Palco animado (SVG + Web Animations API). Decorativo: a verdade do estado vem do servidor.
   Regras: a bola só vai para a caçapa quando etapa === 'concluido' (acionamento concluído, confirmado pelo backend);
   pagamento aprovado só leva a bola até o ponto do botão. Sem animação em carga de página, aba oculta ou movimento reduzido. */
const { S, ballAt, cue } = Art;
const A = { x: 70, y: 75 }, SP = { x: 190, y: 75 }, P = { x: 349, y: 11 };
const R = 11;
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const POSE = { aguardando_pagamento: 'A', processando: 'A', recusado: 'A', cancelado: 'A', expirado: 'A', aguardando_botao: 'S', liberando: 'S', analise: 'S', concluido: 'P' };
const tr = (x, y) => `translate(${x}px, ${y}px)`;

function laneSVG() {
  const svg = S('svg', { viewBox: '0 0 360 150', role: 'img', 'aria-label': 'Mesa de sinuca, vista de cima', preserveAspectRatio: 'xMidYMid slice' });
  svg.append(
    S('rect', { class: 'felt', width: 360, height: 150 }), S('rect', { width: 360, height: 150, fill: 'url(#feltLight)' }),
    S('rect', { class: 'rail-line', x: 10, y: 10, width: 340, height: 130, rx: 3 }),
    ...[[0, 0, 14], [360, 0, 14], [0, 150, 14], [360, 150, 14], [180, 0, 11], [180, 150, 11]].map(([x, y, r]) => S('circle', { class: 'pocket', cx: x, cy: y, r })),
    S('circle', { class: 'pocket-glow', cx: 360, cy: 0, r: 19 }));
  return svg;
}

function createStage() {
  const el = document.createElement('div');
  el.className = 'stage';
  const svg = laneSVG();
  const spot = S('g', { transform: `translate(${SP.x} ${SP.y})` }, S('circle', { class: 'spot', r: 17 }), S('circle', { class: 'spot-ico', r: 3.2 }));
  const chalk = S('circle', { class: 'chalk-ring', cx: A.x, cy: A.y, r: 17 });
  const foul = S('g', { class: 'foul', transform: `translate(${A.x} ${A.y})` }, S('path', { d: 'M-8,-8 L8,8 M8,-8 L-8,8' }));
  const deco = [[4, 262, 112], [6, 284, 98], [3, 300, 120]].map(([n, x, y]) => ballAt(n, x, y, R));
  const ball = ballAt(0, A.x, A.y, R);
  const stick = cue();
  stick.style.transform = tr(A.x - R - 3, A.y);
  stick.style.opacity = '0';
  svg.append(spot, chalk, foul, ...deco, stick, ball);
  el.append(svg);

  let pose = null, token = 0, running = [];
  const place = (g, x, y) => { g.style.transform = tr(x, y); };
  const cancelAll = () => { running.forEach(a => { try { a.cancel(); } catch { /* já finalizada */ } }); running = []; };
  const anim = (node, frames, opts) => { const a = node.animate(frames, { fill: 'forwards', ...opts }); running.push(a); return a.finished.catch(() => {}); };
  const roll = (g, from, to, ms, easing) => {
    const dist = Math.hypot(to.x - from.x, to.y - from.y);
    const deg = (dist / R) * 57.3 * (to.x >= from.x ? 1 : -1);
    anim(g._spin, [{ transform: 'rotate(0deg)' }, { transform: `rotate(${deg}deg)` }], { duration: ms, easing });
    return anim(g, [{ transform: tr(from.x, from.y) }, { transform: tr(to.x, to.y) }], { duration: ms, easing });
  };

  function setPose(next) {
    cancelAll();
    ball.getAnimations?.().forEach(a => a.cancel());
    ball._spin.style.transform = '';
    stick.style.opacity = '0';
    const t = { A, S: SP, P }[next];
    place(ball, t.x, t.y);
    ball.style.opacity = next === 'P' ? '0' : '1';
    ball.style.transform = next === 'P' ? tr(P.x + 4, P.y - 2) + ' scale(0.5)' : tr(t.x, t.y);
    pose = next;
  }

  async function strike(my) {
    stick.style.transform = tr(A.x - R - 3, A.y);
    await anim(stick, [{ opacity: 0, transform: tr(A.x - R - 3, A.y) }, { opacity: 1, transform: tr(A.x - R - 3, A.y), offset: 0.001 }, { opacity: 1, transform: tr(A.x - R - 38, A.y) }], { duration: 520, easing: 'cubic-bezier(0.3, 0, 0.2, 1)' });
    if (my !== token) return false;
    await anim(stick, [{ opacity: 1, transform: tr(A.x - R - 38, A.y) }, { opacity: 1, transform: tr(A.x - R - 3, A.y) }], { duration: 110, easing: 'cubic-bezier(0.55, 0, 1, 0.8)' });
    if (my !== token) return false;
    anim(stick, [{ opacity: 1, transform: tr(A.x - R - 3, A.y) }, { opacity: 0, transform: tr(A.x - R - 10, A.y) }], { duration: 260, easing: 'ease-out', delay: 80 });
    await roll(ball, A, SP, 950, 'cubic-bezier(0.12, 0.7, 0.25, 1)');
    return my === token;
  }

  async function drop(my, from) {
    await roll(ball, from, { x: P.x, y: P.y }, 620, 'cubic-bezier(0.35, 0.55, 0.45, 1)');
    if (my !== token) return false;
    anim(svg.querySelector('.pocket-glow'), [{ opacity: 0.9, transform: 'scale(0.7)' }, { opacity: 0.55, transform: 'scale(1.25)' }], { duration: 520, easing: 'cubic-bezier(0.23, 1, 0.32, 1)' });
    await anim(ball, [{ opacity: 1, transform: tr(P.x, P.y) + ' scale(1)' }, { opacity: 0, transform: tr(P.x + 5, P.y - 3) + ' scale(0.5)' }], { duration: 260, easing: 'cubic-bezier(0.23, 1, 0.32, 1)' });
    return my === token;
  }

  async function set(etapa, { animate = true } = {}) {
    el.dataset.etapa = etapa || 'aguardando_pagamento';
    const target = POSE[etapa] || 'A';
    if (target === pose) return;
    const prev = pose;
    const my = ++token;
    cancelAll();
    if (prev === null || !animate || reduced() || document.hidden || target === 'A') return setPose(target);
    ball.style.opacity = '1';
    if (prev === 'A' && target === 'S') {
      el.classList.add('playing');
      if (await strike(my)) setPose('S');
    } else if (prev === 'S' && target === 'P') {
      if (await drop(my, SP)) setPose('P');
    } else if (prev === 'A' && target === 'P') {
      if ((await strike(my)) && (await drop(my, SP))) setPose('P');
    } else setPose(target);
    if (my === token) el.classList.remove('playing');
  }
  return { el, set };
}

/* Abertura da home: tacada na bola branca, que abre o triângulo. Executa uma vez por sessão; depois, pose final estática. */
function createBreak() {
  const el = document.createElement('div');
  el.className = 'stage';
  const svg = laneSVG();
  svg.setAttribute('aria-label', 'Tacada abrindo o triângulo de bolas');
  const cueBall = ballAt(0, 78, 75, R);
  const rackFinal = [[3, 232, 40], [9, 300, 62], [1, 318, 104], [5, 262, 118], [8, 286, 82], [11, 214, 96], [2, 330, 38], [14, 246, 70], [6, 196, 52], [13, 340, 124]];
  const rackStart = [[3, 252, 75], [9, 270, 66], [1, 270, 84], [5, 288, 57], [8, 288, 75], [11, 288, 93], [2, 306, 48], [14, 306, 66], [6, 306, 84], [13, 306, 102]];
  const balls = rackStart.map(([n, x, y]) => ballAt(n, x, y, R));
  const stick = cue();
  svg.append(...balls, cueBall, stick);
  el.append(svg);
  const finalCue = { x: 205, y: 75 };
  const finals = () => {
    balls.forEach((b, i) => { b.style.transform = tr(rackFinal[i][1], rackFinal[i][2]); });
    cueBall.style.transform = tr(finalCue.x, finalCue.y);
    stick.style.opacity = '0';
  };
  stick.style.transform = tr(78 - R - 3, 75);
  const seen = sessionStorage.getItem('mf_break');
  const go = async () => {
    if (seen || reduced() || document.hidden) return finals();
    sessionStorage.setItem('mf_break', '1');
    const done = [];
    const run = (n, frames, opts) => { const a = n.animate(frames, { fill: 'forwards', ...opts }); done.push(a.finished.catch(() => {})); return a; };
    await run(stick, [{ transform: tr(78 - R - 3, 75) }, { transform: tr(78 - R - 40, 75) }], { duration: 560, easing: 'cubic-bezier(0.3, 0, 0.2, 1)' }).finished.catch(() => {});
    await run(stick, [{ transform: tr(78 - R - 40, 75) }, { transform: tr(78 - R - 3, 75) }], { duration: 100, easing: 'cubic-bezier(0.55, 0, 1, 0.8)' }).finished.catch(() => {});
    run(stick, [{ opacity: 1 }, { opacity: 0 }], { duration: 300, delay: 100 });
    run(cueBall._spin, [{ transform: 'rotate(0deg)' }, { transform: 'rotate(560deg)' }], { duration: 500, easing: 'cubic-bezier(0.1, 0.7, 0.3, 1)' });
    await run(cueBall, [{ transform: tr(78, 75) }, { transform: tr(250, 75) }], { duration: 500, easing: 'cubic-bezier(0.2, 0.6, 0.6, 1)' }).finished.catch(() => {});
    run(cueBall, [{ transform: tr(250, 75) }, { transform: tr(finalCue.x, finalCue.y) }], { duration: 700, easing: 'cubic-bezier(0.1, 0.7, 0.25, 1)' });
    balls.forEach((b, i) => {
      run(b._spin, [{ transform: 'rotate(0deg)' }, { transform: `rotate(${(i % 2 ? -1 : 1) * 380}deg)` }], { duration: 1000, easing: 'cubic-bezier(0.1, 0.7, 0.25, 1)' });
      run(b, [{ transform: tr(rackStart[i][1], rackStart[i][2]) }, { transform: tr(rackFinal[i][1], rackFinal[i][2]) }], { duration: 900 + (i % 3) * 120, easing: 'cubic-bezier(0.1, 0.75, 0.25, 1)' });
    });
    await Promise.all(done);
    finals();
    document.getAnimations?.().forEach(a => { if (a.effect?.target && el.contains(a.effect.target)) a.cancel(); });
  };
  setTimeout(go, 250);
  return el;
}

window.Stage = { createStage, createBreak };
})();
