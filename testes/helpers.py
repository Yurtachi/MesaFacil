"""Utilitarios de teste: servidor em subprocesso, cliente HTTP com cookies e ESP32 simulado em software.

ATENCAO: FakeDevice e SOFTWARE. Nenhum teste aqui valida eletronica, rele ou a mesa fisica.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ADMIN_PASSWORD = 'senha-de-teste-123'
WEBHOOK_SECRET = 'segredo-webhook-teste'


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, **env):
        self.tmp = tempfile.TemporaryDirectory()
        self.port = free_port()
        self.url = f'http://127.0.0.1:{self.port}'
        self.env = os.environ.copy()
        self.env.update(HOST='127.0.0.1', PORT=str(self.port), ADMIN_PASSWORD=ADMIN_PASSWORD,
                        SINUCA_DB=str(Path(self.tmp.name) / 'db.sqlite3'),
                        SINUCA_KEYS=str(Path(self.tmp.name) / 'keys.json'),
                        PAYMENT_MODE='demo', RATE_ORDERS_PER_MIN='1000', WEBHOOK_SECRET=WEBHOOK_SECRET, PYTHONIOENCODING='utf-8')
        self.env.update({k: str(v) for k, v in env.items()})
        self.proc = None

    def start(self):
        self.proc = subprocess.Popen([sys.executable, 'app.py'], cwd=ROOT, env=self.env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(200):
            try:
                with urlopen(self.url + '/api/health', timeout=.5):
                    return self
            except (URLError, OSError):
                time.sleep(.05)
        raise RuntimeError('servidor nao subiu')

    def stop(self):
        if self.proc:
            self.proc.terminate()
            self.proc.wait(timeout=10)
            self.proc = None

    def close(self):
        self.stop()
        self.tmp.cleanup()

    @property
    def keys(self):
        return json.loads(Path(self.env['SINUCA_KEYS']).read_text(encoding='utf-8'))


class Client:
    """Cliente HTTP minimo. Mantem cookie de sessao; devolve (status, corpo-json-ou-texto)."""

    def __init__(self, server, token=None):
        self.server, self.token, self.cookie, self.csrf = server, token, None, None

    def call(self, method, path, body=None, raw=None, headers=None, csrf=True):
        h = dict(headers or {})
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            h['Content-Type'] = 'application/json'
        if self.token:
            h['Authorization'] = 'Bearer ' + self.token
        if self.cookie:
            h['Cookie'] = self.cookie
        if self.csrf and csrf and method == 'POST':
            h['X-CSRF-Token'] = self.csrf
        req = Request(self.server.url + path, data=data, headers=h, method=method)
        try:
            resp = urlopen(req, timeout=10)
        except HTTPError as e:
            resp = e
        with resp:
            raw_out = resp.read()
            self.last_headers = resp.headers
            sc = resp.headers.get('Set-Cookie')
            if sc and sc.startswith('mf_admin=') and 'Max-Age=0' not in sc:
                self.cookie = sc.split(';')[0]
            ctype = resp.headers.get('Content-Type', '')
            if 'json' in ctype:
                return resp.status, json.loads(raw_out)
            if ctype.startswith('text/plain'):
                return resp.status, raw_out.decode().strip()
            return resp.status, raw_out

    def get(self, path, **kw):
        return self.call('GET', path, **kw)

    def post(self, path, body=None, **kw):
        return self.call('POST', path, body if body is not None or 'raw' in kw else {}, **kw)

    def login(self, password=ADMIN_PASSWORD):
        st, js = self.post('/api/admin/login', {'senha': password})
        if st == 200:
            self.csrf = js['csrf']
        return st, js


class FakeDevice:
    """ESP32 em software: NVS (started/done), pulso contado, falhas injetaveis."""

    def __init__(self, server, mesa, token=None):
        self.mesa = mesa
        self.c = Client(server, token or server.keys[mesa])
        self.started = ''
        self.done = ''
        self.pulses = 0
        self.base = f'/api/dispositivos/{mesa}'

    def reboot(self):
        """Perde RAM; NVS (started/done) permanece."""

    def poll(self):
        st, cmd = self.c.get(self.base + '/proximo.txt', headers={'X-Firmware': 'fake-0.4'})
        return cmd if st == 200 and cmd != 'NONE' else None

    def press_button(self, cmd, ack=True, crash_after_pulse=False, crash_before_pulse=False):
        """Reproduz a logica do firmware: nunca repete pulso de comando ja iniciado."""
        if cmd == self.done:
            return self.ack(cmd) if ack else None
        if cmd == self.started:
            self.c.post(self.base + '/incerto', {'comando': cmd})
            return 'INCERTO'
        self.started = cmd
        if crash_before_pulse:
            return 'CRASH'
        self.pulses += 1
        if crash_after_pulse:
            return 'CRASH'
        self.done = cmd
        return self.ack(cmd) if ack else None

    def ack(self, cmd):
        st, js = self.c.post(self.base + '/confirmar', {'comando': cmd, 'duracao_ms': 350})
        return js.get('status') if st == 200 else st

    def cycle(self):
        """poll + botao + ack. Devolve estado final reportado."""
        cmd = self.poll()
        return self.press_button(cmd) if cmd else None
