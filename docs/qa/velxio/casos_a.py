"""Casos T1, T2, T3, T6, T7, T8, T10 no ESP32 emulado do Velxio padrao (QEMU real) contra o backend real.

Ambiente: MF_TMP (dir temporario com firmware.b64, keys.json, db.sqlite3), SINUCA_KEYS, PYTHONPATH com websockets.
"""
import json
import os
import re
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import api
from emu import Emu
from harness import PORT, REPO, TMP, Log, Server

log = Log('casos_a')
srv = Server()
srv.start()
fw = (TMP / 'firmware.b64').read_text()
adm = api.Admin()
result = {}


def cmds():
    c = sqlite3.connect(f'file:{TMP / "db.sqlite3"}?mode=ro', uri=True)
    return c.execute('select id,mesa,pedido_id,status from comandos order by criado_em').fetchall()


def audit_tail(n=6):
    return [f"{a.get('tipo') or a.get('acao')} {str(a.get('detalhe', ''))[:8]}" for a in api.Admin().auditoria()[:n]]


def novo_e_pago(mesa='01'):
    oid = api.novo_pedido(mesa)
    log(f'POST /api/pedidos mesa={mesa} -> pedido {oid[:8]}.. status', api.status(oid))
    st, r = api.pagar(oid)
    log(f'POST /api/demo/pagar -> HTTP {st} status={r.get("status")}')
    return oid


def pedido_info(oid):
    o = api.pedido(oid)
    return f"status={o['status']} comando={o['comando']} etapa={o['etapa']}"


e = Emu(fw)
e.start()
ok = e.wait_for('WiFi conectado', 90)
log('boot:', 'WiFi conectado' if ok else 'FALHOU')
time.sleep(4)
log('Serial de boot:\n' + e.text_since(0)[:1500].replace('\r', ''))
assert 'MesaFacil v0.4' in e.text_since(0)

# ---------------------------------------------------------------- T1
log('\n===== T1 fluxo completo =====')
m = e.mark()
n_pulsos0 = len(e.pulses())
oid1 = novo_e_pago('01')
r1 = e.wait_for('Pressione o botao', 15, m)
log('firmware recebeu comando:', r1, '| backend:', pedido_info(oid1))
e.press()
r2 = e.wait_for('ACK: HTTP 200', 20, m)
time.sleep(1)
p = e.pulses()[n_pulsos0:]
log('pulsos GPIO26 em nivel BAIXO (inicio_s, duracao_s):', [(round(a, 2), round(b, 3)) for a, b in p])
log('backend final:', pedido_info(oid1))
e.t = e.text_since(m)
log.block('Serial T1', e.t)
result['T1'] = 'PASS' if (r1 and r2 and len(p) == 1 and 0.3 <= p[0][1] <= 0.45 and api.status(oid1) == 'LIBERADO') else 'FAIL'

# ---------------------------------------------------------------- T2
log('\n===== T2 segundo clique sem novo pagamento =====')
m = e.mark()
n = len(e.pulses())
for _ in range(2):
    e.press()
    time.sleep(1)
time.sleep(5)  # deixa passar >= 2 polls
log('pulsos novos:', len(e.pulses()) - n, '| backend:', pedido_info(oid1))
log.block('Serial T2', e.text_since(m))
result['T2'] = 'PASS' if (len(e.pulses()) == n and 'BOTAO: sem credito' in e.text_since(m) and 'FICHAS' not in e.text_since(m)) else 'FAIL'

# ---------------------------------------------------------------- T3
log('\n===== T3 segundo pagamento legitimo =====')
m = e.mark()
n = len(e.pulses())
oid3 = novo_e_pago('01')
r1 = e.wait_for('Pressione o botao', 15, m)
e.press()
r2 = e.wait_for('ACK: HTTP 200', 20, m)
time.sleep(1)
log('pulsos novos:', len(e.pulses()) - n, '| ids distintos:', oid3 != oid1, '| backend:', pedido_info(oid3))
log.block('Serial T3', e.text_since(m))
result['T3'] = 'PASS' if (r1 and r2 and len(e.pulses()) == n + 1 and api.status(oid3) == 'LIBERADO') else 'FAIL'

# ---------------------------------------------------------------- T7
log('\n===== T7 ACK perdido (backend cai logo apos o pulso) =====')
m = e.mark()
n = len(e.pulses())
oid7 = novo_e_pago('01')
e.wait_for('Pressione o botao', 15, m)
e.press(0.3)
e.wait_for('FICHAS LIBERADAS', 10, m)
srv.stop()                       # backend cai logo apos o inicio do pulso
log('backend PARADO apos "FICHAS LIBERADAS"')
e.wait_for('Saida desligada', 10, m)
e.wait_for('ACK: HTTP -1', 20, m)
time.sleep(5)
mid = e.text_since(m)
log('ACK falhos durante a queda:', mid.count('ACK: HTTP -1'), '| pulsos:', len(e.pulses()) - n)
srv.start()
log('backend RESTAURADO (mesmo banco)')
r = e.wait_for('ACK: HTTP 200', 30, m)
time.sleep(1)
log('pulsos apos restaurar:', len(e.pulses()) - n, '| backend:', pedido_info(oid7))
log.block('Serial T7', e.text_since(m))
txt = e.text_since(m)
result['T7'] = 'PASS' if (r and len(e.pulses()) == n + 1 and txt.count('FICHAS LIBERADAS') == 1 and api.status(oid7) == 'LIBERADO') else 'FAIL'

# ---------------------------------------------------------------- T6
log('\n===== T6 backend fora do ar: firmware nao cria autorizacao =====')
m = e.mark()
n = len(e.pulses())
srv.stop()
log('backend PARADO (firmware ocioso, sem credito)')
time.sleep(7)
for _ in range(2):
    e.press()
    time.sleep(1.5)
down = e.text_since(m)
log.block('Serial T6 (backend fora)', down)
log('pulsos durante queda:', len(e.pulses()) - n)
srv.start()
time.sleep(8)  # poll volta ao normal
log('backend restaurado; pulsos apos volta sem pedido:', len(e.pulses()) - n)
e.press()
time.sleep(2)
log.block('Serial T6 (apos volta, botao sem credito)', e.text_since(m)[len(down):])
result['T6'] = 'PASS' if (len(e.pulses()) == n and 'POLL: HTTP -1' in down and 'FICHAS' not in e.text_since(m)) else 'FAIL'

# ---------------------------------------------------------------- T10
log('\n===== T10 mesa 01 (Velxio) + mesa 02 (sim_esp32.py) sem mistura =====')
envs = dict(os.environ, PYTHONIOENCODING='utf-8', SINUCA_DB=str(TMP / 'db.sqlite3'), SINUCA_KEYS=str(TMP / 'keys.json'), PORT=PORT)
sim = subprocess.Popen([sys.executable, '-u', 'sim_esp32.py', '--mesa', '02'], cwd=REPO, env=envs,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
time.sleep(3)
m = e.mark()
n = len(e.pulses())
o01 = api.novo_pedido('01')
o02 = api.novo_pedido('02')
api.pagar(o01)
api.pagar(o02)
log('pagos: mesa01', o01[:8], 'mesa02', o02[:8])
time.sleep(6)
log('apos 6 s (sem botao em 01): mesa01', pedido_info(o01), '| mesa02', pedido_info(o02))
before_press = (api.status(o01), api.status(o02))
e.press()
e.wait_for('ACK: HTTP 200', 20, m)
time.sleep(1)
log('apos botao em 01: mesa01', pedido_info(o01), '| mesa02', pedido_info(o02))
sim.terminate()
out = sim.communicate(timeout=10)[0]
log.block('saida sim_esp32 --mesa 02', out)
rows = [(r[0][:8], r[1], r[2][:8], r[3]) for r in cmds()]
log('comandos (id, mesa, pedido, status):', rows)
pulsos02 = out.count('pulso 350 ms')
log('pulsos mesa01 (GPIO26 Velxio):', len(e.pulses()) - n, '| pulsos simulados mesa02:', pulsos02)
log.block('Serial T10', e.text_since(m))
# cada comando pertence a mesa do seu pedido
c = sqlite3.connect(f'file:{TMP / "db.sqlite3"}?mode=ro', uri=True)
cruzado = c.execute('select count(*) from comandos c join pedidos p on p.id=c.pedido_id where c.mesa!=p.mesa').fetchone()[0]
log('comandos cuja mesa difere da mesa do pedido:', cruzado)
result['T10'] = 'PASS' if (before_press == ('PAGO', 'LIBERADO') and api.status(o01) == 'LIBERADO' and api.status(o02) == 'LIBERADO'
                           and len(e.pulses()) - n == 1 and pulsos02 == 1 and cruzado == 0) else 'FAIL'

# ---------------------------------------------------------------- T8
log('\n===== T8 mesa errada =====')
tok01, tok02 = api.token('01'), api.token('02')
cmd01 = [r for r in cmds() if r[1] == '01'][-1][0]
cmd02 = [r for r in cmds() if r[1] == '02'][-1][0]
t8 = {}
casos8 = [
    ('token da mesa 02 em /01/proximo.txt', '01', 'proximo.txt', 'GET', None, tok02),
    ('token da mesa 01 em /02/proximo.txt', '02', 'proximo.txt', 'GET', None, tok01),
    ('sem token em /01/proximo.txt', '01', 'proximo.txt', 'GET', None, 'x'),
    ('token 01 em mesa inexistente /99/proximo.txt', '99', 'proximo.txt', 'GET', None, tok01),
    ('token 02 em /01/confirmar (comando da 01)', '01', 'confirmar', 'POST', {'comando': cmd01, 'duracao_ms': 350}, tok02),
    ('token 01 em /01/confirmar com comando da mesa 02', '01', 'confirmar', 'POST', {'comando': cmd02, 'duracao_ms': 350}, tok01),
    ('token 02 em /02/incerto com comando da mesa 01', '02', 'incerto', 'POST', {'comando': cmd01}, tok02),
]
all_ok = True
for desc, mesa, tail, meth, body, tok in casos8:
    st, resp = api.device(mesa, tail, meth, body, tok=tok)
    log(f'{desc}: HTTP {st} {api.redact(resp)}')
    all_ok &= st in (401, 404)
log('estado dos pedidos intacto: mesa01', api.status(o01), 'mesa02', api.status(o02))
result['T8'] = 'PASS' if all_ok else 'FAIL'
log('\nauditoria (ultimos eventos):', audit_tail(10))

e.close()
srv.stop()
log('\nRESULTADOS casos_a:', json.dumps(result))
json.dump(result, open(os.path.join(os.path.dirname(__file__), 'logs', 'resultado_casos_a.json'), 'w'))
