'use strict';
/* Placas impressas: número da mesa, QR com margem de segurança (sem efeitos sobre os módulos) e instruções. Exige sessão de atendente. */
(async () => {
  const st = await api('/api/admin/estado').catch(() => ({}));
  if (!st.autenticado) return location.replace('/admin');
  const [cfg, list] = await Promise.all([api('/api/config'), api('/api/mesas')]);
  const step = (n, t) => h('li', null, h('i', null, n), t);
  mount(h('main', { id: 'main', class: 'shell stack-lg' },
    h('header', { class: 'topbar no-print' }, brand('QR codes', '/admin'), h('a', { class: 'small', href: '/admin' }, 'Voltar ao painel')),
    h('section', { class: 'stack no-print' },
      h('h1', null, 'QR codes das mesas'),
      h('p', { class: 'muted' }, 'Cada QR code leva à página da mesa e não contém dados sensíveis. O endereço gravado é o configurado em PUBLIC_BASE_URL no servidor.'),
      h('p', { class: 'notice warn' }, 'Se o endereço for local (127.0.0.1 ou IP da rede), o QR code só funciona em celulares na mesma rede Wi-Fi. Veja docs/ARQUITETURA.md.'),
      h('button', { class: 'btn primary', onclick: () => print() }, 'Imprimir')),
    list.mesas.length
      ? h('ul', { class: 'plates', 'aria-label': 'Placas' }, list.mesas.map(t => h('li', { class: 'plate' },
        h('div', { class: 'band' }, h('span', null, Art.ball(((Number(t.id) - 1) % 15) + 1, 44)), h('b', null, `Mesa ${t.id}`), h('small', null, cfg.estabelecimento)),
        h('div', { class: 'qrbox' }, h('img', { src: `/qr/${t.id}.png`, alt: `QR code da mesa ${t.id}`, width: 240, height: 240 })),
        h('ol', null, step(1, 'Escaneie o QR code'), step(2, 'Pague pelo celular'), step(3, 'Aperte o botão da mesa')),
        h('p', { class: 'fine' }, 'Sem cadastro. Em caso de problema, chame o atendente.'))))
      : h('p', { class: 'empty' }, 'Nenhuma mesa cadastrada.')));
})();
