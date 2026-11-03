"""Helpers HTTP do backend MesaFacil (127.0.0.1) usados pelos casos de teste. Tokens nunca sao impressos."""
import json
import os
import re
import urllib.error
import urllib.request

BASE = os.environ.get('MF_BASE', 'http://127.0.0.1:8777')
KEYS = os.environ['SINUCA_KEYS']
ADMIN_PW = os.environ.get('ADMIN_PASSWORD', 'qa-velxio-pass-123')


def redact(text):
    return re.sub(r'[\w-]{43}', '<TOKEN>', str(text))


def req(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    h = {'Content-Type': 'application/json'} if body is not None else {}
    h.update(headers or {})
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw.startswith(('{', '[')) else raw.strip())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        return e.code, (json.loads(raw) if raw.startswith('{') else raw.strip())


def token(mesa):
    return json.load(open(KEYS, encoding='utf-8-sig'))[mesa]


def novo_pedido(mesa='01'):
    st, o = req('POST', '/api/pedidos', {'mesa': mesa})
    assert st == 201, (st, o)
    return o['pedido']


def pagar(oid):
    return req('POST', '/api/demo/pagar', {'pedido': oid, 'resultado': 'aprovado'})


def pedido(oid):
    st, o = req('GET', f'/api/pedidos/{oid}')
    return o


def status(oid):
    return pedido(oid).get('status')


def device(mesa, tail, method='GET', body=None, tok=None):
    return req(method, f'/api/dispositivos/{mesa}/{tail}', body, {'Authorization': 'Bearer ' + (tok or token(mesa))})


class Admin:
    def __init__(self):
        r = urllib.request.Request(BASE + '/api/admin/login', data=json.dumps({'senha': ADMIN_PW}).encode(),
                                   headers={'Content-Type': 'application/json'}, method='POST')
        resp = urllib.request.urlopen(r, timeout=10)
        self.cookie = resp.headers['Set-Cookie'].split(';')[0]
        self.csrf = json.loads(resp.read())['csrf']

    def get(self, path):
        r = urllib.request.Request(BASE + path, headers={'Cookie': self.cookie})
        return json.loads(urllib.request.urlopen(r, timeout=10).read())

    def resumo(self):
        return self.get('/api/admin/resumo')

    def auditoria(self):
        return self.get('/api/admin/auditoria')['auditoria']

    def post(self, path, body):
        r = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method='POST',
                                   headers={'Cookie': self.cookie, 'X-CSRF-Token': self.csrf, 'Content-Type': 'application/json'})
        try:
            resp = urllib.request.urlopen(r, timeout=10)
            return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as ex:
            return ex.code, ex.read().decode()
