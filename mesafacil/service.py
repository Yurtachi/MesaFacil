"""Regras de negocio: pedidos, pagamentos, comandos para o ESP32, administracao.

Ciclo do comando (cada etapa e registrada separadamente; HTTP 200 nao prova abertura fisica):
  PENDENTE  credito disponivel (pagamento aprovado, controlador ainda nao buscou)
  ENTREGUE  comando recebido pelo controlador (ele fez o polling)
  INICIADO  acionamento iniciado (relatado pelo controlador)
  EXECUTADO acionamento concluido, relatado pelo controlador e persistido aqui -> pedido LIBERADO
  INCERTO   controlador reiniciou no meio do ciclo: nunca repetir sozinho, exige decisao do operador
  EXPIRADO  nao iniciado a tempo: pedido pago vai para EM_ANALISE
"""
import hashlib
import hmac
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from . import db
from .config import settings
from .db import connect, now, read, hash_token


class ServiceError(Exception):
    status = 400


class Invalid(ServiceError):
    status = 400


class Forbidden(ServiceError):
    status = 403


class NotFound(ServiceError):
    status = 404


class Conflict(ServiceError):
    status = 409


class Unprocessable(ServiceError):
    status = 422


class Unavailable(ServiceError):
    status = 503


OPEN = ('PENDENTE', 'PAGO', 'EM_ANALISE')
ACTIVE_CMD = ('PENDENTE', 'ENTREGUE', 'INICIADO')


def _later(seconds):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(timespec='milliseconds')


def _parse(ts):
    return datetime.fromisoformat(ts) if ts else None


def record(conn, mesa, tipo, detalhe):
    conn.execute('INSERT INTO eventos(mesa,tipo,detalhe,criado_em) VALUES(?,?,?,?)', (mesa, tipo, str(detalhe)[:300], now()))


def audit(conn, ator, acao, alvo, detalhe, ip):
    conn.execute('INSERT INTO auditoria(ator,acao,alvo,detalhe,ip,criado_em) VALUES(?,?,?,?,?,?)',
                 (ator, acao, alvo, str(detalhe)[:300], ip, now()))


def _default_price(conn):
    row = conn.execute("SELECT valor FROM config WHERE chave='preco_padrao'").fetchone()
    return int(row['valor']) if row else settings.default_price


def _establishment(conn):
    row = conn.execute("SELECT valor FROM config WHERE chave='estabelecimento'").fetchone()
    return row['valor'] if row else settings.establishment


def _price(conn, mesa_row):
    return mesa_row['preco_centavos'] or _default_price(conn)


def _online(mesa_row):
    seen = _parse(mesa_row['visto_em'])
    if not seen:
        return False
    return (datetime.now(timezone.utc) - seen).total_seconds() <= settings.device_online_s


def _new_command(conn, order_id, mesa):
    cid = str(uuid.uuid4())
    conn.execute('INSERT INTO comandos(id,pedido_id,mesa,status,criado_em,expira_em) VALUES(?,?,?,?,?,?)',
                 (cid, order_id, mesa, 'PENDENTE', now(), _later(settings.command_ttl)))
    return cid


# ---------------------------------------------------------------- manutencao
def housekeeping():
    with connect() as conn:
        _expire(conn)


def _expire(conn):
    t = now()
    for o in conn.execute("SELECT id,mesa FROM pedidos WHERE status='PENDENTE' AND expira_em IS NOT NULL AND expira_em < ?", (t,)).fetchall():
        conn.execute("UPDATE pedidos SET status='EXPIRADO' WHERE id=?", (o['id'],))
        record(conn, o['mesa'], 'PEDIDO_EXPIRADO', o['id'])
    for c in conn.execute("SELECT id,pedido_id,mesa FROM comandos WHERE status IN ('PENDENTE','ENTREGUE') AND expira_em < ?", (t,)).fetchall():
        conn.execute("UPDATE comandos SET status='EXPIRADO' WHERE id=?", (c['id'],))
        conn.execute("UPDATE pedidos SET status='EM_ANALISE' WHERE id=? AND status='PAGO'", (c['pedido_id'],))
        record(conn, c['mesa'], 'COMANDO_EXPIRADO_SEM_ACIONAMENTO', c['id'])


# ---------------------------------------------------------------- publico
def public_config():
    with read() as conn:
        return {'estabelecimento': _establishment(conn), 'modo_pagamento': settings.payment_mode,
                'demo': settings.demo, 'preco_padrao_centavos': _default_price(conn)}


def public_tables():
    with read() as conn:
        rows = conn.execute('SELECT * FROM mesas WHERE ativa=1 ORDER BY id').fetchall()
        busy = {r['mesa'] for r in conn.execute(f"SELECT mesa FROM pedidos WHERE status IN {OPEN}")}
        return [{'id': r['id'], 'nome': r['nome'], 'ocupada': r['id'] in busy, 'online': _online(r)} for r in rows]


def public_table(mesa):
    with read() as conn:
        r = conn.execute('SELECT * FROM mesas WHERE id=?', (mesa,)).fetchone()
        if not r or not r['ativa']:
            raise NotFound('Mesa não encontrada ou indisponível')
        busy = conn.execute(f"SELECT 1 FROM pedidos WHERE mesa=? AND status IN {OPEN}", (mesa,)).fetchone()
        return {'id': r['id'], 'nome': r['nome'], 'ocupada': bool(busy), 'online': _online(r),
                'preco_centavos': _price(conn, r), 'estabelecimento': _establishment(conn),
                'demo': settings.demo, 'modo_pagamento': settings.payment_mode}


def _etapa(order, cmd):
    s = order['status']
    if s == 'PENDENTE':
        return 'processando' if order['processando'] else 'aguardando_pagamento'
    if s == 'PAGO':
        if cmd and cmd['status'] == 'INICIADO':
            return 'liberando'
        return 'aguardando_botao'
    return {'LIBERADO': 'concluido', 'EM_ANALISE': 'analise', 'RECUSADO': 'recusado',
            'CANCELADO': 'cancelado', 'EXPIRADO': 'expirado'}[s]


def public_order(oid):
    with read() as conn:
        o = conn.execute('SELECT * FROM pedidos WHERE id=?', (oid,)).fetchone()
        if not o:
            raise NotFound('Pedido não encontrado')
        c = conn.execute('SELECT status FROM comandos WHERE pedido_id=? ORDER BY criado_em DESC, rowid DESC LIMIT 1', (oid,)).fetchone()
        m = conn.execute('SELECT * FROM mesas WHERE id=?', (o['mesa'],)).fetchone()
        return {'pedido': o['id'], 'mesa': o['mesa'], 'status': o['status'], 'etapa': _etapa(o, c),
                'valor_centavos': o['valor_centavos'], 'origem': o['origem'], 'demo': o['origem'] == 'DEMO',
                'comando': c['status'] if c else None, 'controlador_online': _online(m),
                'expira_em': o['expira_em'], 'criado_em': o['criado_em'], 'pago_em': o['pago_em'],
                'liberado_em': o['liberado_em']}


def create_order(mesa):
    with connect() as conn:
        _expire(conn)
        m = conn.execute('SELECT * FROM mesas WHERE id=?', (mesa,)).fetchone()
        if not m or not m['ativa']:
            raise NotFound('Mesa não encontrada ou indisponível')
        if settings.require_device_online and not _online(m):
            raise Unavailable('O controlador desta mesa está sem conexão. Chame o atendente.')
        if conn.execute(f"SELECT 1 FROM pedidos WHERE mesa=? AND status IN {OPEN}", (mesa,)).fetchone():
            raise Conflict('Já existe uma compra em andamento nesta mesa')
        oid = str(uuid.uuid4())
        conn.execute('INSERT INTO pedidos(id,mesa,valor_centavos,status,origem,provider_txid,criado_em,expira_em) VALUES(?,?,?,?,?,?,?,?)',
                     (oid, mesa, _price(conn, m), 'PENDENTE', 'DEMO' if settings.demo else 'PIX',
                      None if settings.demo else oid, now(), _later(settings.order_ttl)))
        record(conn, mesa, 'PEDIDO_CRIADO', oid)
    return public_order(oid)


def cancel_order(oid):
    with connect() as conn:
        o = conn.execute('SELECT mesa,status FROM pedidos WHERE id=?', (oid,)).fetchone()
        if not o:
            raise NotFound('Pedido não encontrado')
        if o['status'] == 'CANCELADO':
            return
        if o['status'] != 'PENDENTE':
            raise Conflict('Não é possível cancelar após o pagamento')
        conn.execute("UPDATE pedidos SET status='CANCELADO' WHERE id=?", (oid,))
        record(conn, o['mesa'], 'PEDIDO_CANCELADO', oid)


# ---------------------------------------------------------------- pagamento
def _approve(conn, order, source):
    """Unico ponto que transforma pagamento aprovado em credito. Idempotente."""
    if order['status'] != 'PENDENTE':
        return order['status']
    conn.execute("UPDATE pedidos SET status='PAGO', pago_em=?, processando=0 WHERE id=? AND status='PENDENTE'", (now(), order['id']))
    _new_command(conn, order['id'], order['mesa'])
    record(conn, order['mesa'], source, order['id'])
    return 'PAGO'


def demo_pay(oid, resultado='aprovado'):
    if not settings.demo:
        raise NotFound('Rota não encontrada')
    if resultado not in ('aprovado', 'recusado', 'pendente'):
        raise Invalid('Resultado inválido')
    with connect() as conn:
        _expire(conn)
        o = conn.execute('SELECT * FROM pedidos WHERE id=?', (oid,)).fetchone()
        if not o:
            raise NotFound('Pedido inexistente')
        if o['origem'] != 'DEMO':
            raise Forbidden('Pedido não é de demonstração')
        if o['status'] != 'PENDENTE':
            return o['status']
        if resultado == 'aprovado':
            return _approve(conn, o, 'PAGAMENTO_SIMULADO')
        if resultado == 'recusado':
            conn.execute("UPDATE pedidos SET status='RECUSADO', processando=0 WHERE id=?", (oid,))
            record(conn, o['mesa'], 'PAGAMENTO_SIMULADO_RECUSADO', oid)
            return 'RECUSADO'
        conn.execute('UPDATE pedidos SET processando=1 WHERE id=?', (oid,))
        record(conn, o['mesa'], 'PAGAMENTO_SIMULADO_PENDENTE', oid)
        return 'PENDENTE'


def verify_signature(body, signature):
    if not settings.webhook_secret:
        return False
    good = hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(good, (signature or '').strip().lower())


def payment_webhook(payload):
    """Notificacao do provedor (modo webhook). Idempotente por evento_id; valida valor no servidor."""
    if settings.demo:
        raise NotFound('Rota não encontrada')
    ev = str(payload.get('evento_id', ''))[:80]
    txid = str(payload.get('txid', ''))[:80]
    result = str(payload.get('status', ''))
    try:
        amount = int(payload.get('valor_centavos'))
    except (TypeError, ValueError):
        raise Invalid('Valor inválido')
    if not ev or not txid or result not in ('aprovado', 'recusado', 'pendente'):
        raise Invalid('Notificação inválida')
    with connect() as conn:
        _expire(conn)
        if conn.execute('SELECT 1 FROM pagamentos_eventos WHERE evento_id=?', (ev,)).fetchone():
            return {'duplicado': True}
        o = conn.execute('SELECT * FROM pedidos WHERE provider_txid=?', (txid,)).fetchone()
        conn.execute('INSERT INTO pagamentos_eventos(evento_id,pedido_id,resultado,valor_centavos,recebido_em) VALUES(?,?,?,?,?)',
                     (ev, o['id'] if o else None, result, amount, now()))
        if not o:
            raise NotFound('Cobrança desconhecida')
        if result == 'aprovado':
            if amount != o['valor_centavos']:
                record(conn, o['mesa'], 'PAGAMENTO_VALOR_DIVERGENTE', f"{o['id']} esperado={o['valor_centavos']} recebido={amount}")
                if o['status'] == 'PENDENTE':
                    conn.execute("UPDATE pedidos SET status='EM_ANALISE' WHERE id=?", (o['id'],))
                return {'status': 'EM_ANALISE', 'aviso': 'valor divergente'}
            if o['status'] in ('EXPIRADO', 'CANCELADO', 'RECUSADO'):
                # dinheiro entrou depois do prazo: nao libera sozinho, operador decide
                conn.execute("UPDATE pedidos SET status='EM_ANALISE', pago_em=? WHERE id=?", (now(), o['id']))
                record(conn, o['mesa'], 'PAGAMENTO_TARDIO', o['id'])
                return {'status': 'EM_ANALISE'}
            return {'status': _approve(conn, o, 'PAGAMENTO_CONFIRMADO_PROVEDOR')}
        if result == 'recusado' and o['status'] == 'PENDENTE':
            conn.execute("UPDATE pedidos SET status='RECUSADO' WHERE id=?", (o['id'],))
            record(conn, o['mesa'], 'PAGAMENTO_RECUSADO', o['id'])
        return {'status': o['status']}


# ---------------------------------------------------------------- dispositivo
def authenticate_device(mesa, token):
    if not token:
        return False
    with read() as conn:
        r = conn.execute('SELECT token_hash FROM mesas WHERE id=?', (mesa,)).fetchone()
    return bool(r) and hmac.compare_digest(r['token_hash'], hash_token(token))


def _touch(conn, mesa, ip, firmware):
    conn.execute('UPDATE mesas SET visto_em=?, visto_ip=?, firmware=COALESCE(?,firmware) WHERE id=?',
                 (now(), ip, (firmware or None) and firmware[:40], mesa))


def device_next(mesa, ip='', firmware=None):
    with connect() as conn:
        _touch(conn, mesa, ip, firmware)
        _expire(conn)
        cmd = conn.execute("SELECT * FROM comandos WHERE mesa=? AND status IN ('PENDENTE','ENTREGUE') ORDER BY criado_em, rowid LIMIT 1", (mesa,)).fetchone()
        if cmd and cmd['status'] == 'PENDENTE':
            conn.execute("UPDATE comandos SET status='ENTREGUE', entregue_em=? WHERE id=?", (now(), cmd['id']))
            record(conn, mesa, 'COMANDO_RECEBIDO_PELO_CONTROLADOR', cmd['id'])
        return dict(cmd) if cmd else None


def _device_cmd(conn, mesa, cmd_id):
    row = conn.execute('SELECT * FROM comandos WHERE id=? AND mesa=?', (cmd_id, mesa)).fetchone()
    if not row:
        raise NotFound('Comando não pertence a esta mesa')
    return row


def device_start(mesa, cmd_id, ip=''):
    with connect() as conn:
        _touch(conn, mesa, ip, None)
        row = _device_cmd(conn, mesa, cmd_id)
        if row['status'] in ('PENDENTE', 'ENTREGUE'):
            conn.execute("UPDATE comandos SET status='INICIADO', iniciado_em=?, entregue_em=COALESCE(entregue_em,?) WHERE id=?", (now(), now(), cmd_id))
            record(conn, mesa, 'ACIONAMENTO_INICIADO', cmd_id)
            return 'INICIADO'
        return row['status']


def device_ack(mesa, cmd_id, duration_ms=None, ip=''):
    """Confirmacao de acionamento CONCLUIDO relatado pelo controlador. Idempotente."""
    with connect() as conn:
        _touch(conn, mesa, ip, None)
        row = _device_cmd(conn, mesa, cmd_id)
        if row['status'] == 'EXECUTADO':
            return 'LIBERADO'
        if row['status'] == 'CANCELADO':
            record(conn, mesa, 'EXECUCAO_DE_COMANDO_CANCELADO', cmd_id)
            return 'CANCELADO'
        t = now()
        dur = duration_ms if isinstance(duration_ms, int) and 0 <= duration_ms <= 60000 else None
        conn.execute("UPDATE comandos SET status='EXECUTADO', executado_em=?, iniciado_em=COALESCE(iniciado_em,?), duracao_ms=? WHERE id=?",
                     (t, t, dur, cmd_id))
        # o pulso fisico ocorreu: vale mesmo se o comando tinha expirado ou ficado incerto
        conn.execute("UPDATE pedidos SET status='LIBERADO', liberado_em=? WHERE id=? AND status IN ('PAGO','EM_ANALISE')",
                     (t, row['pedido_id']))
        record(conn, mesa, 'ACIONAMENTO_CONCLUIDO_E_PERSISTIDO', cmd_id)
        return 'LIBERADO'


def device_uncertain(mesa, cmd_id, ip=''):
    with connect() as conn:
        _touch(conn, mesa, ip, None)
        row = _device_cmd(conn, mesa, cmd_id)
        if row['status'] in ('EXECUTADO', 'CANCELADO'):
            return row['status']
        conn.execute("UPDATE comandos SET status='INCERTO' WHERE id=?", (cmd_id,))
        conn.execute("UPDATE pedidos SET status='EM_ANALISE' WHERE id=? AND status='PAGO'", (row['pedido_id'],))
        record(conn, mesa, 'ESTADO_INCERTO_REPORTADO', cmd_id)
        return 'INCERTO'


# ---------------------------------------------------------------- admin
def admin_summary():
    with connect() as conn:  # connect: roda _expire e garante leitura consistente
        _expire(conn)
        mesas = conn.execute('SELECT * FROM mesas ORDER BY id').fetchall()
        open_orders = {r['mesa']: r for r in conn.execute(f"SELECT * FROM pedidos WHERE status IN {OPEN}")}
        last_cmd = {}
        for r in conn.execute('SELECT * FROM comandos ORDER BY criado_em, rowid'):
            last_cmd[r['mesa']] = r
        out = []
        for m in mesas:
            o = open_orders.get(m['id'])
            c = last_cmd.get(m['id'])
            out.append({'id': m['id'], 'nome': m['nome'], 'ativa': bool(m['ativa']), 'online': _online(m),
                        'visto_em': m['visto_em'], 'firmware': m['firmware'],
                        'preco_centavos': m['preco_centavos'], 'preco_efetivo_centavos': _price(conn, m),
                        'estado': o['status'] if o else 'DISPONIVEL', 'pedido': o['id'] if o else None,
                        'comando': c['status'] if c else None})
        orders = [dict(r) for r in conn.execute('SELECT * FROM pedidos ORDER BY criado_em DESC, rowid DESC LIMIT 40')]
        events = [dict(r) for r in conn.execute('SELECT * FROM eventos ORDER BY id DESC LIMIT 30')]
        issues = [dict(r) for r in conn.execute("SELECT p.id,p.mesa,p.status,p.valor_centavos,p.pago_em,c.status AS comando FROM pedidos p LEFT JOIN comandos c ON c.pedido_id=p.id AND c.rowid=(SELECT MAX(rowid) FROM comandos WHERE pedido_id=p.id) WHERE p.status='EM_ANALISE' ORDER BY p.criado_em")]
        today = now()[:10]
        stats = conn.execute("SELECT COUNT(*) n, COALESCE(SUM(valor_centavos),0) total FROM pedidos WHERE status='LIBERADO' AND origem!='MANUAL' AND liberado_em LIKE ?", (today + '%',)).fetchone()
        return {'estabelecimento': _establishment(conn), 'modo_pagamento': settings.payment_mode, 'demo': settings.demo,
                'preco_padrao_centavos': _default_price(conn), 'mesas': out, 'pedidos': orders, 'eventos': events,
                'pendencias': issues, 'hoje': {'liberacoes': stats['n'], 'total_centavos': stats['total']}}


def admin_audit(limit=60):
    with read() as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM auditoria ORDER BY id DESC LIMIT ?', (limit,))]


def _valid_name(name, default):
    name = (name or default).strip()
    if not 1 <= len(name) <= 40 or any(ord(ch) < 32 for ch in name):
        raise Invalid('Nome inválido (1 a 40 caracteres)')
    return name


def _valid_price(v):
    if v in (None, ''):
        return None
    if isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 100000:
        raise Invalid('Preço inválido (1 a 100000 centavos)')
    return v


def admin_create_table(actor, ip, nome=None, preco=None, mesa_id=None):
    price = _valid_price(preco)
    with connect() as conn:
        if mesa_id is None:
            nums = [int(r['id']) for r in conn.execute('SELECT id FROM mesas')]
            mesa_id = f'{(max(nums) + 1) if nums else 1:02}'
        if not (isinstance(mesa_id, str) and mesa_id.isdigit() and 2 <= len(mesa_id) <= 4):
            raise Invalid('Identificador de mesa inválido')
        if conn.execute('SELECT 1 FROM mesas WHERE id=?', (mesa_id,)).fetchone():
            raise Conflict('Mesa já existe')
        token = secrets.token_urlsafe(32)
        conn.execute('INSERT INTO mesas(id,nome,preco_centavos,token_hash,criado_em) VALUES(?,?,?,?,?)',
                     (mesa_id, _valid_name(nome, f'Mesa {mesa_id}'), price, hash_token(token), now()))
        audit(conn, actor, 'MESA_CRIADA', mesa_id, nome or '', ip)
    return {'id': mesa_id, 'token': token}


def admin_update_table(actor, ip, mesa, data):
    with connect() as conn:
        m = conn.execute('SELECT * FROM mesas WHERE id=?', (mesa,)).fetchone()
        if not m:
            raise NotFound('Mesa não encontrada')
        nome = _valid_name(data['nome'], m['nome']) if 'nome' in data else m['nome']
        preco = _valid_price(data['preco_centavos']) if 'preco_centavos' in data else m['preco_centavos']
        ativa = m['ativa']
        if 'ativa' in data:
            if not isinstance(data['ativa'], bool):
                raise Invalid('Campo ativa deve ser booleano')
            ativa = int(data['ativa'])
            if not ativa and conn.execute(f"SELECT 1 FROM pedidos WHERE mesa=? AND status IN {OPEN}", (mesa,)).fetchone():
                raise Conflict('Mesa tem cobrança em andamento')
        conn.execute('UPDATE mesas SET nome=?, preco_centavos=?, ativa=? WHERE id=?', (nome, preco, ativa, mesa))
        audit(conn, actor, 'MESA_ATUALIZADA', mesa, f'nome={nome} preco={preco} ativa={ativa}', ip)


def admin_rotate_token(actor, ip, mesa):
    with connect() as conn:
        if not conn.execute('SELECT 1 FROM mesas WHERE id=?', (mesa,)).fetchone():
            raise NotFound('Mesa não encontrada')
        token = secrets.token_urlsafe(32)
        conn.execute('UPDATE mesas SET token_hash=? WHERE id=?', (hash_token(token), mesa))
        audit(conn, actor, 'CREDENCIAL_ROTACIONADA', mesa, '', ip)
    return {'id': mesa, 'token': token}


def admin_settings(actor, ip, data):
    with connect() as conn:
        if 'estabelecimento' in data:
            name = str(data['estabelecimento']).strip()
            if not 1 <= len(name) <= 60:
                raise Invalid('Nome do estabelecimento inválido')
            conn.execute("INSERT INTO config(chave,valor) VALUES('estabelecimento',?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (name,))
        if 'preco_padrao_centavos' in data:
            price = _valid_price(data['preco_padrao_centavos'])
            if price is None:
                raise Invalid('Preço inválido')
            conn.execute("INSERT INTO config(chave,valor) VALUES('preco_padrao',?) ON CONFLICT(chave) DO UPDATE SET valor=excluded.valor", (str(price),))
        audit(conn, actor, 'CONFIG_ATUALIZADA', 'config', ','.join(sorted(data)), ip)


def admin_manual_release(actor, ip, mesa, motivo):
    motivo = (motivo or '').strip()
    if not 3 <= len(motivo) <= 200:
        raise Invalid('Informe o motivo da liberação manual (3 a 200 caracteres)')
    with connect() as conn:
        _expire(conn)
        m = conn.execute('SELECT * FROM mesas WHERE id=?', (mesa,)).fetchone()
        if not m or not m['ativa']:
            raise NotFound('Mesa não encontrada ou inativa')
        if conn.execute(f"SELECT 1 FROM pedidos WHERE mesa=? AND status IN {OPEN}", (mesa,)).fetchone():
            raise Conflict('Mesa tem cobrança em andamento: resolva-a antes')
        oid = str(uuid.uuid4())
        conn.execute('INSERT INTO pedidos(id,mesa,valor_centavos,status,origem,criado_em,pago_em) VALUES(?,?,0,?,?,?,?)',
                     (oid, mesa, 'PAGO', 'MANUAL', now(), now()))
        _new_command(conn, oid, mesa)
        record(conn, mesa, 'LIBERACAO_MANUAL_AUTORIZADA', oid)
        audit(conn, actor, 'LIBERACAO_MANUAL', mesa, f'pedido={oid} motivo={motivo}', ip)
    return {'pedido': oid}


def admin_resolve(actor, ip, oid, acao, motivo):
    motivo = (motivo or '').strip()
    if not 3 <= len(motivo) <= 200:
        raise Invalid('Informe o motivo (3 a 200 caracteres)')
    if acao not in ('reabrir', 'liberado', 'cancelar'):
        raise Invalid('Ação inválida')
    with connect() as conn:
        o = conn.execute('SELECT * FROM pedidos WHERE id=?', (oid,)).fetchone()
        if not o:
            raise NotFound('Pedido não encontrado')
        if o['status'] != 'EM_ANALISE':
            raise Conflict('Pedido não está em análise')
        t = now()
        if acao == 'reabrir':
            # novo credito; o comando anterior (incerto/expirado) nunca e reutilizado
            conn.execute("UPDATE comandos SET status='CANCELADO' WHERE pedido_id=? AND status IN ('PENDENTE','ENTREGUE','INICIADO','INCERTO','EXPIRADO')", (oid,))
            conn.execute("UPDATE pedidos SET status='PAGO', pago_em=COALESCE(pago_em,?) WHERE id=?", (t, oid))
            _new_command(conn, oid, o['mesa'])
        elif acao == 'liberado':
            conn.execute("UPDATE pedidos SET status='LIBERADO', liberado_em=? WHERE id=?", (t, oid))
        else:
            conn.execute("UPDATE comandos SET status='CANCELADO' WHERE pedido_id=? AND status IN ('PENDENTE','ENTREGUE','INICIADO','INCERTO','EXPIRADO')", (oid,))
            conn.execute("UPDATE pedidos SET status='CANCELADO' WHERE id=?", (oid,))
        record(conn, o['mesa'], 'PENDENCIA_RESOLVIDA_' + acao.upper(), oid)
        audit(conn, actor, 'PENDENCIA_' + acao.upper(), oid, motivo, ip)


def backup_to(path):
    """Copia consistente do banco (API de backup do SQLite) para `path`."""
    src = sqlite3.connect(settings.db, timeout=15)
    try:
        dst = sqlite3.connect(path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def health():
    with read() as conn:
        conn.execute('SELECT 1').fetchone()
    return {'status': 'ok', 'demo': settings.demo, 'versao': '0.4.0'}
