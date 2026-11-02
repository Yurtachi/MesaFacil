"""Senha do admin (PBKDF2), sessoes em memoria, CSRF e limitacao de taxa."""
import hashlib
import hmac
import secrets
import threading
import time

from .config import settings
from .db import connect, read

ITERATIONS = 240_000


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ITERATIONS).hex()
    return f'pbkdf2${ITERATIONS}${salt}${digest}'


def verify_password(password, stored):
    try:
        _, iters, salt, digest = stored.split('$')
        calc = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), int(iters)).hex()
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(calc, digest)


def set_admin_password(password):
    if len(password) < 8:
        raise ValueError('A senha do administrador precisa ter ao menos 8 caracteres')
    with connect() as conn:
        conn.execute("INSERT INTO config(chave,valor) VALUES('admin_hash',?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor",
                     (hash_password(password),))


def ensure_admin():
    """Garante senha de admin. Retorna a senha gerada (para exibir UMA vez) ou None."""
    with read() as conn:
        row = conn.execute("SELECT valor FROM config WHERE chave='admin_hash'").fetchone()
    if row:
        return None
    if settings.admin_password:
        set_admin_password(settings.admin_password)
        return None
    generated = secrets.token_urlsafe(12)
    set_admin_password(generated)
    return generated


def check_admin_password(password):
    with read() as conn:
        row = conn.execute("SELECT valor FROM config WHERE chave='admin_hash'").fetchone()
    # custo constante mesmo sem hash configurado
    return verify_password(password, row['valor'] if row else hash_password('x' * 12)) and bool(row)


class Sessions:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {}

    def create(self, ip):
        sid, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(24)
        with self._lock:
            self._prune()
            self._data[sid] = {'csrf': csrf, 'exp': time.time() + settings.session_ttl, 'ip': ip}
        return sid, csrf

    def get(self, sid):
        if not sid:
            return None
        with self._lock:
            s = self._data.get(sid)
            if s and s['exp'] < time.time():
                del self._data[sid]
                return None
            return s

    def delete(self, sid):
        with self._lock:
            self._data.pop(sid, None)

    def _prune(self):
        t = time.time()
        for k in [k for k, v in self._data.items() if v['exp'] < t]:
            del self._data[k]


class RateLimiter:
    """Janela deslizante por (balde, chave). Em memoria: suficiente para um unico processo."""

    def __init__(self):
        self._lock = threading.Lock()
        self._hits = {}

    def allow(self, bucket, key, limit, window):
        t = time.monotonic()
        with self._lock:
            hits = [h for h in self._hits.get((bucket, key), ()) if t - h < window]
            if len(hits) >= limit:
                self._hits[(bucket, key)] = hits
                return False
            hits.append(t)
            self._hits[(bucket, key)] = hits
            if len(self._hits) > 5000:
                self._hits = {k: v for k, v in self._hits.items() if v and t - v[-1] < 600}
            return True

    def count(self, bucket, key, window):
        t = time.monotonic()
        with self._lock:
            return len([h for h in self._hits.get((bucket, key), ()) if t - h < window])

    def hit(self, bucket, key):
        with self._lock:
            self._hits.setdefault((bucket, key), []).append(time.monotonic())

    def clear(self, bucket, key):
        with self._lock:
            self._hits.pop((bucket, key), None)

    def reset(self):
        with self._lock:
            self._hits.clear()


sessions = Sessions()
limiter = RateLimiter()
