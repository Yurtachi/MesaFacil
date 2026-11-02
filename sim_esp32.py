"""Simulador SOFTWARE de 10 controladores. Não é emulação elétrica nem firmware real."""
import argparse
import json
import threading
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from app import init, TOKENS, TABLES, PORT
import app


def api(url, token, data=None):
    headers = {'Authorization': f'Bearer {token}'}
    if data is not None:
        headers['Content-Type'] = 'application/json'
    request = Request(url, headers=headers, data=json.dumps(data).encode() if data is not None else None)
    with urlopen(request, timeout=3) as resp:
        return json.loads(resp.read().decode())


def loop(mesa):
    base = f'http://127.0.0.1:{app.PORT}/api/dispositivos/{mesa}'
    token = app.TOKENS[mesa]
    last_seen = ''
    while True:
        try:
            cmd = api(base + '/proximo', token)['comando']
            if cmd and cmd['id'] != last_seen:
                last_seen = cmd['id']
                print(f'[ESP32 VIRTUAL mesa {mesa}] comando {cmd["id"][:8]} recebido, simulando botão e pulso...', flush=True)
                time.sleep(0.7)
                print(f'[ESP32 VIRTUAL mesa {mesa}] RELÉ ATIVO por 350ms e DESLIGADO', flush=True)
                time.sleep(0.35)
                api(base + '/confirmar', token, {'comando': cmd['id']})
                print(f'[ESP32 VIRTUAL mesa {mesa}] confirmação enviada!', flush=True)
            if not cmd:
                last_seen = ''
        except (URLError, OSError, ValueError, KeyError) as exc:
            print(f'[mesa {mesa}] aviso de conexão: {exc}', flush=True)
        time.sleep(1)


def start(mesas):
    app.init()
    for mesa in mesas:
        thread = threading.Thread(target=loop, args=(mesa,), daemon=True, name=f'esp32-{mesa}')
        thread.start()
    print(f'Simuladores de ESP32 ativos: {", ".join(mesas)}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mesa', default='todas', help='01..10 ou todas')
    args = parser.parse_args()
    mesas = app.TABLES if args.mesa == 'todas' else [args.mesa]
    if not all(m in app.TABLES for m in mesas):
        parser.error('Mesa inválida')
    start(mesas)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print('Encerrado')
