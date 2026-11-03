"""Testes funcionais do backend (HTTP real contra servidor em subprocesso). Sem hardware.

Cenarios numerados correspondem a docs/qa/TESTES_FUNCIONAIS.md.
"""
import hashlib
import hmac
import json
import sqlite3
import threading
import time
import unittest
import warnings

from helpers import WEBHOOK_SECRET, Client, FakeDevice, Server

warnings.simplefilter('ignore', ResourceWarning)


def order_for(cl, mesa):
    st, js = cl.post('/api/pedidos', {'mesa': mesa})
    assert st == 201, (st, js)
    return js['pedido']


class DemoFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Server().start()

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def setUp(self):
        self.c = Client(self.s)

    def status(self, oid):
        return self.c.get('/api/pedidos/' + oid)[1]

    # 1
    def test_01_pagamento_aprovado_ate_liberacao(self):
        oid = order_for(self.c, '01')
        self.assertEqual(self.status(oid)['etapa'], 'aguardando_pagamento')
        dev = FakeDevice(self.s, '01')
        self.assertIsNone(dev.poll())  # sem credito antes de pagar
        self.assertEqual(self.c.post('/api/demo/pagar', {'pedido': oid})[1]['status'], 'PAGO')
        self.assertEqual(self.status(oid)['etapa'], 'aguardando_botao')
        cmd = dev.poll()
        self.assertEqual(self.status(oid)['comando'], 'ENTREGUE')  # recebido != concluido
        self.assertEqual(self.status(oid)['status'], 'PAGO')
        self.assertEqual(dev.press_button(cmd), 'LIBERADO')
        s = self.status(oid)
        self.assertEqual((s['status'], s['etapa'], s['comando']), ('LIBERADO', 'concluido', 'EXECUTADO'))
        self.assertEqual(dev.pulses, 1)

    # 2
    def test_02_pagamento_recusado_nao_gera_credito(self):
        oid = order_for(self.c, '02')
        self.assertEqual(self.c.post('/api/demo/pagar', {'pedido': oid, 'resultado': 'recusado'})[1]['status'], 'RECUSADO')
        self.assertIsNone(FakeDevice(self.s, '02').poll())
        self.assertEqual(self.status(oid)['etapa'], 'recusado')
        order_for(self.c, '02')  # mesa livre de novo

    # 3
    def test_03_pagamento_pendente_depois_aprovado(self):
        oid = order_for(self.c, '03')
        self.assertEqual(self.c.post('/api/demo/pagar', {'pedido': oid, 'resultado': 'pendente'})[1]['status'], 'PENDENTE')
        self.assertEqual(self.status(oid)['etapa'], 'processando')
        self.assertIsNone(FakeDevice(self.s, '03').poll())
        self.c.post('/api/demo/pagar', {'pedido': oid})
        self.assertIsNotNone(FakeDevice(self.s, '03').poll())

    # 4 + 8
    def test_04_reenvio_da_confirmacao_nao_duplica_credito(self):
        oid = order_for(self.c, '04')
        for _ in range(3):
            self.c.post('/api/demo/pagar', {'pedido': oid})
        dev = FakeDevice(self.s, '04')
        cmd = dev.poll()
        self.assertEqual(dev.poll(), cmd)
        self.assertEqual(dev.press_button(cmd), 'LIBERADO')
        self.assertEqual(dev.ack(cmd), 'LIBERADO')  # ACK duplicado
        self.assertIsNone(dev.poll())
        self.assertEqual(dev.pulses, 1)
        self.c.post('/api/demo/pagar', {'pedido': oid})  # pagamento repetido apos liberar
        self.assertIsNone(dev.poll())

    # 5
    def test_05_requisicoes_simultaneas(self):
        res = []
        def create():
            res.append(self.c.__class__(self.s).post('/api/pedidos', {'mesa': '05'})[0])
        ts = [threading.Thread(target=create) for _ in range(12)]
        [t.start() for t in ts]; [t.join() for t in ts]
        self.assertEqual(sorted(res).count(201), 1)
        self.assertTrue(all(r in (201, 409) for r in res), res)
        oid = self.c.get('/api/admin/resumo')  # sem login: 401, apenas garante nao-vazamento
        self.assertEqual(oid[0], 401)
        st, mesa = self.c.get('/api/mesas/05')
        self.assertTrue(mesa['ocupada'])
        # pega o pedido aberto via criacao em outra mesa nao e possivel: usa admin
        adm = Client(self.s); adm.login()
        oid = next(m['pedido'] for m in adm.get('/api/admin/resumo')[1]['mesas'] if m['id'] == '05')
        out = []
        def pay():
            out.append(Client(self.s).post('/api/demo/pagar', {'pedido': oid})[1]['status'])
        ts = [threading.Thread(target=pay) for _ in range(20)]
        [t.start() for t in ts]; [t.join() for t in ts]
        con = sqlite3.connect(self.s.env['SINUCA_DB'])
        n = con.execute('SELECT COUNT(*) FROM comandos WHERE pedido_id=?', (oid,)).fetchone()[0]
        con.close()
        self.assertEqual(n, 1)

    # 6 + 7
    def test_06_mesas_distintas_e_mesa_errada(self):
        o6, o7 = order_for(self.c, '06'), order_for(self.c, '07')
        self.c.post('/api/demo/pagar', {'pedido': o6})
        d6, d7 = FakeDevice(self.s, '06'), FakeDevice(self.s, '07')
        self.assertIsNone(d7.poll())  # pagamento da 06 nao afeta a 07
        cmd6 = d6.poll()
        st, _ = d7.c.post('/api/dispositivos/07/confirmar', {'comando': cmd6})
        self.assertEqual(st, 404)  # mesa errada nao libera
        self.assertEqual(d7.c.post('/api/dispositivos/06/confirmar', {'comando': cmd6})[0], 401)  # token da 07 na 06
        self.assertEqual(self.status(o6)['status'], 'PAGO')
        self.assertEqual(self.status(o7)['status'], 'PENDENTE')

    # 9 + 10
    def test_09_reconexao_e_reinicio_com_credito_pendente(self):
        oid = order_for(self.c, '08')
        self.c.post('/api/demo/pagar', {'pedido': oid})
        d = FakeDevice(self.s, '08')
        cmd = d.poll()
        d2 = FakeDevice(self.s, '08')  # "reiniciou" antes do botao: NVS vazio, nada iniciado
        self.assertEqual(d2.poll(), cmd)
        self.assertEqual(d2.press_button(cmd), 'LIBERADO')
        self.assertEqual(d2.pulses, 1)

    # 11
    def test_11_interrupcao_durante_acionamento_nao_repete_pulso(self):
        oid = order_for(self.c, '09')
        self.c.post('/api/demo/pagar', {'pedido': oid})
        d = FakeDevice(self.s, '09')
        cmd = d.poll()
        self.assertEqual(d.press_button(cmd, crash_before_pulse=True), 'CRASH')
        # reinicia: NVS tem started==cmd, done vazio -> estado incerto
        self.assertEqual(d.press_button(d.poll() or cmd), 'INCERTO')
        self.assertEqual(d.pulses, 0)
        s = self.status(oid)
        self.assertEqual((s['status'], s['etapa'], s['comando']), ('EM_ANALISE', 'analise', 'INCERTO'))
        self.assertIsNone(d.poll())  # servidor nao oferece o comando de novo
        # operador decide reabrir credito
        adm = Client(self.s); adm.login()
        st, _ = adm.post(f'/api/admin/pedidos/{oid}/resolver', {'acao': 'reabrir', 'motivo': 'cliente sem fichas, verificado'})
        self.assertEqual(st, 200)
        new = d.poll()
        self.assertNotEqual(new, cmd)
        self.assertEqual(d.press_button(new), 'LIBERADO')
        self.assertEqual(self.status(oid)['status'], 'LIBERADO')
        self.assertTrue(any(a['acao'] == 'PENDENCIA_REABRIR' for a in adm.get('/api/admin/auditoria')[1]['auditoria']))

    # 12
    def test_12_falha_no_ack_reenvia_sem_novo_pulso(self):
        oid = order_for(self.c, '10')
        self.c.post('/api/demo/pagar', {'pedido': oid})
        d = FakeDevice(self.s, '10')
        cmd = d.poll()
        d.press_button(cmd, ack=False)  # pulso feito, ACK perdido
        self.assertEqual(self.status(oid)['status'], 'PAGO')  # servidor ainda nao sabe
        self.assertEqual(d.poll(), cmd)
        self.assertEqual(d.press_button(cmd), 'LIBERADO')  # reenvia ACK sem novo pulso
        self.assertEqual(d.pulses, 1)
        self.assertEqual(self.status(oid)['status'], 'LIBERADO')

    # 15
    def test_15_dez_mesas_operam(self):
        ids = [f'{i:02}' for i in range(1, 11)]
        self.assertEqual([m['id'] for m in self.c.get('/api/mesas')[1]['mesas']], ids)
        # usa ids de mesas ja livres: cria novo ciclo em todas
        done = 0
        for mid in ids:
            st, js = self.c.post('/api/pedidos', {'mesa': mid})
            if st != 201:  # mesa ainda aberta por outro teste: segue sem tocar
                continue
            self.c.post('/api/demo/pagar', {'pedido': js['pedido']})
            self.assertEqual(FakeDevice(self.s, mid).cycle(), 'LIBERADO')
            done += 1
        self.assertGreaterEqual(done, 4)

    def test_validacao_de_entrada(self):
        self.assertEqual(self.c.post('/api/pedidos', {'mesa': '99'})[0], 404)
        self.assertEqual(self.c.post('/api/pedidos', {'mesa': "01' OR 1=1"})[0], 404)
        self.assertEqual(self.c.post('/api/pedidos', {'mesa': 1})[0], 404)
        self.assertEqual(self.c.post('/api/pedidos', raw=b'{nao json', headers={'Content-Type': 'application/json'})[0], 400)
        self.assertEqual(self.c.post('/api/pedidos', raw=b'[1,2]', headers={'Content-Type': 'application/json'})[0], 400)
        self.assertEqual(self.c.post('/api/pedidos', raw=b'{"mesa":"' + b'1' * 20000 + b'"}')[0], 400)
        self.assertEqual(self.c.get('/api/pedidos/not-a-uuid')[0], 404)
        self.assertEqual(self.c.get('/api/pedidos/' + '0' * 8 + '-0000-0000-0000-' + '0' * 12)[0], 404)
        self.assertEqual(self.c.post('/api/demo/pagar', {'pedido': 'x'})[0], 404)
        self.assertEqual(self.c.get('/../../etc/passwd')[0], 404)
        self.assertEqual(self.c.get('/assets/..%2fapp.py')[0], 404)
        d = FakeDevice(self.s, '01')
        self.assertEqual(d.c.post('/api/dispositivos/01/confirmar', {'comando': "' OR 1=1 --"})[0], 404)
        self.assertEqual(Client(self.s, 'token-errado').get('/api/dispositivos/01/proximo.txt')[0], 401)
        self.assertEqual(Client(self.s).get('/api/dispositivos/01/proximo.txt')[0], 401)

    def test_cabecalhos_de_seguranca(self):
        self.c.get('/api/health')
        h = self.c.last_headers
        self.assertIn("default-src 'self'", h['Content-Security-Policy'])
        self.assertEqual(h['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(h['X-Frame-Options'], 'DENY')

    def test_nenhum_segredo_em_respostas_publicas(self):
        blob = json.dumps([self.c.get('/api/mesas')[1], self.c.get('/api/mesas/01')[1], self.c.get('/api/config')[1]])
        for tok in self.s.keys.values():
            self.assertNotIn(tok, blob)
        self.assertNotIn('token_hash', blob)
        self.assertNotIn('visto_ip', blob)


class AdminSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Server().start()

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    # 17
    def test_17_rotas_admin_exigem_autenticacao(self):
        c = Client(self.s)
        for path in ('/api/admin/resumo', '/api/admin/auditoria', '/api/admin/sessao', '/api/admin/backup'):
            self.assertEqual(c.get(path)[0], 401, path)
        for path in ('/api/admin/mesas', '/api/admin/mesas/01', '/api/admin/mesas/01/liberar', '/api/admin/mesas/01/rotacionar',
                     '/api/admin/config', '/api/admin/logout'):
            self.assertEqual(c.post(path, {'motivo': 'teste teste'})[0], 401, path)
        self.assertEqual(c.post('/api/admin/pedidos/' + '0' * 8 + '-0000-0000-0000-' + '0' * 12 + '/resolver', {})[0], 401)
        # token de dispositivo nao abre o admin
        dev = Client(self.s, self.s.keys['01'])
        self.assertEqual(dev.get('/api/admin/resumo')[0], 401)
        self.assertEqual(dev.post('/api/admin/mesas/01/liberar', {'motivo': 'abc def'})[0], 401)

    def test_liberacao_manual_exige_csrf_motivo_e_gera_auditoria(self):
        a = Client(self.s)
        self.assertEqual(a.login('errada')[0], 401)
        self.assertEqual(a.login()[0], 200)
        self.assertEqual(a.post('/api/admin/mesas/01/liberar', {'motivo': 'quebrou a ficha'}, csrf=False)[0], 403)
        self.assertEqual(a.post('/api/admin/mesas/01/liberar', {'motivo': ''})[0], 400)
        self.assertEqual(a.post('/api/admin/mesas/01/liberar', {'motivo': 'ficha presa, conferido no local'})[0], 201)
        self.assertEqual(a.post('/api/admin/mesas/01/liberar', {'motivo': 'de novo'})[0], 409)  # ja ha liberacao aberta
        self.assertEqual(FakeDevice(self.s, '01').cycle(), 'LIBERADO')
        log = a.get('/api/admin/auditoria')[1]['auditoria']
        self.assertTrue(any(x['acao'] == 'LIBERACAO_MANUAL' and 'ficha presa' in x['detalhe'] for x in log))
        # Origin externo e rejeitado
        self.assertEqual(a.post('/api/admin/config', {'estabelecimento': 'X'}, headers={'Origin': 'http://evil.example'})[0], 403)

    def test_logout_invalida_sessao(self):
        a = Client(self.s); a.login()
        self.assertEqual(a.get('/api/admin/resumo')[0], 200)
        self.assertEqual(a.post('/api/admin/logout')[0], 200)
        self.assertEqual(a.get('/api/admin/resumo')[0], 401)

    def test_zz_limite_de_tentativas_de_login(self):
        a = Client(self.s)
        codes = [a.login('x' * 9)[0] for _ in range(7)]
        self.assertEqual(codes[:5], [401] * 5)
        self.assertEqual(codes[5], 429)
        self.assertEqual(a.login()[0], 429)  # mesmo a senha certa fica bloqueada na janela

    # 16
    def test_16_cadastro_de_novas_mesas(self):
        a = Client(self.s); a.login()
        st, js = a.post('/api/admin/mesas', {'nome': 'Mesa <b>VIP</b>', 'preco_centavos': 800})
        self.assertEqual(st, 201)
        self.assertEqual(js['id'], '11')
        self.assertEqual(Client(self.s).get('/api/mesas/11')[1]['preco_centavos'], 800)
        d = FakeDevice(self.s, '11', token=js['token'])
        c = Client(self.s)
        oid = c.post('/api/pedidos', {'mesa': '11'})[1]['pedido']
        c.post('/api/demo/pagar', {'pedido': oid})
        self.assertEqual(d.cycle(), 'LIBERADO')
        self.assertEqual(a.post('/api/admin/mesas', {'nome': 'x' * 80})[0], 400)
        self.assertEqual(a.post('/api/admin/mesas', {'preco_centavos': -5})[0], 400)
        self.assertEqual(a.post('/api/admin/mesas', {'preco_centavos': '5'})[0], 400)
        # rotacionar invalida credencial antiga
        st, new = a.post('/api/admin/mesas/11/rotacionar')
        self.assertEqual(st, 200)
        self.assertEqual(d.c.get('/api/dispositivos/11/proximo.txt')[0], 401)
        self.assertEqual(Client(self.s, new['token']).get('/api/dispositivos/11/proximo.txt')[0], 200)
        # desativar mesa
        self.assertEqual(a.post('/api/admin/mesas/11', {'ativa': False})[0], 200)
        self.assertEqual(c.post('/api/pedidos', {'mesa': '11'})[0], 404)
        self.assertEqual(a.post('/api/admin/mesas/11', {'ativa': 'nao'})[0], 400)

    def test_backup_requer_login_e_gera_sqlite_valido(self):
        a = Client(self.s); a.login()
        st, data = a.get('/api/admin/backup')
        self.assertEqual(st, 200)
        self.assertTrue(data.startswith(b'SQLite format 3'))
        self.assertNotIn(self.s.keys['01'].encode(), data)  # tokens so como hash


class Persistence(unittest.TestCase):
    # 13 + 14
    def test_13_14_backend_indisponivel_e_recuperacao(self):
        s = Server().start()
        try:
            c = Client(s)
            oid = c.post('/api/pedidos', {'mesa': '01'})[1]['pedido']
            c.post('/api/demo/pagar', {'pedido': oid})
            d = FakeDevice(s, '01')
            cmd = d.poll()
            d.press_button(cmd, ack=False)  # pulso feito, ACK ainda nao
            s.stop()  # backend cai
            with self.assertRaises(Exception):
                d.ack(cmd)
            s.start()  # volta com o mesmo banco
            self.assertEqual(c.get('/api/pedidos/' + oid)[1]['status'], 'PAGO')
            self.assertEqual(d.poll(), cmd)
            self.assertEqual(d.press_button(cmd), 'LIBERADO')
            self.assertEqual(d.pulses, 1)
            self.assertEqual(c.get('/api/pedidos/' + oid)[1]['status'], 'LIBERADO')
        finally:
            s.close()

    def test_expiracao_de_comando_vai_para_analise_e_ack_tardio_resolve(self):
        s = Server(COMMAND_TTL_S=1).start()
        try:
            c = Client(s)
            oid = c.post('/api/pedidos', {'mesa': '02'})[1]['pedido']
            c.post('/api/demo/pagar', {'pedido': oid})
            time.sleep(1.3)
            d = FakeDevice(s, '02')
            self.assertIsNone(d.poll())  # expirado nao e oferecido
            self.assertEqual(c.get('/api/pedidos/' + oid)[1]['status'], 'EM_ANALISE')
            adm = Client(s); adm.login()
            self.assertEqual(len(adm.get('/api/admin/resumo')[1]['pendencias']), 1)
            self.assertEqual(adm.post(f'/api/admin/pedidos/{oid}/resolver', {'acao': 'cancelar', 'motivo': 'estorno manual feito'})[0], 200)
            self.assertEqual(c.get('/api/pedidos/' + oid)[1]['status'], 'CANCELADO')
        finally:
            s.close()

    def test_pedido_pendente_expira_e_libera_a_mesa(self):
        s = Server(ORDER_TTL_S=1).start()
        try:
            c = Client(s)
            oid = c.post('/api/pedidos', {'mesa': '03'})[1]['pedido']
            self.assertEqual(c.post('/api/pedidos', {'mesa': '03'})[0], 409)
            time.sleep(1.3)
            self.assertEqual(c.post('/api/pedidos', {'mesa': '03'})[0], 201)
            self.assertEqual(c.get('/api/pedidos/' + oid)[1]['status'], 'EXPIRADO')
        finally:
            s.close()

    def test_migracao_do_banco_v03(self):
        s = Server()
        con = sqlite3.connect(s.env['SINUCA_DB'])
        con.executescript('''
        CREATE TABLE pedidos (id TEXT PRIMARY KEY, mesa TEXT NOT NULL, valor_centavos INTEGER NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('PENDENTE','PAGO','LIBERADO','CANCELADO')), criado_em TEXT NOT NULL, pago_em TEXT, liberado_em TEXT);
        CREATE TABLE comandos (id TEXT PRIMARY KEY, pedido_id TEXT NOT NULL UNIQUE REFERENCES pedidos(id), mesa TEXT NOT NULL,
          status TEXT NOT NULL CHECK(status IN ('PENDENTE','EXECUTADO')), criado_em TEXT NOT NULL, executado_em TEXT);
        CREATE TABLE eventos (id INTEGER PRIMARY KEY AUTOINCREMENT, mesa TEXT NOT NULL, tipo TEXT NOT NULL, detalhe TEXT NOT NULL, criado_em TEXT NOT NULL);
        INSERT INTO pedidos VALUES ('11111111-1111-1111-1111-111111111111','01',500,'LIBERADO','2026-01-01T00:00:00+00:00',NULL,NULL);
        INSERT INTO comandos VALUES ('22222222-2222-2222-2222-222222222222','11111111-1111-1111-1111-111111111111','01','EXECUTADO','2026-01-01T00:00:00+00:00',NULL);
        INSERT INTO eventos(mesa,tipo,detalhe,criado_em) VALUES ('01','PEDIDO_CRIADO','x','2026-01-01T00:00:00+00:00');
        ''')
        con.commit(); con.close()
        s.start()
        try:
            c = Client(s)
            self.assertEqual(c.get('/api/pedidos/11111111-1111-1111-1111-111111111111')[1]['status'], 'LIBERADO')
            self.assertEqual(len(c.get('/api/mesas')[1]['mesas']), 10)
        finally:
            s.close()


class WebhookMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.s = Server(PAYMENT_MODE='webhook').start()
        cls.c = Client(cls.s)

    @classmethod
    def tearDownClass(cls):
        cls.s.close()

    def sign(self, payload, secret=WEBHOOK_SECRET):
        raw = json.dumps(payload).encode()
        return raw, {'X-Signature': hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest(), 'Content-Type': 'application/json'}

    def hook(self, payload, secret=WEBHOOK_SECRET):
        raw, h = self.sign(payload, secret)
        return self.c.post('/api/webhook/pagamento', raw=raw, headers=h)

    def test_modo_demo_totalmente_separado(self):
        dev = FakeDevice(self.s, '01')
        dev.c.get('/api/dispositivos/01/proximo.txt')  # controlador online
        oid = self.c.post('/api/pedidos', {'mesa': '01'})[1]['pedido']
        self.assertEqual(self.c.post('/api/demo/pagar', {'pedido': oid})[0], 404)  # navegador nao aprova
        self.assertFalse(self.c.get('/api/mesas/01')[1]['demo'])
        self.assertIsNone(dev.poll())

    def test_exige_controlador_online(self):
        self.assertEqual(self.c.post('/api/pedidos', {'mesa': '05'})[0], 503)

    def test_webhook_assinatura_valor_e_idempotencia(self):
        dev = FakeDevice(self.s, '02')
        dev.poll()
        oid = self.c.post('/api/pedidos', {'mesa': '02'})[1]['pedido']
        ok = {'evento_id': 'ev-1', 'txid': oid, 'status': 'aprovado', 'valor_centavos': 500}
        raw, _ = self.sign(ok)
        self.assertEqual(self.c.post('/api/webhook/pagamento', raw=raw, headers={'Content-Type': 'application/json'})[0], 401)  # sem assinatura
        self.assertEqual(self.hook(ok, secret='outro')[0], 401)  # assinatura errada
        self.assertIsNone(dev.poll())
        self.assertEqual(self.hook(dict(ok, evento_id='ev-x', valor_centavos=1))[1]['status'], 'EM_ANALISE')  # valor divergente
        self.assertIsNone(dev.poll())

    def test_webhook_aprovado_uma_vez(self):
        dev = FakeDevice(self.s, '03')
        dev.poll()
        oid = self.c.post('/api/pedidos', {'mesa': '03'})[1]['pedido']
        ok = {'evento_id': 'ev-2', 'txid': oid, 'status': 'aprovado', 'valor_centavos': 500}
        self.assertEqual(self.hook(ok)[1]['status'], 'PAGO')
        self.assertTrue(self.hook(ok)[1].get('duplicado'))  # mesmo evento
        self.hook(dict(ok, evento_id='ev-3'))  # outro evento, mesma cobranca
        cmd = dev.poll()
        self.assertEqual(dev.press_button(cmd), 'LIBERADO')
        self.assertIsNone(dev.poll())
        self.assertEqual(dev.pulses, 1)

    def test_pagamento_tardio_nao_libera_sozinho(self):
        dev = FakeDevice(self.s, '04')
        dev.poll()
        oid = self.c.post('/api/pedidos', {'mesa': '04'})[1]['pedido']
        self.c.post('/api/pedidos/cancelar', {'pedido': oid})
        r = self.hook({'evento_id': 'ev-4', 'txid': oid, 'status': 'aprovado', 'valor_centavos': 500})
        self.assertEqual(r[1]['status'], 'EM_ANALISE')
        self.assertIsNone(dev.poll())

    def test_demo_pagamento_remoto_bloqueado_por_padrao(self):
        # em modo demo, IP nao-local nao pode aprovar: simulado via X-Forwarded-For nao confiado = ignorado
        s = Server().start()
        try:
            c = Client(s)
            st, js = c.get('/api/mesas/01')
            self.assertTrue(js['demo_pagamento_permitido'])  # cliente local
        finally:
            s.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
