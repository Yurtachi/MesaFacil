'use strict';
/* Página pública: abertura (tacada) + mesas vistas de cima com disponibilidade. Operação fica em /admin. */
let first = true, lastSig = '';

function tile(t) {
  const [label, tone, art] = t.ocupada ? ['Em uso', 'warn', 'busy'] : !t.online ? ['Sem conexão', 'idle', 'off'] : ['Livre', 'ok', 'free'];
  return h('li', null, h('a', { class: 'table-tile', href: `/mesa/${t.id}`, 'aria-label': `${t.nome}, ${label}` },
    Art.tableSVG(t.id, art, `Mesa ${t.id} vista de cima`),
    h('span', { class: 'meta' }, h('b', null, t.nome), h('span', { class: `badge ${tone}` }, label))));
}

async function load() {
  const [cfg, list] = await Promise.all([api('/api/config'), api('/api/mesas')]);
  const sig = JSON.stringify([cfg, list]);
  if (sig === lastSig) return;
  lastSig = sig;
  const free = list.mesas.filter(t => !t.ocupada).length;
  const rv = first ? ' reveal' : '';
  const hero = first ? h('div', { class: 'hero-art' }, Stage.createBreak()) : document.querySelector('.hero-art');
  mount(h('main', { id: 'main', class: 'shell stack-lg' },
    h('header', { class: 'topbar' }, brand(cfg.estabelecimento), h('a', { class: 'small', href: '/admin' }, 'Área do atendente')),
    cfg.demo && h('p', { class: 'demo-pill', role: 'note' }, 'Demonstração: nenhum pagamento real, nenhuma mesa física'),
    h('section', { class: 'hero' }, hero,
      h('div', { class: 'hero-copy' }, h('p', { class: 'eyebrow' + rv }, cfg.estabelecimento), h('h1', { class: rv.trim() ? 'reveal d1' : '' }, 'Escolha sua mesa'),
        h('p', { class: rv.trim() ? 'reveal d2' : '' }, 'Cada mesa tem um QR code fixo. Escaneie o da sua mesa para pagar, ou toque na mesa abaixo.'))),
    list.mesas.length
      ? h('section', { 'aria-label': 'Mesas', class: 'stack' },
        h('div', { class: 'row between' }, h('p', { class: 'muted small', role: 'status' }, `${plural(free, 'mesa livre', 'mesas livres')} de ${list.mesas.length}`),
          h('p', { class: 'legend' }, h('span', { class: 'badge ok' }, 'Livre'), h('span', { class: 'badge warn' }, 'Em uso'), h('span', { class: 'badge idle' }, 'Sem conexão'))),
        h('ul', { class: 'table-grid' }, list.mesas.map(tile)))
      : h('p', { class: 'empty' }, 'Nenhuma mesa cadastrada ainda.')));
  first = false;
}

load().catch(e => mount(h('main', { id: 'main', class: 'shell narrow' }, h('div', { class: 'notice bad', role: 'alert' }, h('strong', null, 'Não foi possível carregar'), e.message))));
poll(async () => { try { await load(); } catch { /* mantém tela anterior */ } }, { base: 6000, slow: 15000 });
