// Prepara estados reais via API (sem mock de tela): uma mesa por estado de interface.
const fs = require('fs');
const path = require('path');
const { request } = require('@playwright/test');

const TMP = path.join(__dirname, '..', '.tmp');
const BASE = 'http://127.0.0.1:8791';

module.exports = async () => {
  const keys = JSON.parse(fs.readFileSync(path.join(TMP, 'keys.json'), 'utf8'));
  const api = await request.newContext({ baseURL: BASE });
  const post = async (p, b, headers = {}) => (await api.post(p, { data: b, headers })).json();
  const dev = mesa => ({ Authorization: `Bearer ${keys[mesa]}` });
  const order = async mesa => (await post('/api/pedidos', { mesa })).pedido;
  const next = async mesa => (await (await api.get(`/api/dispositivos/${mesa}/proximo.txt`, { headers: dev(mesa) })).text()).trim();
  const states = {};
  // heartbeat: a maioria dos controladores aparece online; 07, 10 e 11 ficam offline para exibir esse estado
  for (const m of ['01', '02', '03', '04', '05', '06', '08', '09']) await api.get(`/api/dispositivos/${m}/proximo.txt`, { headers: dev(m) });

  // prova de estado ja preparado em execucao anterior com o mesmo banco
  states.aguardando = await order('02');
  states.processando = await order('03');
  await post('/api/demo/pagar', { pedido: states.processando, resultado: 'pendente' });
  states.credito = await order('04');
  await post('/api/demo/pagar', { pedido: states.credito });
  states.botao = await order('05');
  await post('/api/demo/pagar', { pedido: states.botao });
  await next('05'); // controlador recebe o credito
  states.concluido = await order('06');
  await post('/api/demo/pagar', { pedido: states.concluido });
  await post('/api/dispositivos/06/confirmar', { comando: await next('06'), duracao_ms: 350 }, dev('06'));
  states.recusado = await order('07');
  await post('/api/demo/pagar', { pedido: states.recusado, resultado: 'recusado' });
  states.analise = await order('08');
  await post('/api/demo/pagar', { pedido: states.analise });
  await post('/api/dispositivos/08/incerto', { comando: await next('08') }, dev('08'));

  const adm = await request.newContext({ baseURL: BASE });
  const login = await (await adm.post('/api/admin/login', { data: { senha: 'qa-senha-123' } })).json();
  const H = { 'X-CSRF-Token': login.csrf };
  // nome longo e hostil: prova escape e quebra de linha
  await adm.post('/api/admin/mesas/10', { data: { nome: 'Mesa VIP <img src=x onerror=alert(1)>' }, headers: H });
  await adm.post('/api/admin/mesas', { data: { nome: 'Mesa 11 reserva' }, headers: H });
  // mesas extras livres e online para os testes de animação (12..16); credenciais ficam só no arquivo temporário de QA
  const extra = { ...keys };
  for (let i = 12; i <= 16; i++) {
    const r = await (await adm.post('/api/admin/mesas', { data: { nome: `Mesa ${i}` }, headers: H })).json();
    extra[r.id] = r.token;
    await api.get(`/api/dispositivos/${r.id}/proximo.txt`, { headers: { Authorization: `Bearer ${r.token}` } });
  }
  fs.writeFileSync(path.join(TMP, 'keys.json'), JSON.stringify(extra));
  await adm.post('/api/admin/mesas/09/liberar', { data: { motivo: 'ficha presa, conferido pelo atendente' }, headers: H });
  await adm.storageState({ path: path.join(TMP, 'admin.json') });
  fs.writeFileSync(path.join(TMP, 'states.json'), JSON.stringify(states));
};
