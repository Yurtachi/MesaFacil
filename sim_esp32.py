"""Simulador SOFTWARE de controladores (não é emulação elétrica nem firmware real).

Segue o protocolo do firmware v0.4: nunca repete pulso de comando já iniciado (estado em arquivo, como a NVS),
reenvia o ACK sem novo pulso e reporta estado incerto.
"""
import argparse
import json
import threading
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

from mesafacil.config import BASE, settings


def api(url, token, data=None):
    headers = {'Authorization': f'Bearer {token}', 'X-Firmware': 'sim-0.4'}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    req = Request(url, headers=headers, data=json.dumps(data).encode() if data is not None else None)
    with urlopen(req, timeout=3) as resp:
        return resp.read().decode().strip()


def loop(mesa, token, state_dir):
    base = f'http://127.0.0.1:{settings.port}/api/dispositivos/{mesa}'
    nvs = state_dir / f'nvs_{mesa}.json'
    st = json.loads(nvs.read_text()) if nvs.exists() else {'started': '', 'done': ''}

    def save():
        nvs.write_text(json.dumps(st))

    while True:
        try:
            cmd = api(base + '/proximo.txt', token)
            if cmd != 'NONE':
                if cmd == st['done']:
                    api(base + '/confirmar', token, {'comando': cmd, 'duracao_ms': 350})  # só reenvia o ACK
                elif cmd == st['started']:
                    api(base + '/incerto', token, {'comando': cmd})
                else:
                    time.sleep(0.7)  # "cliente aperta o botão"
                    st['started'] = cmd
                    save()
                    print(f'[sim {mesa}] pulso 350 ms (simulado) cmd {cmd[:8]}', flush=True)
                    time.sleep(0.35)
                    st['done'] = cmd
                    save()
                    api(base + '/confirmar', token, {'comando': cmd, 'duracao_ms': 350})
        except (URLError, OSError, ValueError) as exc:
            print(f'[sim {mesa}] conexão: {exc}', flush=True)
        time.sleep(1)


def start(mesas, state_dir=None):
    keys = json.loads(settings.keys.read_text(encoding='utf-8'))
    state_dir = state_dir or BASE / 'privado'
    state_dir.mkdir(exist_ok=True)
    for mesa in mesas:
        threading.Thread(target=loop, args=(mesa, keys[mesa], state_dir), daemon=True, name=f'sim-{mesa}').start()
    print(f'Simuladores de controlador ativos: {", ".join(mesas)}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mesa', default='todas', help='NN ou "todas" (mesas do arquivo de chaves)')
    args = parser.parse_args()
    keys = json.loads(settings.keys.read_text(encoding='utf-8'))
    start(sorted(keys) if args.mesa == 'todas' else [args.mesa])
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print('Encerrado')
