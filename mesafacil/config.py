"""Configuracao por variaveis de ambiente. Nenhum segredo fica no codigo."""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


def _int(name, default):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        raise SystemExit(f'Variavel {name} deve ser um numero inteiro')


def _flag(name, default='0'):
    return os.getenv(name, default).strip().lower() in ('1', 'true', 'sim', 'yes')


class Settings:
    def __init__(self):
        self.db = Path(os.getenv('SINUCA_DB', str(BASE / 'sinuca_demo.sqlite3')))
        self.keys = Path(os.getenv('SINUCA_KEYS', str(BASE / 'device_keys.json')))
        self.port = _int('PORT', 8765)
        self.host = os.getenv('HOST', '127.0.0.1')
        self.public_base_url = os.getenv('PUBLIC_BASE_URL', f'http://127.0.0.1:{self.port}').rstrip('/')
        self.payment_mode = os.getenv('PAYMENT_MODE', 'demo').strip().lower()
        if self.payment_mode not in ('demo', 'webhook'):
            raise SystemExit('PAYMENT_MODE deve ser "demo" ou "webhook"')
        self.webhook_secret = os.getenv('WEBHOOK_SECRET', '')
        self.admin_password = os.getenv('ADMIN_PASSWORD', '')
        self.demo_remote_pay = _flag('DEMO_REMOTE_PAY')
        self.establishment = os.getenv('ESTABELECIMENTO', 'MesaFácil Sinuca')[:60]
        self.default_price = _int('PRICE_CENTS', 500)
        self.seed_tables = _int('TABLE_COUNT', 10)
        self.command_ttl = _int('COMMAND_TTL_S', 1800)
        self.order_ttl = _int('ORDER_TTL_S', 600)
        self.device_online_s = _int('DEVICE_ONLINE_S', 30)
        self.require_device_online = _flag('REQUIRE_DEVICE_ONLINE', '1' if self.payment_mode == 'webhook' else '0')
        self.trust_proxy = _flag('TRUST_PROXY')
        self.cookie_secure = _flag('COOKIE_SECURE')
        self.session_ttl = _int('SESSION_TTL_S', 8 * 3600)
        self.rate_orders = _int('RATE_ORDERS_PER_MIN', 20)

    @property
    def demo(self):
        return self.payment_mode == 'demo'


settings = Settings()
