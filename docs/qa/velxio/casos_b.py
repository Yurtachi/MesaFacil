"""Casos T4, T5 e T9 (reinicios) no ESP32 emulado.

Parte S: Velxio padrao (stop/start pelo WebSocket: flash nova a cada partida, NVS NAO persiste).
Parte P: mesmo worker QEMU do Velxio, copia em /tmp do container que mantem o arquivo de flash (NVS persiste).
"""
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import api
from emu import Emu, EmuPersist
from harness import TMP, Log, Server

log = Log('casos_b')
srv = Server()
srv.start()
fw = (TMP / 'firmware.b64').read_text()
adm = api.Admin()
result = {}


def cmd_status(oid):
    c = sqlite3.connect(f'file:{TMP / "db.sqlite3"}?mode=ro', uri=True)
    return [r[0] for r in c.execute('select status from comandos where pedido_id=? order by criado_em', (oid,))]


def info(oid):
    o = api.pedido(oid)
    return f"pedido={o['status']} comandos={cmd_status(oid)}"


def novo_e_pago():
    oid = api.novo_pedido('01')
    st, r = api.pagar(oid)
    log(f'pedido {oid[:8]}.. criado e pago (demo): HTTP {st} {r.get("status")}')
    return oid


# =================================================================== PARTE S (Velxio padrao)
log('##### PARTE S - Velxio padrao #####')
e = Emu(fw)
e.start()
assert e.wait_for('WiFi conectado', 90)
time.sleep(3)
log('\n===== T4 reinicio (parar/iniciar simulacao) ANTES do acionamento =====')
m = e.mark()
oid4 = novo_e_pago()
assert e.wait_for('Pressione o botao', 15, m)
log('antes do reinicio:', info(oid4))
e.stop()
time.sleep(2)
log('simulacao PARADA. backend:', info(oid4), '(comando ENTREGUE nao foi acionado)')
e.pre = len(e.pulses())
e.serial += '\n=====REINICIO=====\n'
m2 = e.mark()
e.start()
assert e.wait_for('WiFi conectado', 90, m2)
ok = e.wait_for('Pressione o botao', 20, m2)
log('apos reiniciar o firmware voltou a receber o comando (mesmo credito):', ok, '| pulsos desde o reinicio ate aqui:',
    len([p for p in e.pulses() if p[0] > 0]) - 0)
n_antes = len(e.pulses())
time.sleep(5)
log('sem apertar o botao: pulsos =', len(e.pulses()) - n_antes)
e.press()
e.wait_for('ACK: HTTP 200', 20, m2)
time.sleep(1)
log('apos 1 clique:', info(oid4), '| pulsos totais na nova partida:', len(e.pulses()) - n_antes)
log.block('Serial T4 (apos reinicio)', e.text_since(m2))
# segundo clique nao pode gerar outro pulso
e.press()
time.sleep(3)
tot = len(e.pulses()) - n_antes
log('segundo clique: pulsos totais =', tot)
result['T4'] = 'PASS' if (ok and tot == 1 and api.status(oid4) == 'LIBERADO' and cmd_status(oid4) == ['EXECUTADO']) else 'FAIL'

log('\n===== T9 (parte Velxio padrao): NVS apos reiniciar depois de um ciclo COMPLETO =====')
e.stop()
time.sleep(2)
m3 = e.mark()
e.start()
assert e.wait_for('MesaFacil v0.4', 40, m3)
time.sleep(2)
boot = e.text_since(m3)
log.block('boot apos parar/iniciar (ciclo anterior completo)', boot[:900])
stock_nvs_wiped = 'started NOT_FOUND' in boot and 'done NOT_FOUND' in boot
log('Velxio padrao: NVS apagada ao reiniciar (chaves started/done NOT_FOUND):', stock_nvs_wiped)
e.close()
time.sleep(2)

# =================================================================== PARTE P (flash persistente)
log('\n##### PARTE P - flash persistente (copia do worker no container) #####')
p = EmuPersist(fw)
p.start(fresh_flash=True)
assert p.wait_for('WiFi conectado', 90), p.text_since(0)[-300:]
time.sleep(3)

log('\n===== T4b reinicio antes do acionamento (NVS persistente) =====')
m = p.mark()
oid = novo_e_pago()
assert p.wait_for('Pressione o botao', 15, m)
p.stop()
time.sleep(1)
m = p.mark()
p.start()
assert p.wait_for('WiFi conectado', 90, m)
ok = p.wait_for('Pressione o botao', 20, m)
log('apos reinicio: credito reapresentado =', ok, '| NVS vazia? ', 'started NOT_FOUND' in p.text_since(m))
time.sleep(4)
n0 = len(p.pulses())
p.press()
p.wait_for('ACK: HTTP 200', 20, m)
time.sleep(1)
p.press()
time.sleep(3)
log('pulsos apos reinicio+2 cliques:', len(p.pulses()) - n0, '|', info(oid))
log.block('Serial T4b', p.text_since(m))
result['T4b'] = 'PASS' if (ok and len(p.pulses()) - n0 == 1 and api.status(oid) == 'LIBERADO') else 'FAIL'

log('\n===== T9 (flash persistente): chaves started/done sobrevivem =====')
p.stop()
time.sleep(1)
m = p.mark()
p.start()
assert p.wait_for('MesaFacil v0.4', 60, m)
time.sleep(2)
boot = p.text_since(m)
log.block('boot apos ciclo completo, flash preservada', boot[:700])
nvs_ok = 'NOT_FOUND' not in boot
log('chaves started/done lidas sem NOT_FOUND:', nvs_ok)
assert p.wait_for('WiFi conectado', 60, m)
time.sleep(5)
p.stop()

log('\n===== T9b ACK perdido + reinicio: ramo "done" =====')
m = p.mark()
p.start()
assert p.wait_for('WiFi conectado', 90, m)
time.sleep(3)
oid9 = novo_e_pago()
assert p.wait_for('Pressione o botao', 15, m)
srv.stop()      # backend fora ANTES do clique: o ACK nao tem como chegar
log('backend PARADO antes do clique (credito ja entregue ao firmware)')
p.press(0.3)
p.wait_for('FICHAS LIBERADAS', 10, m)
p.wait_for('Saida desligada', 10, m)
time.sleep(5)
log('firmware persistiu "done" (pulso feito) e nao consegue enviar ACK; pulsos nesta partida:', len(p.pulses()))
log.block('Serial T9b antes do reinicio', p.text_since(m))
p.stop()
log('ESP32 reiniciado (parada limpa) com o backend ainda fora')
srv.start()
m = p.mark()
p.start()
n_pre = len(p.pulses())
assert p.wait_for('WiFi conectado', 90, m)
r = p.wait_for('ACK: HTTP 200', 30, m)
time.sleep(2)
p.press()   # botao apos o reinicio: tambem nao deve acionar
time.sleep(3)
log('apos reinicio: pulsos novos =', len(p.pulses()) - n_pre, '|', info(oid9))
log.block('Serial T9b (apos o reinicio)', p.text_since(m))
result['T9'] = 'PASS' if (nvs_ok and r and 'Reenviando ACK sem novo pulso' in p.text_since(m) and len(p.pulses()) == n_pre
                          and api.status(oid9) == 'LIBERADO') else 'FAIL'
result['T9_velxio_padrao_nvs_apagada'] = stock_nvs_wiped

log('\n===== T5 reinicio DURANTE o pulso de 350 ms =====')
p.stop()
m = p.mark()
p.start()
assert p.wait_for('WiFi conectado', 90, m)
time.sleep(3)
oid5 = novo_e_pago()
assert p.wait_for('Pressione o botao', 15, m)
n_pre = len(p.pulses())
p.crash_armed = True
p.press(0.3)
time.sleep(2)
log('QEMU morto com SIGKILL assim que GPIO26 foi a nivel BAIXO (t=%.2fs); processo vivo? %s' % (p.crashed_at or -1, bool(p.proc and p.proc.poll() is None)))
sr = p.text_since(m)
log.block('Serial ate a queda', sr)
log('pulso visto antes da queda:', p.pulses()[n_pre:], '| "Saida desligada" impresso?', 'Saida desligada' in sr)
log('backend logo apos a queda:', info(oid5))
p.stop()
m = p.mark()
p.start()
n_pre = len(p.pulses())
assert p.wait_for('WiFi conectado', 90, m)
inc = p.wait_for('ESTADO INCERTO', 30, m)
time.sleep(4)
log('firmware apos reiniciar: ESTADO INCERTO impresso =', inc)
log('backend: ', info(oid5))
for _ in range(3):
    p.press()
    time.sleep(1.5)
time.sleep(6)
log('pulsos apos o reinicio (3 cliques + 10 s de polling):', len(p.pulses()) - n_pre)
st, issues = 200, api.Admin().resumo()
log('admin /api/admin/resumo pendencias EM_ANALISE:', [(i['id'][:8], i['mesa'], i['status'], i['comando']) for i in issues.get('pendencias', issues.get('issues', []))] if isinstance(issues, dict) else issues)
log('chaves do resumo:', list(issues.keys()) if isinstance(issues, dict) else '')
log.block('Serial T5 apos reinicio', p.text_since(m))
t5_status = (api.status(oid5), cmd_status(oid5))
result['T5'] = 'PASS' if (inc and len(p.pulses()) == n_pre and t5_status == ('EM_ANALISE', ['INCERTO'])) else 'FAIL'
log('T5 estado final:', t5_status)

log('\n--- T5 epilogo: operador resolve (reabrir) -> novo credito legitimo ---')
st, r = api.Admin().post(f'/api/admin/pedidos/{oid5}/resolver', {'acao': 'reabrir', 'motivo': 'QA Velxio: conferido, reabrir credito'})
log('POST /api/admin/pedidos/<id>/resolver reabrir -> HTTP', st, r)
m = p.mark()
n_pre = len(p.pulses())
okc = p.wait_for('Pressione o botao', 15, m)
p.press()
okk = p.wait_for('ACK: HTTP 200', 20, m)
time.sleep(1)
log('novo comando recebido:', okc, '| pulsos:', len(p.pulses()) - n_pre, '|', info(oid5))
result['T5_epilogo_reabrir'] = 'PASS' if (okc and okk and len(p.pulses()) - n_pre == 1 and api.status(oid5) == 'LIBERADO') else 'FAIL'

p.close()
srv.stop()
log('\nRESULTADOS casos_b:', json.dumps(result))
json.dump(result, open(os.path.join(os.path.dirname(__file__), 'logs', 'resultado_casos_b.json'), 'w'))
