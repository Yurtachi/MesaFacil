'use strict';
/* Impressão dos QR codes permanentes. Exige sessão de atendente. */
(async () => {
  try { await api('/api/admin/sessao'); } catch { return location.replace('/admin'); }
  const [cfg, list] = await Promise.all([api('/api/config'), api('/api/mesas')]);
  mount(h('main', { id: 'main', class: 'shell stack-lg' },
    h('header', { class: 'topbar no-print' }, brand('QR codes', '/admin'), h('a', { class: 'small', href: '/admin' }, 'Voltar ao painel')),
    h('section', { class: 'stack no-print' },
      h('h1', null, 'QR codes das mesas'),
      h('p', { class: 'muted' }, 'Cada QR code leva à página da mesa e não contém dados sensíveis. O endereço gravado é o configurado em PUBLIC_BASE_URL no servidor.'),
      h('p', { class: 'notice warn' }, 'Se o endereço for local (127.0.0.1 ou IP da rede), o QR code só funciona em celulares na mesma rede Wi-Fi. Veja docs/ARQUITETURA.md.'),
      h('button', { class: 'btn primary', onclick: () => print() }, 'Imprimir')),
    list.mesas.length
      ? h('section', { class: 'plates', 'aria-label': 'Placas' }, list.mesas.map(t => h('figure', { class: 'plate' },
        h('img', { src: `/qr/${t.id}.png`, alt: `QR code da mesa ${t.id}`, width: 192, height: 192 }),
        h('b', null, t.id), h('small', null, cfg.estabelecimento))))
      : h('p', { class: 'empty' }, 'Nenhuma mesa cadastrada.')));
})();
