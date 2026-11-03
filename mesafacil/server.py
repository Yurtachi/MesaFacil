"""Servidor HTTP (biblioteca padrao): paginas, API publica, API do dispositivo e API admin."""
import hashlib
import json
import re
import sys
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse

from . import db, security, service
from .config import BASE, settings
from .service import ServiceError

WEB = BASE / 'web'
UUID = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
MESA = r'(\d{2,4})'
COOKIE = 'mf_admin'
MAX_BODY = 16_384
TYPES = {'.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8',
         '.js': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.woff2': 'font/woff2', '.txt': 'text/plain; charset=utf-8'}
PAGES = {'/': 'index.html', '/admin': 'admin.html', '/admin/placas': 'placas.html'}
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; "
       "frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'")
LOCAL = ('127.0.0.1', '::1')


class Ctx:
    def __init__(self, handler, match, body):
        self.h, self.m, self.body = handler, match, body
        self.ip = handler.client_ip()


def route_table():
    """(metodo, regex, funcao, tipo) onde tipo in public|device|admin."""
    R = []

    def add(method, pattern, kind):
        def deco(fn):
            R.append((method, re.compile(pattern + r'$'), fn, kind))
            return fn
        return deco
    return R, add


ROUTES, add = route_table()


# ------------------------------------------------------------------ publico
@add('GET', r'/api/health', 'public')
def r_health(c):
    return 200, service.health()


@add('GET', r'/api/config', 'public')
def r_config(c):
    return 200, service.public_config()


@add('GET', r'/api/mesas', 'public')
def r_tables(c):
    return 200, {'mesas': service.public_tables()}


@add('GET', rf'/api/mesas/{MESA}', 'public')
def r_table(c):
    t = service.public_table(c.m.group(1))
    t['demo_pagamento_permitido'] = demo_allowed(c)
    return 200, t


def demo_allowed(c):
    return settings.demo and (settings.demo_remote_pay or c.ip in LOCAL)


@add('POST', r'/api/pedidos', 'public')
def r_create(c):
    if not security.limiter.allow('pedido', c.ip, settings.rate_orders, 60):
        return 429, {'erro': 'Muitas tentativas. Aguarde um instante.'}
    return 201, service.create_order(str(c.body.get('mesa', '')))


@add('POST', r'/api/pedidos/cancelar', 'public')
def r_cancel(c):
    service.cancel_order(str(c.body.get('pedido', '')))
    return 200, {'status': 'CANCELADO'}


@add('GET', rf'/api/pedidos/{UUID}', 'public')
def r_order(c):
    o = service.public_order(c.m.group(1))
    o['demo_pagamento_permitido'] = demo_allowed(c) and o['demo']
    return 200, o


@add('POST', r'/api/demo/pagar', 'public')
def r_demo_pay(c):
    if not settings.demo:
        return 404, {'erro': 'Rota não encontrada'}
    if not demo_allowed(c):
        return 403, {'erro': 'Aprovação fictícia permitida apenas no computador do servidor'}
    if not security.limiter.allow('demo', c.ip, 60, 60):
        return 429, {'erro': 'Muitas tentativas. Aguarde um instante.'}
    status = service.demo_pay(str(c.body.get('pedido', '')), str(c.body.get('resultado', 'aprovado')))
    return 200, {'status': status, 'aviso': 'PAGAMENTO FICTÍCIO — NÃO HOUVE PIX REAL'}


@add('POST', r'/api/webhook/pagamento', 'webhook')
def r_webhook(c):
    return 200, service.payment_webhook(c.body)


# ------------------------------------------------------------------ dispositivo
@add('GET', rf'/api/dispositivos/{MESA}/proximo\.txt', 'device')
def r_next_txt(c):
    cmd = service.device_next(c.m.group(1), c.ip, c.h.headers.get('X-Firmware'))
    return 200, ('text', cmd['id'] if cmd else 'NONE')


@add('GET', rf'/api/dispositivos/{MESA}/proximo', 'device')
def r_next(c):
    cmd = service.device_next(c.m.group(1), c.ip, c.h.headers.get('X-Firmware'))
    return 200, {'comando': ({'id': cmd['id'], 'tipo': 'PULSO', 'pedido': cmd['pedido_id'], 'expira_em': cmd['expira_em']} if cmd else None)}


@add('POST', rf'/api/dispositivos/{MESA}/iniciar', 'device')
def r_start(c):
    return 200, {'status': service.device_start(c.m.group(1), str(c.body.get('comando', '')), c.ip)}


@add('POST', rf'/api/dispositivos/{MESA}/confirmar', 'device')
def r_ack(c):
    dur = c.body.get('duracao_ms')
    return 200, {'status': service.device_ack(c.m.group(1), str(c.body.get('comando', '')), dur if isinstance(dur, int) else None, c.ip)}


@add('POST', rf'/api/dispositivos/{MESA}/incerto', 'device')
def r_uncertain(c):
    return 200, {'status': service.device_uncertain(c.m.group(1), str(c.body.get('comando', '')), c.ip)}


# ------------------------------------------------------------------ admin
@add('POST', r'/api/admin/login', 'login')
def r_login(c):
    if security.limiter.count('login', c.ip, 300) >= 5:
        return 429, {'erro': 'Muitas tentativas de login. Aguarde alguns minutos.'}
    if not security.check_admin_password(str(c.body.get('senha', ''))):
        security.limiter.hit('login', c.ip)
        return 401, {'erro': 'Senha incorreta'}
    security.limiter.clear('login', c.ip)
    sid, csrf = security.sessions.create(c.ip)
    with db.connect() as conn:
        service.audit(conn, 'admin', 'LOGIN', 'sessao', '', c.ip)
    c.h.set_cookie = sid
    return 200, {'csrf': csrf}


@add('POST', r'/api/admin/logout', 'admin')
def r_logout(c):
    security.sessions.delete(c.h.session_id())
    c.h.clear_cookie = True
    return 200, {'ok': True}


@add('GET', r'/api/admin/estado', 'public')
def r_state(c):
    """Sondagem sem erro 401 no console: informa se ha sessao valida (e o token CSRF dela)."""
    sess = security.sessions.get(c.h.session_id())
    return 200, ({'autenticado': True, 'csrf': sess['csrf']} if sess else {'autenticado': False})


@add('GET', r'/api/admin/sessao', 'admin')
def r_session(c):
    return 200, {'csrf': c.h.session['csrf'], 'estabelecimento': service.public_config()['estabelecimento']}


@add('GET', r'/api/admin/resumo', 'admin')
def r_summary(c):
    return 200, service.admin_summary()


@add('GET', r'/api/admin/auditoria', 'admin')
def r_audit(c):
    return 200, {'auditoria': service.admin_audit()}


@add('POST', r'/api/admin/mesas', 'admin')
def r_new_table(c):
    return 201, service.admin_create_table('admin', c.ip, c.body.get('nome'), c.body.get('preco_centavos'))


@add('POST', rf'/api/admin/mesas/{MESA}', 'admin')
def r_edit_table(c):
    service.admin_update_table('admin', c.ip, c.m.group(1), c.body)
    return 200, {'ok': True}


@add('POST', rf'/api/admin/mesas/{MESA}/rotacionar', 'admin')
def r_rotate(c):
    return 200, service.admin_rotate_token('admin', c.ip, c.m.group(1))


@add('POST', rf'/api/admin/mesas/{MESA}/liberar', 'admin')
def r_manual(c):
    return 201, service.admin_manual_release('admin', c.ip, c.m.group(1), str(c.body.get('motivo', '')))


@add('POST', rf'/api/admin/pedidos/{UUID}/resolver', 'admin')
def r_resolve(c):
    service.admin_resolve('admin', c.ip, c.m.group(1), str(c.body.get('acao', '')), str(c.body.get('motivo', '')))
    return 200, {'ok': True}


@add('POST', r'/api/admin/config', 'admin')
def r_settings(c):
    service.admin_settings('admin', c.ip, c.body)
    return 200, {'ok': True}


@add('GET', r'/api/admin/backup', 'admin')
def r_backup(c):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / 'backup.sqlite3'
        service.backup_to(target)
        data = target.read_bytes()
    with db.connect() as conn:
        service.audit(conn, 'admin', 'BACKUP_BAIXADO', 'banco', '', c.ip)
    return 200, ('file', data, 'application/octet-stream', f'mesafacil-backup-{db.now()[:10]}.sqlite3')


@add('GET', rf'/qr/{MESA}\.(png|svg)', 'public')
def r_qr(c):
    mesa, fmt = c.m.group(1), c.m.group(2)
    service.public_table(mesa)  # 404 se nao existe
    import qrcode
    url = f'{settings.public_base_url}/mesa/{mesa}'
    if fmt == 'svg':
        import qrcode.image.svg
        img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage, border=4)
        out = BytesIO()
        img.save(out)
        return 200, ('file', out.getvalue(), 'image/svg+xml', None)
    out = BytesIO()
    qrcode.make(url, border=4).save(out, format='PNG')
    return 200, ('file', out.getvalue(), 'image/png', None)


# ------------------------------------------------------------------ handler
class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    timeout = 15
    server_version = 'MesaFacil'
    sys_version = ''
    set_cookie = None
    clear_cookie = False
    session = None

    def log_message(self, fmt, *args):
        print(f'[{self.log_date_time_string()}] {self.client_ip()} {fmt % args}', flush=True)

    def client_ip(self):
        if settings.trust_proxy:
            fwd = self.headers.get('X-Forwarded-For', '')
            if fwd:
                return fwd.split(',')[-1].strip()[:45]
        return self.client_address[0]

    def session_id(self):
        raw = self.headers.get('Cookie', '')
        try:
            jar = SimpleCookie(raw)
        except Exception:
            return None
        return jar[COOKIE].value if COOKIE in jar else None

    # ---- respostas
    def _headers(self, code, ctype, length, cache='no-store'):
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(length))
        self.send_header('Cache-Control', cache)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        self.send_header('Content-Security-Policy', CSP)
        if self.set_cookie:
            secure = '; Secure' if settings.cookie_secure else ''
            self.send_header('Set-Cookie', f'{COOKIE}={self.set_cookie}; HttpOnly; SameSite=Strict; Path=/; Max-Age={settings.session_ttl}{secure}')
        if self.clear_cookie:
            self.send_header('Set-Cookie', f'{COOKIE}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0')

    def send_result(self, code, obj):
        if isinstance(obj, tuple) and obj[0] == 'text':
            data = (obj[1] + '\n').encode('ascii')
            self._headers(code, 'text/plain; charset=ascii', len(data))
        elif isinstance(obj, tuple) and obj[0] == 'file':
            data = obj[1]
            self._headers(code, obj[2], len(data), 'private, no-store')
            if obj[3]:
                self.send_header('Content-Disposition', f'attachment; filename="{obj[3]}"')
        else:
            data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
            self._headers(code, 'application/json; charset=utf-8', len(data))
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def send_error_json(self, code, msg):
        self.send_result(code, {'erro': msg})

    def static(self, path):
        data = path.read_bytes()
        etag = '"' + hashlib.sha256(data).hexdigest()[:16] + '"'
        if self.headers.get('If-None-Match') == etag:
            self.send_response(304)
            self.send_header('ETag', etag)
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            return
        self._headers(200, TYPES.get(path.suffix, 'application/octet-stream'), len(data), 'no-cache')
        self.send_header('ETag', etag)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    # ---- entrada
    def do_HEAD(self):
        self.dispatch('GET')

    def do_GET(self):
        self.dispatch('GET')

    def do_POST(self):
        self.dispatch('POST')

    def read_body(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            raise ValueError('Corpo inválido')
        if size > MAX_BODY or size < 0:
            raise ValueError('Corpo de requisição grande demais')
        if size == 0:
            return {}, b''
        raw = self.rfile.read(size)
        try:
            body = json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise ValueError('JSON inválido')
        if not isinstance(body, dict):
            raise ValueError('JSON inválido')
        return body, raw

    def dispatch(self, method):
        path = urlparse(self.path).path
        try:
            if method == 'GET' and not path.startswith(('/api/', '/qr/')):
                return self.serve_page(path)
            for m, rx, fn, kind in ROUTES:
                match = rx.match(path)
                if m == method and match:
                    return self.run(fn, match, kind)
            if any(rx.match(path) for _, rx, _, _ in ROUTES):
                return self.send_error_json(405, 'Método não permitido')
            return self.send_error_json(404, 'Rota não encontrada')
        except ServiceError as exc:
            self.send_error_json(exc.status, str(exc))
        except (ConnectionError, TimeoutError):
            pass
        except Exception as exc:  # nao vazar detalhes internos
            print(f'ERRO INTERNO {method} {path}: {type(exc).__name__}: {exc}', file=sys.stderr, flush=True)
            self.send_error_json(500, 'Erro interno')

    def run(self, fn, match, kind):
        ip = self.client_ip()
        raw = b''
        body = {}
        if self.command == 'POST':
            try:
                body, raw = self.read_body()
            except ValueError as exc:
                return self.send_error_json(400, str(exc))
        if kind == 'device':
            mesa = match.group(1)
            if not security.limiter.allow('device', f'{mesa}', 240, 60):
                return self.send_error_json(429, 'Muitas requisições')
            auth = self.headers.get('Authorization', '')
            token = auth[7:] if auth.startswith('Bearer ') else ''
            if not service.authenticate_device(mesa, token):
                return self.send_error_json(401, 'Credencial inválida')
        elif kind == 'admin':
            if not security.limiter.allow('admin', ip, 300, 60):
                return self.send_error_json(429, 'Muitas requisições')
            self.session = security.sessions.get(self.session_id())
            if not self.session:
                return self.send_error_json(401, 'Autenticação necessária')
            if self.command == 'POST':
                if not self.origin_ok() or self.headers.get('X-CSRF-Token', '') != self.session['csrf']:
                    return self.send_error_json(403, 'Verificação CSRF falhou')
        elif kind == 'login':
            if not self.origin_ok():
                return self.send_error_json(403, 'Origem não permitida')
        elif kind == 'webhook':
            if not security.limiter.allow('webhook', ip, 120, 60):
                return self.send_error_json(429, 'Muitas requisições')
            if not service.verify_signature(raw, self.headers.get('X-Signature', '')):
                return self.send_error_json(401, 'Assinatura inválida')
        else:
            if not security.limiter.allow('read', ip, 900, 60):
                return self.send_error_json(429, 'Muitas requisições')
        code, obj = fn(Ctx(self, match, body))
        self.send_result(code, obj)

    def origin_ok(self):
        origin = self.headers.get('Origin')
        if not origin:
            return True
        return urlparse(origin).netloc == self.headers.get('Host', '')

    def serve_page(self, path):
        if path == '/placas':
            self.send_response(302)
            self.send_header('Location', '/admin/placas')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if re.fullmatch(r'/mesa/\d{2,4}', path):
            return self.static(WEB / 'mesa.html')
        if path in PAGES:
            return self.static(WEB / PAGES[path])
        m = re.fullmatch(r'/assets/((?:fonts/)?[\w-]+(?:[.-][\w-]+)*\.(?:css|js|svg|png|ico|woff2|txt))', path)
        if m and (WEB / 'assets' / m.group(1)).is_file():
            return self.static(WEB / 'assets' / m.group(1))
        return self.send_error_json(404, 'Página não encontrada')


def housekeeping_loop():
    while True:
        time.sleep(5)
        try:
            service.housekeeping()
        except Exception as exc:
            print(f'housekeeping: {exc}', file=sys.stderr, flush=True)


def serve():
    db.init()
    generated = security.ensure_admin()
    print(f'\nMesaFácil v{__import__("mesafacil").__version__} — modo de pagamento: {settings.payment_mode.upper()}')
    if settings.demo:
        print('DEMONSTRAÇÃO: pagamentos FICTÍCIOS, nenhum Pix real é gerado.')
    print(f'Cliente: {settings.public_base_url}/   Admin: http://{settings.host}:{settings.port}/admin')
    if generated:
        print(f'\nSenha inicial do administrador (exibida UMA vez): {generated}\n'
              'Defina a sua com: python app.py --senha-admin   (ou variável ADMIN_PASSWORD no primeiro início)\n')
    threading.Thread(target=housekeeping_loop, daemon=True, name='housekeeping').start()
    server = ThreadingHTTPServer((settings.host, settings.port), Handler)
    server.daemon_threads = True
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        print('\nServidor interrompido')
    finally:
        server.server_close()
