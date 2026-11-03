"""T8b: firmware REAL da mesa 01 compilado com o token da mesa 02 (credencial trocada) nao recebe credito da mesa 01."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import api
from emu import Emu
from harness import TMP, Log, Server

log = Log('caso_t8b')
srv = Server()
srv.start()
e = Emu((TMP / 'firmware_tokenerrado.b64').read_text())
e.start()
assert e.wait_for('WiFi conectado', 90)
time.sleep(3)
oid = api.novo_pedido('01')
st, r = api.pagar(oid)
log(f'pedido mesa 01 pago: HTTP {st} {r.get("status")}')
time.sleep(8)
for _ in range(2):
    e.press()
    time.sleep(1.5)
o = api.pedido(oid)
log('pedido apos 8 s + 2 cliques:', o['status'], '| comando:', o['comando'], '| etapa:', o['etapa'])
log.block('Serial (firmware com token da mesa 02)', e.text_since(0)[e.text_since(0).find('MesaFacil'):])
log('pulsos em GPIO26:', len(e.pulses()))
res = 'PASS' if (len(e.pulses()) == 0 and 'POLL: HTTP 401' in e.text_since(0) and o['comando'] == 'PENDENTE') else 'FAIL'
log('T8b', res)
e.close()
# limpeza: cancela a pendencia via admin (EM_ANALISE nao se aplica: comando PENDENTE nunca entregue)
srv.stop()
