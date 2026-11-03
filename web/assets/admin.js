'use strict';
/* Painel do atendente. Todas as ações exigem sessão + CSRF; o servidor revalida tudo. */
let csrf = null, data = null, audit = null, view = 'mesas', lastSig = '', dialogOpen = false, stopPoll = null;

const ORDER = { PENDENTE: ['Aguardando pagamento', 'info'], PAGO: ['Pago, aguardando botão', 'warn'], LIBERADO: ['Liberado', 'ok'], CANCELADO: ['Cancelado', 'idle'], RECUSADO: ['Recusado', 'bad'], EXPIRADO: ['Expirado', 'idle'], EM_ANALISE: ['Em análise', 'bad'], DISPONIVEL: ['Livre', 'ok'] };
const CMD = { PENDENTE: 'crédito disponível', ENTREGUE: 'comando recebido pela mesa', INICIADO: 'acionamento iniciado', EXECUTADO: 'acionamento concluído', INCERTO: 'estado incerto', EXPIRADO: 'comando expirado', CANCELADO: 'comando cancelado' };
const EVENT = {
  PEDIDO_CRIADO: 'Cobrança criada', PEDIDO_CANCELADO: 'Cobrança cancelada', PEDIDO_EXPIRADO: 'Cobrança expirou sem pagamento',
  PAGAMENTO_SIMULADO: 'Pagamento simulado aprovado', PAGAMENTO_SIMULADO_RECUSADO: 'Pagamento simulado recusado', PAGAMENTO_SIMULADO_PENDENTE: 'Pagamento simulado em processamento',
  PAGAMENTO_CONFIRMADO_PROVEDOR: 'Pagamento confirmado pelo provedor', PAGAMENTO_RECUSADO: 'Pagamento recusado', PAGAMENTO_VALOR_DIVERGENTE: 'Valor divergente: conferir', PAGAMENTO_TARDIO: 'Pagamento após o prazo: conferir',
  COMANDO_RECEBIDO_PELO_CONTROLADOR: 'Controlador recebeu o crédito', ACIONAMENTO_INICIADO: 'Acionamento iniciado', ACIONAMENTO_CONCLUIDO_E_PERSISTIDO: 'Acionamento concluído e registrado',
  COMANDO_EXPIRADO_SEM_ACIONAMENTO: 'Crédito expirou sem acionamento', ESTADO_INCERTO_REPORTADO: 'Controlador reportou estado incerto', EXECUCAO_DE_COMANDO_CANCELADO: 'Execução de comando cancelado: conferir',
  LIBERACAO_MANUAL_AUTORIZADA: 'Liberação manual autorizada', PENDENCIA_RESOLVIDA_REABRIR: 'Pendência: crédito reaberto', PENDENCIA_RESOLVIDA_LIBERADO: 'Pendência: marcada como liberada', PENDENCIA_RESOLVIDA_CANCELAR: 'Pendência: cancelada',
};
const AUDIT = { LOGIN: 'Login', LIBERACAO_MANUAL: 'Liberação manual', MESA_CRIADA: 'Mesa criada', MESA_ATUALIZADA: 'Mesa alterada', CREDENCIAL_ROTACIONADA: 'Credencial rotacionada', CONFIG_ATUALIZADA: 'Ajustes alterados', BACKUP_BAIXADO: 'Backup baixado', PENDENCIA_REABRIR: 'Pendência: reabrir', PENDENCIA_LIBERADO: 'Pendência: liberado', PENDENCIA_CANCELAR: 'Pendência: cancelar' };

const post = (path, body) => api(path, body ?? {}, { csrf });
const badge = (key) => { const [t, c] = ORDER[key] || [key, 'idle']; return h('span', { class: `badge ${c}` }, t); };

function ask({ title, text, fields = [], submit = 'Confirmar', danger = false }) {
  return new Promise(resolve => {
    dialogOpen = true;
    const err = h('p', { class: 'error-text', role: 'alert', hidden: true });
    const inputs = fields.map(f => {
      const id = 'f_' + f.name;
      const control = f.type === 'textarea' ? h('textarea', { id, name: f.name, required: f.required, maxlength: f.max || 200, rows: 3 }, f.value || '')
        : f.type === 'select' ? h('select', { id, name: f.name }, f.options.map(([v, l]) => h('option', { value: v }, l)))
        : f.type === 'checkbox' ? h('input', { id, name: f.name, type: 'checkbox', checked: f.value, class: 'check' })
        : h('input', { id, name: f.name, type: f.type || 'text', required: f.required, maxlength: f.max || 40, value: f.value ?? '', inputmode: f.inputmode, min: f.min, autocomplete: 'off' });
      return h('div', { class: 'field' }, h('label', { for: id }, f.label), control, f.hint && h('span', { class: 'hint' }, f.hint));
    });
    const dlg = h('dialog', { 'aria-labelledby': 'dlg-t' },
      h('form', { method: 'dialog', onsubmit: ev => {
        ev.preventDefault();
        const out = {};
        for (const f of fields) { const el = dlg.querySelector('#f_' + f.name); out[f.name] = f.type === 'checkbox' ? el.checked : el.value.trim(); }
        done(out);
      } },
      h('h2', { id: 'dlg-t' }, title), text && h('p', { class: 'muted' }, text), inputs, err,
      h('div', { class: 'row' },
        h('button', { class: 'btn grow', type: 'button', onclick: () => done(null) }, 'Cancelar'),
        h('button', { class: `btn grow ${danger ? 'danger' : 'primary'}`, type: 'submit' }, submit))));
    function done(v) { dlg.close(); dlg.remove(); dialogOpen = false; resolve(v); }
    dlg.addEventListener('cancel', () => { dialogOpen = false; dlg.remove(); resolve(null); });
    document.body.append(dlg);
    dlg.showModal();
    dlg.querySelector('input,textarea,select')?.focus();
  });
}

function showSecret(title, id, token) {
  return new Promise(resolve => {
    dialogOpen = true;
    const dlg = h('dialog', { 'aria-labelledby': 'dlg-s' },
      h('div', { class: 'stack' }, h('h2', { id: 'dlg-s' }, title),
        h('p', { class: 'notice warn' }, `Esta credencial da mesa ${id} aparece só agora. Grave-a no firmware (gerar_firmware.py --token) e não a compartilhe.`),
        h('p', { class: 'secret', tabindex: 0 }, token),
        h('div', { class: 'row' },
          h('button', { class: 'btn grow', onclick: async () => { try { await navigator.clipboard.writeText(token); toast('Credencial copiada'); } catch { toast('Copie manualmente: o campo está selecionável', true); } } }, 'Copiar'),
          h('button', { class: 'btn primary grow', onclick: () => { dlg.close(); dlg.remove(); dialogOpen = false; resolve(); } }, 'Já guardei'))));
    document.body.append(dlg);
    dlg.showModal();
  });
}

async function act(fn, okMsg) {
  try { await fn(); if (okMsg) toast(okMsg); await load(true); } catch (e) { if (e.status === 401) return loginView(); toast(e.message, true); }
}

/* ---------- ações ---------- */
const manualRelease = async t => {
  const v = await ask({ title: `Liberar a mesa ${t.id} manualmente`, text: 'Gera um crédito sem cobrança. Fica registrado na auditoria com o seu motivo.', submit: 'Autorizar liberação',
    fields: [{ name: 'motivo', label: 'Motivo', type: 'textarea', required: true, hint: 'Ex.: ficha presa, cortesia autorizada.' }] });
  if (v) act(() => post(`/api/admin/mesas/${t.id}/liberar`, v), 'Crédito criado: a mesa libera quando o botão for apertado');
};
const editTable = async t => {
  const v = await ask({ title: `Editar ${t.nome}`, submit: 'Salvar', fields: [
    { name: 'nome', label: 'Nome', required: true, value: t.nome },
    { name: 'preco', label: 'Preço em centavos', type: 'number', inputmode: 'numeric', min: 1, value: t.preco_centavos ?? '', hint: `Vazio usa o preço padrão (${money(data.preco_padrao_centavos)}).` },
    { name: 'ativa', label: 'Mesa ativa (aceita pagamentos)', type: 'checkbox', value: t.ativa }] });
  if (!v) return;
  const body = { nome: v.nome, ativa: v.ativa, preco_centavos: v.preco === '' ? null : Number(v.preco) };
  act(() => post(`/api/admin/mesas/${t.id}`, body), 'Mesa atualizada');
};
const newTable = async () => {
  const v = await ask({ title: 'Nova mesa', text: 'O número é o próximo livre. A credencial do controlador é mostrada uma única vez.', submit: 'Cadastrar', fields: [
    { name: 'nome', label: 'Nome (opcional)' },
    { name: 'preco', label: 'Preço em centavos (opcional)', type: 'number', inputmode: 'numeric', min: 1 }] });
  if (!v) return;
  try {
    const r = await post('/api/admin/mesas', { nome: v.nome || undefined, preco_centavos: v.preco === '' ? undefined : Number(v.preco) });
    await load(true);
    await showSecret(`Mesa ${r.id} cadastrada`, r.id, r.token);
  } catch (e) { toast(e.message, true); }
};
const rotate = async t => {
  const v = await ask({ title: `Rotacionar credencial da mesa ${t.id}`, text: 'A credencial atual deixa de valer na hora. O controlador ficará sem comunicação até receber o firmware novo.', submit: 'Rotacionar', danger: true, fields: [] });
  if (!v) return;
  try { const r = await post(`/api/admin/mesas/${t.id}/rotacionar`); await load(true); await showSecret(`Nova credencial da mesa ${t.id}`, t.id, r.token); } catch (e) { toast(e.message, true); }
};
const resolveIssue = async p => {
  const v = await ask({ title: `Resolver pendência da mesa ${p.mesa}`, text: `Pedido ${short(p.id)}, ${money(p.valor_centavos)}. Confira a mesa antes de decidir.`, submit: 'Aplicar', fields: [
    { name: 'acao', label: 'Decisão', type: 'select', options: [['reabrir', 'Reabrir crédito (a mesa libera de novo)'], ['liberado', 'Marcar como liberado (conferi que as fichas saíram)'], ['cancelar', 'Cancelar (estorno feito fora do sistema)']] },
    { name: 'motivo', label: 'Motivo', type: 'textarea', required: true }] });
  if (v) act(() => post(`/api/admin/pedidos/${p.id}/resolver`, v), 'Pendência resolvida');
};

/* ---------- telas ---------- */
function loginView(message) {
  stopPoll?.(); csrf = null;
  const err = h('p', { class: 'error-text', role: 'alert' }, message || '');
  mount(h('main', { id: 'main', class: 'shell narrow stack-lg' },
    h('header', { class: 'topbar' }, brand('Área do atendente'), h('a', { class: 'small', href: '/' }, 'Voltar')),
    h('form', { class: 'card pad-lg stack', onsubmit: async ev => {
      ev.preventDefault();
      const input = ev.target.senha, btn = ev.target.querySelector('button');
      btn.disabled = true; err.textContent = '';
      try { const r = await api('/api/admin/login', { senha: input.value }); csrf = r.csrf; await start(); } catch (e) { err.textContent = e.message; btn.disabled = false; input.select(); }
    } },
    h('h1', null, 'Entrar'), h('p', { class: 'muted' }, 'Acesso restrito ao atendente do estabelecimento.'),
    h('div', { class: 'field' }, h('label', { for: 'senha' }, 'Senha'), h('input', { id: 'senha', name: 'senha', type: 'password', autocomplete: 'current-password', required: true, maxlength: 200 })),
    err, h('button', { class: 'btn primary block', type: 'submit' }, 'Entrar'))));
  document.getElementById('senha')?.focus();
}

function header() {
  const tabs = [['mesas', 'Mesas'], ['historico', 'Histórico'], ['auditoria', 'Auditoria'], ['ajustes', 'Ajustes']];
  return h('header', { class: 'stack' },
    h('div', { class: 'topbar' }, brand(data.estabelecimento, '/admin'),
      h('button', { class: 'btn sm', onclick: async () => { await post('/api/admin/logout').catch(() => {}); loginView(); } }, 'Sair')),
    data.demo && demoBanner(),
    h('nav', { class: 'nav', 'aria-label': 'Seções' }, tabs.map(([k, l]) => h('a', { href: '#' + k, 'aria-current': view === k ? 'page' : null }, l))));
}

function tableCard(t) {
  const [label, tone] = ORDER[t.estado] || [t.estado, 'idle'];
  return h('article', { class: 'card tcard' + (t.ativa ? '' : ' inactive'), 'aria-label': t.nome },
    h('div', { class: 'head' }, h('div', { class: 'name' }, t.nome), h('span', { class: `badge ${t.ativa ? tone : 'idle'}` }, t.ativa ? label : 'Inativa')),
    h('div', { class: 'small muted' },
      h('div', { class: 'row' }, h('span', { class: 'dot ' + (t.online ? 'on' : 'off'), role: 'img', 'aria-label': t.online ? 'online' : 'offline' }), t.online ? 'Controlador online' : `Controlador offline · visto ${ago(t.visto_em)}`),
      h('div', null, `Preço ${money(t.preco_efetivo_centavos)}${t.preco_centavos ? '' : ' (padrão)'}`),
      t.comando && h('div', null, `Último comando: ${CMD[t.comando] || t.comando}`),
      t.firmware && h('div', null, `Firmware ${t.firmware}`)),
    h('div', { class: 'actions' },
      h('button', { class: 'btn sm', onclick: () => manualRelease(t), disabled: !t.ativa || t.estado !== 'DISPONIVEL' }, 'Liberar'),
      h('button', { class: 'btn sm ghost', onclick: () => editTable(t) }, 'Editar'),
      h('button', { class: 'btn sm ghost', onclick: () => rotate(t) }, 'Credencial')));
}

function viewMesas() {
  const free = data.mesas.filter(m => m.ativa && m.estado === 'DISPONIVEL').length;
  const busy = data.mesas.filter(m => m.ativa && ['PENDENTE', 'PAGO'].includes(m.estado)).length;
  const off = data.mesas.filter(m => m.ativa && !m.online).length;
  const stat = (v, l) => h('div', { class: 'card stat' }, h('div', { class: 'v' }, v), h('div', { class: 'l' }, l));
  return [
    h('section', { class: 'stats', 'aria-label': 'Resumo' }, stat(free, 'Livres'), stat(busy, 'Em compra'), stat(off, 'Controladores offline'),
      stat(data.hoje.liberacoes, `Liberações hoje · ${money(data.hoje.total_centavos)}`)),
    data.pendencias.length ? h('section', { class: 'stack', 'aria-labelledby': 'pend' },
      h('h2', { id: 'pend' }, `Pendências (${data.pendencias.length})`),
      data.pendencias.map(p => h('div', { class: 'notice bad row between' },
        h('div', null, h('strong', null, `Mesa ${p.mesa} · ${money(p.valor_centavos)}`), `Pedido ${short(p.id)}. ${p.comando ? 'Último comando: ' + (CMD[p.comando] || p.comando) + '.' : ''} Confira a mesa antes de decidir.`),
        h('button', { class: 'btn sm', onclick: () => resolveIssue(p) }, 'Resolver')))) : null,
    h('section', { 'aria-labelledby': 'mm' },
      h('div', { class: 'section-head' }, h('h2', { id: 'mm' }, plural(data.mesas.length, 'mesa', 'mesas')), h('button', { class: 'btn primary sm', onclick: newTable }, 'Nova mesa')),
      data.mesas.length ? h('div', { class: 'admin-tables' }, data.mesas.map(tableCard)) : h('p', { class: 'empty' }, 'Nenhuma mesa cadastrada. Use “Nova mesa”.')),
  ];
}

function viewHistorico() {
  return [
    h('section', { 'aria-labelledby': 'h1' }, h('div', { class: 'section-head' }, h('h2', { id: 'h1' }, 'Últimas cobranças')),
      data.pedidos.length ? h('div', { class: 'tablewrap', tabindex: 0, role: 'region', 'aria-label': 'Últimas cobranças (rolável)' }, h('table', null, h('caption', { class: 'sr-only' }, 'Últimas cobranças'),
        h('thead', null, h('tr', null, ['Mesa', 'Código', 'Valor', 'Situação', 'Origem', 'Criada'].map(c => h('th', { scope: 'col' }, c)))),
        h('tbody', null, data.pedidos.map(p => h('tr', null, h('td', null, h('strong', null, p.mesa)), h('td', { class: 'mono' }, short(p.id)), h('td', { class: 'num' }, money(p.valor_centavos)),
          h('td', null, badge(p.status)), h('td', null, { DEMO: 'Demonstração', PIX: 'Pix', MANUAL: 'Manual' }[p.origem]), h('td', { class: 'num' }, when(p.criado_em))))))) : h('p', { class: 'empty' }, 'Nenhuma cobrança ainda.')),
    h('section', { 'aria-labelledby': 'h2' }, h('div', { class: 'section-head' }, h('h2', { id: 'h2' }, 'Eventos recentes')),
      data.eventos.length ? h('ul', { class: 'feed card' }, data.eventos.map(e => h('li', null, h('span', null, h('strong', null, `Mesa ${e.mesa}`), ' · ', EVENT[e.tipo] || e.tipo), h('span', { class: 'muted num' }, when(e.criado_em))))) : h('p', { class: 'empty' }, 'Sem eventos.')),
  ];
}

function viewAuditoria() {
  if (!audit) return [h('div', { class: 'skeleton sk-block' })];
  return [h('section', { 'aria-labelledby': 'a1' }, h('div', { class: 'section-head' }, h('h2', { id: 'a1' }, 'Ações do atendente'), h('p', { class: 'muted small' }, 'Registro permanente de ações administrativas.')),
    audit.length ? h('div', { class: 'tablewrap', tabindex: 0, role: 'region', 'aria-label': 'Auditoria (rolável)' }, h('table', null, h('caption', { class: 'sr-only' }, 'Auditoria'),
      h('thead', null, h('tr', null, ['Quando', 'Ação', 'Alvo', 'Detalhe', 'IP'].map(c => h('th', { scope: 'col' }, c)))),
      h('tbody', null, audit.map(a => h('tr', null, h('td', { class: 'num' }, when(a.criado_em)), h('td', null, AUDIT[a.acao] || a.acao), h('td', null, a.alvo.length > 12 ? short(a.alvo) : a.alvo), h('td', { class: 'wrap' }, a.detalhe || '—'), h('td', { class: 'mono' }, a.ip)))))) : h('p', { class: 'empty' }, 'Sem registros.'))];
}

function viewAjustes() {
  return [h('section', { class: 'card pad-lg stack', 'aria-labelledby': 'aj' }, h('h2', { id: 'aj' }, 'Estabelecimento'),
    h('form', { class: 'stack', onsubmit: async ev => {
      ev.preventDefault();
      const f = ev.target;
      act(() => post('/api/admin/config', { estabelecimento: f.nome.value, preco_padrao_centavos: Number(f.preco.value) }), 'Ajustes salvos');
    } },
    h('div', { class: 'field' }, h('label', { for: 'c-nome' }, 'Nome exibido aos clientes'), h('input', { id: 'c-nome', name: 'nome', value: data.estabelecimento, maxlength: 60, required: true })),
    h('div', { class: 'field' }, h('label', { for: 'c-preco' }, 'Preço padrão em centavos'), h('input', { id: 'c-preco', name: 'preco', type: 'number', inputmode: 'numeric', min: 1, max: 100000, value: data.preco_padrao_centavos, required: true }), h('span', { class: 'hint' }, `Atual: ${money(data.preco_padrao_centavos)}. Mesas com preço próprio não mudam.`)),
    h('button', { class: 'btn primary', type: 'submit' }, 'Salvar ajustes'))),
  h('section', { class: 'card pad-lg stack', 'aria-labelledby': 'ut' }, h('h2', { id: 'ut' }, 'Ferramentas'),
    h('div', { class: 'row' }, h('a', { class: 'btn', href: '/admin/placas' }, 'Imprimir QR codes'), h('a', { class: 'btn', href: '/api/admin/backup', download: '' }, 'Baixar backup do banco')),
    h('p', { class: 'muted small' }, `Modo de pagamento: ${data.demo ? 'demonstração (fictício)' : 'webhook do provedor'}. Faça backups regulares; veja docs/OPERACAO.md.`))];
}

function draw() {
  const body = { mesas: viewMesas, historico: viewHistorico, auditoria: viewAuditoria, ajustes: viewAjustes }[view]();
  const y = window.scrollY;
  mount(h('main', { id: 'main', class: 'shell stack-lg' }, header(), h('div', { class: 'stack-lg' }, body), h('footer', { class: 'foot' }, 'Ações administrativas ficam registradas na auditoria.')));
  window.scrollTo(0, y);
}

async function load(force) {
  if (dialogOpen && !force) return;
  data = await api('/api/admin/resumo');
  if (view === 'auditoria') audit = (await api('/api/admin/auditoria')).auditoria;
  const sig = JSON.stringify([view, data, audit]);
  if (force || sig !== lastSig) { lastSig = sig; if (!dialogOpen) draw(); }
}

function route() {
  const v = location.hash.slice(1);
  view = ['mesas', 'historico', 'auditoria', 'ajustes'].includes(v) ? v : 'mesas';
  lastSig = '';
  if (data) load(true).catch(() => {});
}
window.addEventListener('hashchange', route);

async function start() {
  stopPoll?.();
  route();
  await load(true);
  stopPoll = poll(async () => { try { await load(false); } catch (e) { if (e.status === 401) { loginView('Sessão encerrada. Entre de novo.'); return false; } } }, { base: 3000, slow: 8000 });
}

(async () => {
  try {
    const s = await api('/api/admin/estado');
    if (!s.autenticado) return loginView();
    csrf = s.csrf;
    await start();
  } catch (e) { loginView(); }
})();
