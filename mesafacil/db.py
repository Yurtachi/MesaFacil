"""SQLite: conexao, schema v2 e migracao do schema v1 (POC v0.3)."""
import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from .config import settings

SCHEMA_VERSION = 2

SCHEMA = [
    'CREATE TABLE IF NOT EXISTS config (chave TEXT PRIMARY KEY, valor TEXT NOT NULL)',
    '''CREATE TABLE IF NOT EXISTS mesas (
        id TEXT PRIMARY KEY CHECK(id GLOB '[0-9][0-9]*' AND length(id) BETWEEN 2 AND 4),
        nome TEXT NOT NULL,
        preco_centavos INTEGER CHECK(preco_centavos IS NULL OR preco_centavos BETWEEN 1 AND 100000),
        ativa INTEGER NOT NULL DEFAULT 1,
        token_hash TEXT NOT NULL,
        criado_em TEXT NOT NULL,
        visto_em TEXT, visto_ip TEXT, firmware TEXT)''',
    '''CREATE TABLE IF NOT EXISTS pedidos (
        id TEXT PRIMARY KEY,
        mesa TEXT NOT NULL REFERENCES mesas(id),
        valor_centavos INTEGER NOT NULL CHECK(valor_centavos >= 0),
        status TEXT NOT NULL CHECK(status IN ('PENDENTE','PAGO','LIBERADO','CANCELADO','RECUSADO','EXPIRADO','EM_ANALISE')),
        origem TEXT NOT NULL DEFAULT 'DEMO' CHECK(origem IN ('DEMO','PIX','MANUAL')),
        processando INTEGER NOT NULL DEFAULT 0,
        provider_txid TEXT UNIQUE,
        criado_em TEXT NOT NULL,
        expira_em TEXT,
        pago_em TEXT,
        liberado_em TEXT)''',
    '''CREATE UNIQUE INDEX IF NOT EXISTS uma_cobranca_aberta_por_mesa
        ON pedidos(mesa) WHERE status IN ('PENDENTE','PAGO','EM_ANALISE')''',
    'CREATE INDEX IF NOT EXISTS pedidos_criado ON pedidos(criado_em)',
    '''CREATE TABLE IF NOT EXISTS comandos (
        id TEXT PRIMARY KEY,
        pedido_id TEXT NOT NULL REFERENCES pedidos(id),
        mesa TEXT NOT NULL REFERENCES mesas(id),
        status TEXT NOT NULL CHECK(status IN ('PENDENTE','ENTREGUE','INICIADO','EXECUTADO','INCERTO','EXPIRADO','CANCELADO')),
        criado_em TEXT NOT NULL,
        expira_em TEXT NOT NULL,
        entregue_em TEXT, iniciado_em TEXT, executado_em TEXT,
        duracao_ms INTEGER)''',
    '''CREATE UNIQUE INDEX IF NOT EXISTS um_comando_ativo_por_pedido
        ON comandos(pedido_id) WHERE status IN ('PENDENTE','ENTREGUE','INICIADO')''',
    '''CREATE UNIQUE INDEX IF NOT EXISTS uma_execucao_por_pedido
        ON comandos(pedido_id) WHERE status='EXECUTADO\'''',
    'CREATE INDEX IF NOT EXISTS comandos_mesa ON comandos(mesa, status)',
    '''CREATE TABLE IF NOT EXISTS pagamentos_eventos (
        evento_id TEXT PRIMARY KEY,
        pedido_id TEXT,
        resultado TEXT NOT NULL,
        valor_centavos INTEGER,
        recebido_em TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS eventos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mesa TEXT NOT NULL,
        tipo TEXT NOT NULL,
        detalhe TEXT NOT NULL,
        criado_em TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS auditoria (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ator TEXT NOT NULL, acao TEXT NOT NULL, alvo TEXT NOT NULL,
        detalhe TEXT NOT NULL, ip TEXT NOT NULL, criado_em TEXT NOT NULL)''',
]


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def _open():
    conn = sqlite3.connect(settings.db, timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    conn.execute('PRAGMA busy_timeout=15000')
    return conn


@contextmanager
def connect():
    """Transacao imediata: escritas concorrentes sao serializadas pelo SQLite."""
    conn = _open()
    conn.execute('BEGIN IMMEDIATE')
    try:
        yield conn
        conn.execute('COMMIT')
    except BaseException:
        conn.execute('ROLLBACK')
        raise
    finally:
        conn.close()


@contextmanager
def read():
    conn = _open()
    try:
        yield conn
    finally:
        conn.close()


def _create_schema(conn):
    for stmt in SCHEMA:
        conn.execute(stmt)


def _migrate_v1(conn):
    """POC v0.3 -> v2: preserva pedidos, comandos e eventos."""
    for t in ('pedidos', 'comandos', 'eventos'):
        conn.execute(f'ALTER TABLE {t} RENAME TO {t}_v1')
    conn.execute('DROP INDEX IF EXISTS uma_cobranca_aberta_por_mesa')
    _create_schema(conn)
    _seed(conn)
    mesas = {r[0] for r in conn.execute('SELECT id FROM mesas')}
    for (m,) in conn.execute('SELECT DISTINCT mesa FROM pedidos_v1').fetchall():
        if m not in mesas:
            conn.execute('INSERT INTO mesas(id,nome,token_hash,criado_em,ativa) VALUES(?,?,?,?,0)',
                         (m, f'Mesa {m}', 'x', now()))
    conn.execute('''INSERT INTO pedidos(id,mesa,valor_centavos,status,origem,criado_em,pago_em,liberado_em)
                    SELECT id,mesa,valor_centavos,status,'DEMO',criado_em,pago_em,liberado_em FROM pedidos_v1''')
    conn.execute('''INSERT INTO comandos(id,pedido_id,mesa,status,criado_em,expira_em,executado_em)
                    SELECT id,pedido_id,mesa,status,criado_em,criado_em,executado_em FROM comandos_v1''')
    conn.execute('INSERT INTO eventos(mesa,tipo,detalhe,criado_em) SELECT mesa,tipo,detalhe,criado_em FROM eventos_v1')
    for t in ('comandos', 'eventos', 'pedidos'):
        conn.execute(f'DROP TABLE {t}_v1')


def init():
    settings.db.parent.mkdir(parents=True, exist_ok=True)
    conn = _open()
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('BEGIN IMMEDIATE')
        version = conn.execute('PRAGMA user_version').fetchone()[0]
        has_orders = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='pedidos'").fetchone()
        has_mesas = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='mesas'").fetchone()
        if has_orders and not has_mesas and version < 2:
            _migrate_v1(conn)
        else:
            _create_schema(conn)
            _seed(conn)
        conn.execute(f'PRAGMA user_version={SCHEMA_VERSION}')
        conn.execute('COMMIT')
    except BaseException:
        conn.execute('ROLLBACK')
        raise
    finally:
        conn.close()


def _seed(conn):
    """Cria mesas iniciais. Tokens vem do arquivo de chaves (se houver); no banco fica so o hash."""
    if conn.execute('SELECT COUNT(*) FROM mesas').fetchone()[0]:
        return
    keys = {}
    if settings.keys.exists():
        keys = json.loads(settings.keys.read_text(encoding='utf-8'))
    wrote = False
    for i in range(1, settings.seed_tables + 1):
        mid = f'{i:02}'
        if mid not in keys:
            keys[mid] = secrets.token_urlsafe(32)
            wrote = True
        conn.execute('INSERT INTO mesas(id,nome,token_hash,criado_em) VALUES(?,?,?,?)',
                     (mid, f'Mesa {mid}', hash_token(keys[mid]), now()))
    if wrote or not settings.keys.exists():
        settings.keys.write_text(json.dumps(keys, indent=2), encoding='utf-8')
        try:
            os.chmod(settings.keys, 0o600)
        except OSError:
            pass
