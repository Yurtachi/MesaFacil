'use strict';
/* Página pública: lista de mesas (somente disponibilidade). Operação fica em /admin. */
function tile(t) {
  const state = t.ocupada ? ['Em uso', 'warn'] : !t.online ? ['Sem conexão', 'idle'] : ['Livre', 'ok'];
  return h('a', { class: 'table-tile', href: `/mesa/${t.id}`, 'aria-label': `${t.nome}, ${state[0]}` },
    h('span', { class: 'muted small' }, 'Mesa'), h('span', { class: 'n' }, t.id), h('span', { class: `badge ${state[1]}` }, state[0]));
}

async function load() {
  const [cfg, list] = await Promise.all([api('/api/config'), api('/api/mesas')]);
  const free = list.mesas.filter(t => !t.ocupada).length;
  mount(h('main', { id: 'main', class: 'shell stack-lg' },
    h('header', { class: 'topbar' }, brand(cfg.estabelecimento), h('a', { class: 'small', href: '/admin' }, 'Área do atendente')),
    cfg.demo && demoBanner(),
    h('section', { class: 'stack' },
      h('h1', null, 'Escolha sua mesa'),
      h('p', { class: 'muted' }, 'Cada mesa tem um QR code fixo. Escaneie o da sua mesa para pagar, ou toque no número abaixo.')),
    list.mesas.length
      ? h('section', { 'aria-label': 'Mesas' }, h('p', { class: 'muted small mt-16', role: 'status' }, `${plural(free, 'mesa livre', 'mesas livres')} de ${list.mesas.length}`), h('div', { class: 'table-grid mt-16' }, list.mesas.map(tile)))
      : h('p', { class: 'empty' }, 'Nenhuma mesa cadastrada ainda.')));
}

load().catch(e => mount(h('main', { id: 'main', class: 'shell narrow' }, h('div', { class: 'notice bad', role: 'alert' }, h('strong', null, 'Não foi possível carregar'), e.message))));
poll(async () => { try { await load(); } catch { /* mantém tela anterior */ } }, { base: 5000, slow: 15000 });
