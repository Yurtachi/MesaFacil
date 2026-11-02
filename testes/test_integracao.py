"""Testes automáticos do protótipo: não envolvem pagamentos nem hardware real."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def call(base, path, payload=None, token=None, expected=200):
    headers = {}
    if payload is not None:
        headers['Content-Type'] = 'application/json'
    if token:
        headers['Authorization'] = f'Bearer {token}'
    req = Request(base + path, headers=headers, data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urlopen(req, timeout=3) as response:
            status = response.status
            raw = response.read()
    except HTTPError as exc:
        status = exc.code
        raw = exc.read()
    assert status == expected, f'{path}: esperado {expected}, recebido {status}: {raw}'
    return json.loads(raw) if raw else {}


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        cls.port = sock.getsockname()[1]
        sock.close()
        cls.base = f'http://127.0.0.1:{cls.port}'
        env = os.environ.copy()
        env['PORT'] = str(cls.port)
        env['HOST'] = '127.0.0.1'
        env['SINUCA_DB'] = str(Path(cls.temp.name) / 'demo.sqlite3')
        env['SINUCA_KEYS'] = str(Path(cls.temp.name) / 'keys.json')
        cls.proc = subprocess.Popen([sys.executable, 'app.py'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        for _ in range(100):
            try:
                call(cls.base, '/api/mesas')
                break
            except (ConnectionError, URLError):
                time.sleep(.05)
        else:
            raise RuntimeError('Servidor não iniciou')
        cls.keys = json.loads(Path(env['SINUCA_KEYS']).read_text())

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.temp.cleanup()

    def test_10_mesas(self):
        state = call(self.base, '/api/mesas')
        self.assertEqual(len(state['mesas']), 10)
        self.assertEqual([m['id'] for m in state['mesas']], [f'{x:02}' for x in range(1,11)])

    def test_pagamento_e_confirmacao_idempotente(self):
        order = call(self.base, '/api/pedidos', {'mesa': '03'}, expected=201)['pedido']
        call(self.base, '/api/pedidos', {'mesa': '03'}, expected=409)
        call(self.base, '/api/demo/pagar', {'pedido': order})
        call(self.base, '/api/demo/pagar', {'pedido': order})
        cmd = call(self.base, '/api/dispositivos/03/proximo', token=self.keys['03'])['comando']
        self.assertEqual(cmd['tipo'], 'PULSO')
        self.assertEqual(cmd['pedido'], order)
        self.assertEqual(call(self.base, '/api/dispositivos/03/proximo', token=self.keys['03'])['comando']['id'], cmd['id'])
        call(self.base, '/api/dispositivos/04/proximo', token=self.keys['03'], expected=401)
        call(self.base, '/api/dispositivos/03/confirmar', {'comando': cmd['id']}, token=self.keys['03'])
        call(self.base, '/api/dispositivos/03/confirmar', {'comando': cmd['id']}, token=self.keys['03'])
        self.assertEqual(call(self.base, '/api/dispositivos/03/proximo', token=self.keys['03'])['comando'], None)
        self.assertEqual(call(self.base, '/api/pedidos/' + order)['status'], 'LIBERADO')
        new = call(self.base, '/api/pedidos', {'mesa': '03'}, expected=201)
        self.assertNotEqual(new['pedido'], order)

    def test_cross_table_and_cancel(self):
        order = call(self.base, '/api/pedidos', {'mesa': '08'}, expected=201)['pedido']
        call(self.base, '/api/pedidos/cancelar', {'pedido': order})
        self.assertEqual(call(self.base, '/api/pedidos/'+order)['status'], 'CANCELADO')
        order = call(self.base, '/api/pedidos', {'mesa': '08'}, expected=201)['pedido']
        call(self.base, '/api/demo/pagar', {'pedido': order})
        cmd = call(self.base, '/api/dispositivos/08/proximo', token=self.keys['08'])['comando']['id']
        call(self.base, '/api/dispositivos/09/confirmar', {'comando': cmd}, token=self.keys['09'], expected=404)
        self.assertEqual(call(self.base, '/api/pedidos/'+order)['status'], 'PAGO')

    def test_qr_png(self):
        with urlopen(self.base + '/qr/01.png', timeout=3) as r:
            self.assertEqual(r.headers.get_content_type(), 'image/png')
            self.assertEqual(r.read(8), b'\x89PNG\r\n\x1a\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
