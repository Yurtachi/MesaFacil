"""POC local de mesas de sinuca: pagamentos FICTÍCIOS e acionamento via polling.
Não contém integração financeira real, segurança ou eletrônica validada para produção.
"""
import json
import os
import re
import secrets
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from io import BytesIO

BASE = Path(__file__).resolve().parent
DB = Path(os.getenv('SINUCA_DB', str(BASE / 'sinuca_demo.sqlite3')))
KEYS = Path(os.getenv('SINUCA_KEYS', str(BASE / 'device_keys.json')))
PORT = int(os.getenv('PORT', '8765'))
HOST = os.getenv('HOST', '127.0.0.1')
PUBLIC_BASE_URL = os.getenv('PUBLIC_BASE_URL', f'http://127.0.0.1:{PORT}').rstrip('/')
LOCK = threading.RLock()
TABLES = [f'{i:02}' for i in range(1, 11)]
PRICE_CENTS = 500  # Somente preço ilustrativo; 1 pagamento = 1 liberação
TOKENS = {}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


@contextmanager
def connect():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def init():
    global TOKENS
    DB.parent.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS pedidos (
            id TEXT PRIMARY KEY,
            mesa TEXT NOT NULL,
            valor_centavos INTEGER NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('PENDENTE','PAGO','LIBERADO','CANCELADO')),
            criado_em TEXT NOT NULL,
            pago_em TEXT,
            liberado_em TEXT
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uma_cobranca_aberta_por_mesa
        ON pedidos(mesa) WHERE status IN ('PENDENTE','PAGO');
        CREATE TABLE IF NOT EXISTS comandos (
            id TEXT PRIMARY KEY,
            pedido_id TEXT NOT NULL UNIQUE REFERENCES pedidos(id),
            mesa TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('PENDENTE','EXECUTADO')),
            criado_em TEXT NOT NULL,
            executado_em TEXT
        );
        CREATE TABLE IF NOT EXISTS eventos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mesa TEXT NOT NULL,
            tipo TEXT NOT NULL,
            detalhe TEXT NOT NULL,
            criado_em TEXT NOT NULL
        );
        ''')
    if KEYS.exists():
        TOKENS = json.loads(KEYS.read_text(encoding='utf-8'))
        if set(TOKENS) != set(TABLES):
            raise RuntimeError('Arquivo de tokens incompleto. Recupere os tokens antes de continuar.')
    else:
        TOKENS = {mesa: secrets.token_urlsafe(32) for mesa in TABLES}
        KEYS.write_text(json.dumps(TOKENS, indent=2), encoding='utf-8')
        try:
            os.chmod(KEYS, 0o600)
        except OSError:
            pass


def record(conn, mesa, tipo, detalhe):
    conn.execute('INSERT INTO eventos(mesa,tipo,detalhe,criado_em) VALUES(?,?,?,?)',
                 (mesa, tipo, detalhe, now()))


def json_body(handler):
    size = int(handler.headers.get('Content-Length', '0'))
    if size <= 0 or size > 16_384:
        raise ValueError('Corpo de requisição inválido')
    return json.loads(handler.rfile.read(size).decode('utf-8'))


def create_order(mesa):
    if mesa not in TABLES:
        raise ValueError('Mesa não encontrada')
    with LOCK, connect() as conn:
        existing = conn.execute('SELECT id FROM pedidos WHERE mesa=? AND status IN (\'PENDENTE\',\'PAGO\')', (mesa,)).fetchone()
        if existing:
            raise RuntimeError('Já existe uma compra aguardando nesta mesa')
        oid = str(uuid.uuid4())
        conn.execute('INSERT INTO pedidos(id,mesa,valor_centavos,status,criado_em) VALUES(?,?,?,?,?)',
                     (oid, mesa, PRICE_CENTS, 'PENDENTE', now()))
        record(conn, mesa, 'PEDIDO_CRIADO', oid)
        return oid


def pay_demo(oid):
    with LOCK, connect() as conn:
        order = conn.execute('SELECT * FROM pedidos WHERE id=?', (oid,)).fetchone()
        if not order:
            raise LookupError('Pedido inexistente')
        if order['status'] != 'PENDENTE':
            # Duas notificações do pagamento não geram duas liberações
            return order['status']
        conn.execute("UPDATE pedidos SET status='PAGO', pago_em=? WHERE id=?", (now(), oid))
        conn.execute('INSERT INTO comandos(id,pedido_id,mesa,status,criado_em) VALUES(?,?,?,?,?)',
                     (str(uuid.uuid4()), oid, order['mesa'], 'PENDENTE', now()))
        record(conn, order['mesa'], 'PAGAMENTO_SIMULADO', oid)
        return 'PAGO'


def acknowledge(mesa, cmd_id):
    with LOCK, connect() as conn:
        row = conn.execute('SELECT * FROM comandos WHERE id=? AND mesa=?', (cmd_id, mesa)).fetchone()
        if not row:
            raise LookupError('Comando não pertence a esta mesa')
        if row['status'] == 'EXECUTADO':
            return 'LIBERADO'
        conn.execute("UPDATE comandos SET status='EXECUTADO', executado_em=? WHERE id=?", (now(), cmd_id))
        conn.execute("UPDATE pedidos SET status='LIBERADO', liberado_em=? WHERE id=? AND status='PAGO'",
                     (now(), row['pedido_id']))
        record(conn, mesa, 'PULSO_CONFIRMADO_PELO_DISPOSITIVO', cmd_id)
        return 'LIBERADO'


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f'[{self.log_date_time_string()}] {fmt % args}')

    def send(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def file(self, path, content_type):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def authorized(self, mesa):
        supplied = self.headers.get('Authorization', '')
        token = TOKENS.get(mesa, '')
        return bool(token) and secrets.compare_digest(supplied, f'Bearer {token}')

    def send_text(self, code, value):
        data = (value + "\n").encode("ascii")
        self.send_response(code)
        self.send_header('Content-Type', 'text/plain; charset=ascii')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/health':
            return self.send(200, {'status': 'ok', 'demo': True})
        if path in ['/', '/admin', '/placas'] or re.fullmatch(r'/mesa/\d\d', path):
            return self.file(BASE / 'web' / 'index.html', 'text/html; charset=utf-8')
        if path == '/style.css':
            return self.file(BASE / 'web' / 'style.css', 'text/css; charset=utf-8')
        if path == '/app.js':
            return self.file(BASE / 'web' / 'app.js', 'text/javascript; charset=utf-8')
        match = re.fullmatch(r'/qr/(\d\d)\.png', path)
        if match and match.group(1) in TABLES:
            import qrcode
            qr = qrcode.make(f'{PUBLIC_BASE_URL}/mesa/{match.group(1)}')
            out = BytesIO()
            qr.save(out, format='PNG')
            raw = out.getvalue()
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            return self.wfile.write(raw)
        match = re.fullmatch(r'/api/pedidos/([\da-f-]{36})', path)
        if match:
            with LOCK, connect() as conn:
                row = conn.execute('SELECT * FROM pedidos WHERE id=?', (match.group(1),)).fetchone()
            return self.send(200, dict(row)) if row else self.send(404, {'erro': 'Pedido não encontrado'})
        if path == '/api/mesas':
            with LOCK, connect() as conn:
                rows = conn.execute('''SELECT mesa, status, id FROM pedidos
                                       WHERE status IN ('PENDENTE','PAGO')''').fetchall()
                recent = conn.execute('SELECT * FROM pedidos ORDER BY criado_em DESC LIMIT 30').fetchall()
                events = conn.execute('SELECT * FROM eventos ORDER BY id DESC LIMIT 15').fetchall()
            reserved = {r['mesa']: {'status': r['status'], 'pedido': r['id']} for r in rows}
            return self.send(200, {'mesas': [{'id': m, **reserved.get(m, {'status': 'DISPONIVEL', 'pedido': None})} for m in TABLES],
                                   'pedidos': [dict(r) for r in recent], 'eventos': [dict(r) for r in events],
                                   'preco_centavos': PRICE_CENTS, 'base_url': PUBLIC_BASE_URL})
        # Formato texto simples para firmware Arduino sem dependência JSON adicional.
        match = re.fullmatch(r'/api/dispositivos/(\d\d)/proximo.txt', path)
        if match:
            mesa = match.group(1)
            if not self.authorized(mesa):
                return self.send(401, {'erro': 'Credencial inválida'})
            with LOCK, connect() as conn:
                cmd = conn.execute("SELECT id FROM comandos WHERE mesa=? AND status='PENDENTE' ORDER BY criado_em LIMIT 1", (mesa,)).fetchone()
            return self.send_text(200, cmd['id'] if cmd else 'NONE')
        match = re.fullmatch(r'/api/dispositivos/(\d\d)/proximo', path)
        if match:
            mesa = match.group(1)
            if not self.authorized(mesa):
                return self.send(401, {'erro': 'Credencial inválida'})
            with LOCK, connect() as conn:
                cmd = conn.execute("SELECT id, pedido_id FROM comandos WHERE mesa=? AND status='PENDENTE' ORDER BY criado_em LIMIT 1", (mesa,)).fetchone()
            return self.send(200, {'comando': ({'id': cmd['id'], 'tipo': 'PULSO', 'pedido': cmd['pedido_id']} if cmd else None)})
        return self.send(404, {'erro': 'Rota não encontrada'})

    def do_POST(self):
        path = urlparse(self.path).path
        # Endpoints públicos para simulação LOCAL, não são um produto de pagamento.
        try:
            payload = json_body(self)
        except (ValueError, json.JSONDecodeError):
            return self.send(400, {'erro': 'JSON inválido'})
        if path == '/api/pedidos':
            try:
                order_id = create_order(str(payload.get('mesa', '')))
            except ValueError as exc:
                return self.send(400, {'erro': str(exc)})
            except RuntimeError as exc:
                return self.send(409, {'erro': str(exc)})
            return self.send(201, {'pedido': order_id, 'status': 'PENDENTE', 'preco_centavos': PRICE_CENTS})
        if path == '/api/demo/pagar':
            if self.client_address[0] not in ('127.0.0.1', '::1'):
                return self.send(403, {'erro': 'Aprovação fictícia permitida apenas no PC local'})
            try:
                status = pay_demo(str(payload.get('pedido', '')))
            except LookupError as exc:
                return self.send(404, {'erro': str(exc)})
            return self.send(200, {'status': status, 'aviso': 'PAGAMENTO FICTÍCIO — NÃO HOUVE PIX REAL'})
        match = re.fullmatch(r'/api/dispositivos/(\d\d)/confirmar', path)
        if match:
            mesa = match.group(1)
            if not self.authorized(mesa):
                return self.send(401, {'erro': 'Credencial inválida'})
            try:
                status = acknowledge(mesa, str(payload.get('comando', '')))
            except LookupError as exc:
                return self.send(404, {'erro': str(exc)})
            return self.send(200, {'status': status})
        if path == '/api/pedidos/cancelar':
            if self.client_address[0] not in ('127.0.0.1', '::1'):
                return self.send(403, {'erro': 'Cancelamento de demonstração apenas no PC local'})
            oid = str(payload.get('pedido', ''))
            with LOCK, connect() as conn:
                row = conn.execute('SELECT mesa,status FROM pedidos WHERE id=?', (oid,)).fetchone()
                if not row:
                    return self.send(404, {'erro': 'Pedido não encontrado'})
                if row['status'] != 'PENDENTE':
                    return self.send(409, {'erro': 'Não é possível cancelar após pagamento'})
                conn.execute("UPDATE pedidos SET status='CANCELADO' WHERE id=?", (oid,))
                record(conn, row['mesa'], 'PEDIDO_CANCELADO', oid)
            return self.send(200, {'status': 'CANCELADO'})
        return self.send(404, {'erro': 'Rota não encontrada'})


def serve():
    init()
    print(f'\nSINUCA POC — APENAS TESTES, SEM PAGAMENTOS REAIS\nPainel: http://127.0.0.1:{PORT}/admin\nQRs: http://127.0.0.1:{PORT}/placas')
    print(f'Tokens de teste: {KEYS}\n')
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        print('\nServidor interrompido')
    finally:
        server.server_close()


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3 and sys.argv[1] == '--token':
        init()
        print(TOKENS[sys.argv[2]])
    else:
        serve()
