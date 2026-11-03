'use strict';
/* Fluxo do cliente: /mesa/NN. O estado vem do servidor (campo `etapa`); o navegador nunca aprova pagamento real.
   O palco (Stage) é decorativo: só reflete a etapa recebida, nunca a antecipa. */
const mesaId = location.pathname.split('/')[2];
const storeKey = `mf_pedido_${mesaId}`;
let table = null, order = null, busy = false, offline = false, error = '', lastSig = '', stopPoll = null, ui = null, lastEtapa = null;

const STEPS = ['Pagamento', 'Crédito na mesa', 'Mesa liberada'];
const TERMINAL = ['concluido', 'recusado', 'cancelado', 'expirado'];
const CAPTION = {
  none: 'Pagamento da mesa', aguardando_pagamento: 'Aguardando pagamento', processando: 'Processando', aguardando_botao: 'Aperte o botão',
  liberando: 'Liberando', concluido: 'Mesa liberada', analise: 'Em conferência', recusado: 'Pagamento recusado', cancelado: 'Compra cancelada', expirado: 'Cobrança expirada',
};

function stepStates(etapa) {
  const now = { aguardando_pagamento: 0, processando: 0, aguardando_botao: 1, liberando: 1, analise: 1, concluido: 3 }[etapa] ?? -1;
  return STEPS.map((_, i) => (i < now ? 'done' : i === now ? 'now' : 'todo'));
}

function setOrder(id) {
  order = id;
  const url = new URL(location.href);
  if (id) { url.searchParams.set('pedido', id); sessionStorage.setItem(storeKey, id); }
  else { url.searchParams.delete('pedido'); sessionStorage.removeItem(storeKey); }
  history.replaceState({}, '', url);
}

async function run(fn) {
  if (busy) return;
  busy = true; error = ''; draw();
  try { await fn(); } catch (e) { error = e.message; if (e.status === 404 && order) setOrder(null); }
  busy = false;
  startPoll();
  await refresh(true);
}
function startPoll() { stopPoll?.(); stopPoll = poll(() => refresh(false), { base: 2000 }); }

const startOrder = () => run(async () => { const o = await api('/api/pedidos', { mesa: mesaId }); setOrder(o.pedido); });
const cancelOrder = () => run(async () => { await api('/api/pedidos/cancelar', { pedido: order.pedido }); setOrder(null); });
const demoPay = r => run(() => api('/api/demo/pagar', { pedido: order.pedido, resultado: r }));
const restart = () => { setOrder(null); order = null; error = ''; startPoll(); refresh(true); };

function hero(iconName, tone, title, text, spin = false) {
  return h('div', { class: 'status-hero enter' },
    h('div', { class: `status-icon ${tone}${spin ? ' spin' : ''}` }, icon(iconName)),
    h('h2', null, title),
    text && h('p', { class: 'muted' }, text));
}

function demoButtons() {
  if (!order.demo_pagamento_permitido) {
    return h('div', { class: 'notice info' }, h('strong', null, 'Pagamento de demonstração'),
      'A aprovação fictícia só pode ser feita no computador do servidor. Inicie com DEMO_REMOTE_PAY=1 para testar pelo celular em rede confiável.');
  }
  return h('div', { class: 'stack' },
    h('div', { class: 'notice warn' }, h('strong', null, 'Pagamento de demonstração'), 'Os botões abaixo simulam a resposta do banco. Nenhum dinheiro é movimentado.'),
    h('button', { id: 'b-ok', class: 'btn primary block', onclick: () => demoPay('aprovado'), disabled: busy }, 'Simular pagamento aprovado'),
    h('div', { class: 'row' },
      h('button', { id: 'b-no', class: 'btn grow', onclick: () => demoPay('recusado'), disabled: busy }, 'Simular recusa'),
      h('button', { id: 'b-wait', class: 'btn grow', onclick: () => demoPay('pendente'), disabled: busy }, 'Simular processamento')));
}

function pressBlock(received) {
  return h('div', { class: 'press' + (received ? '' : ' waiting') }, Art.buttonArt(),
    h('div', { class: 'stack' }, h('h3', null, received ? `Aperte o botão da mesa ${order.mesa}` : 'Enviando o crédito'),
      h('p', { class: 'muted small' }, received ? 'O botão fica na própria mesa. A liberação só conta depois que ele for apertado.' : 'Ainda não foi liberado. Esta tela avisa quando a mesa receber o crédito.')));
}

function panel() {
  const o = order, e = o?.etapa;
  const hint = table.demo ? ' (simulado)' : '';
  if (!o) {
    return {
      status: hero('qr', '', 'Pague para liberar a mesa', 'Depois do pagamento, aperte o botão físico da mesa para receber as fichas.'),
      body: h('div', { class: 'stack' },
        !table.online && h('div', { class: 'notice warn' }, h('strong', null, 'Controlador sem resposta'), 'A liberação só acontece quando a mesa voltar a se conectar. Se tiver pressa, chame o atendente.'),
        table.ocupada && h('div', { class: 'notice info' }, h('strong', null, 'Compra em andamento'), 'Alguém já iniciou o pagamento desta mesa. Aguarde ou chame o atendente.')),
      action: h('button', { id: 'b-pay', class: 'btn primary block', onclick: startOrder, disabled: busy || table.ocupada }, busy ? 'Aguarde…' : `Pagar ${money(table.preco_centavos)} com Pix${hint}`),
    };
  }
  if (e === 'aguardando_pagamento') {
    return {
      status: hero('clock', '', 'Aguardando o pagamento', o.expira_em ? `Esta cobrança vale até ${new Date(o.expira_em).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })}.` : ''),
      body: o.demo ? demoButtons() : h('div', { class: 'notice warn' }, h('strong', null, 'Pix indisponível'), 'O provedor de pagamentos ainda não está configurado neste servidor. Chame o atendente.'),
      action: h('button', { id: 'b-cancel', class: 'btn ghost block', onclick: cancelOrder, disabled: busy }, 'Cancelar compra'),
    };
  }
  if (e === 'processando') return { status: hero('spinner', '', 'Processando o pagamento', 'Aguarde. Não pague de novo.', true), body: o.demo && demoButtons() };
  if (e === 'aguardando_botao') {
    const received = o.comando === 'ENTREGUE';
    return {
      status: hero('check', 'ok', 'Pagamento aprovado', received ? 'O crédito já está na mesa.' : 'O crédito está a caminho da mesa.'),
      body: h('div', { class: 'stack' }, h('div', { class: 'card' }, pressBlock(received)),
        !o.controlador_online && h('div', { class: 'notice bad', role: 'alert' }, h('strong', null, 'Mesa sem conexão'), `Seu pagamento está registrado. Chame o atendente e informe o código ${short(o.pedido)}.`)),
    };
  }
  if (e === 'liberando') return { status: hero('spinner', '', 'Liberando fichas', 'O acionamento está em andamento.', true) };
  if (e === 'concluido') {
    return {
      status: hero('check', 'ok', 'Mesa liberada', `A mesa ${o.mesa} confirmou o acionamento. Bom jogo.`),
      body: h('dl', { class: 'kv card' }, h('dt', null, 'Código'), h('dd', { class: 'mono' }, short(o.pedido)),
        h('dt', null, 'Valor'), h('dd', { class: 'num' }, o.origem === 'MANUAL' ? 'Cortesia' : money(o.valor_centavos)),
        h('dt', null, 'Liberada às'), h('dd', null, when(o.liberado_em)), o.demo && h('dt', null, 'Modo'), o.demo && h('dd', null, 'Demonstração')),
      action: h('button', { id: 'b-new', class: 'btn block', onclick: restart }, 'Nova compra'),
    };
  }
  if (e === 'analise') {
    return {
      status: hero('alert', 'warn', 'Estamos conferindo sua mesa', 'Seu pagamento foi registrado, mas a liberação precisa de conferência.'),
      body: h('div', { class: 'notice warn' }, h('strong', null, 'Chame o atendente'), `Informe o código ${short(o.pedido)}. Você não será cobrado de novo.`),
    };
  }
  const text = { recusado: ['Pagamento recusado', 'O banco não aprovou. Nada foi cobrado. Tente de novo ou use outro meio.'], cancelado: ['Compra cancelada', 'Nenhum valor foi cobrado.'], expirado: ['Cobrança expirada', 'O prazo para pagar acabou. Gere uma nova cobrança.'] }[e] || ['Compra encerrada', ''];
  return { status: hero(e === 'recusado' ? 'x' : 'clock', e === 'recusado' ? 'bad' : '', text[0], text[1]), action: h('button', { id: 'b-retry', class: 'btn primary block', onclick: restart }, 'Tentar de novo') };
}

function build() {
  const stage = Stage.createStage();
  stage.el.append(h('div', { class: 'stage-tag' }, h('span', { id: 'tag-cap' }), h('h1', { id: 'tt' }, table.nome)));
  const price = h('p', { class: 'price num', id: 'price' });
  const cap = h('p', { class: 'cap', id: 'cap' });
  const steps = h('ol', { class: 'steps', 'aria-label': 'Etapas' }, STEPS.map(s => h('li', null, s)));
  const host = h('div', { class: 'stack-lg', id: 'host' });
  mount(h('main', { id: 'main', class: 'shell narrow stack' },
    h('header', { class: 'topbar' }, brand(table.estabelecimento), h('a', { class: 'small', href: '/' }, 'Outras mesas')),
    table.demo && h('p', { class: 'demo-pill', role: 'note' }, 'Demonstração: nenhum Pix real, nenhuma mesa física'),
    stage.el,
    h('section', { class: 'scoreboard', 'aria-label': 'Valor' }, h('div', null, h('p', { class: 'lbl' }, 'Valor'), cap), price),
    steps, host,
    h('footer', { class: 'foot' }, table.demo ? 'Demonstração local. Nada aqui movimenta dinheiro.' : 'Em caso de problema, chame o atendente.')));
  ui = { stage, price, cap, steps, host, capTag: document.getElementById('tag-cap') };
}

function draw() {
  if (!table) return;
  if (!ui) build();
  const p = panel();
  const etapa = order?.etapa || 'none';
  ui.capTag.textContent = CAPTION[etapa] || '';
  ui.stage.set(order?.etapa, { animate: lastEtapa !== null });
  lastEtapa = etapa;
  ui.price.textContent = money(order ? order.valor_centavos || table.preco_centavos : table.preco_centavos);
  ui.cap.textContent = order?.origem === 'MANUAL' ? 'Liberação autorizada pelo atendente' : '1 liberação de fichas';
  stepStates(order?.etapa).forEach((s, i) => {
    const li = ui.steps.children[i];
    li.dataset.s = s;
    if (s === 'now') li.setAttribute('aria-current', 'step'); else li.removeAttribute('aria-current');
  });
  const activeId = document.activeElement?.id;
  ui.host.replaceChildren(...[
    h('section', { class: 'card pad-lg', 'aria-live': 'polite', 'aria-atomic': 'true' }, p.status),
    offline && h('div', { class: 'notice warn', role: 'status' }, 'Sem conexão com o servidor. Tentando de novo…'),
    error && h('p', { class: 'error-text', role: 'alert' }, error),
    p.body,
    p.action && h('div', { class: order ? 'action' : 'sticky-action' }, p.action)].filter(Boolean));
  if (activeId) document.getElementById(activeId)?.focus();
}

async function refresh(force) {
  try {
    table = await api(`/api/mesas/${mesaId}`);
    if (order) {
      const id = typeof order === 'string' ? order : order.pedido;
      order = await api(`/api/pedidos/${encodeURIComponent(id)}`);
      if (order.mesa !== mesaId) { setOrder(null); order = null; }
    }
    offline = false;
  } catch (e) {
    if (e.status === 0) offline = true;
    else if (e.status === 404 && order) { setOrder(null); order = null; }
    else if (e.status === 404) return mount(h('main', { id: 'main', class: 'shell narrow stack-lg' }, h('header', { class: 'topbar' }, brand('Pagamento')), h('div', { class: 'notice bad', role: 'alert' }, h('strong', null, 'Mesa não encontrada'), 'Confira o QR code ou chame o atendente.'), h('a', { class: 'btn block', href: '/' }, 'Ver mesas')));
  }
  const sig = JSON.stringify([table?.online, table?.ocupada, table?.preco_centavos, order && [order.etapa, order.comando, order.controlador_online, order.demo_pagamento_permitido], offline, error, busy]);
  if (force || sig !== lastSig) { lastSig = sig; draw(); }
  return !(order && TERMINAL.includes(order.etapa));
}

(async () => {
  if (!/^\d{2,4}$/.test(mesaId || '')) return location.replace('/');
  order = new URLSearchParams(location.search).get('pedido') || sessionStorage.getItem(storeKey);
  await refresh(true);
  startPoll();
})();
