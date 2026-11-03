# Arquitetura

## Componentes

```
Celular do cliente ──HTTP──▶ Backend Python (stdlib) ◀──HTTP poll (Bearer por mesa)── ESP32 da mesa
                              │  SQLite (WAL)                                           botão + pulso 350 ms
Painel do atendente ──cookie+CSRF──┘
Provedor de Pix (futuro) ──webhook assinado (HMAC)──▶ /api/webhook/pagamento
```

- **Backend** (`mesafacil/`): `config.py` (variáveis de ambiente), `db.py` (schema v2 + migração do v0.3), `service.py` (regras), `security.py` (senha PBKDF2, sessões, limitador), `server.py` (rotas/HTTP). Só biblioteca padrão + `qrcode`.
- **Frontend** (`web/`): HTML + CSS + JS vanilla, sem build, sem CDN, sem scripts inline (CSP `script-src 'self'`). ~50 KB por página.
- **Firmware** (`velxio/sketch_template.ino`, v0.4): polling a cada 2 s; botão físico consome o crédito.

## Por que não mudar a stack
10 mesas ≈ 5 requisições/s no pior caso (polling) — SQLite com WAL e `BEGIN IMMEDIATE` sobra. Não se justificam Postgres, Redis, MQTT, filas, containers orquestrados ou framework SPA. Docker é opcional.

## Máquina de estados

Pedido: `PENDENTE → PAGO → LIBERADO`; saídas: `RECUSADO`, `CANCELADO`, `EXPIRADO`; e `EM_ANALISE` (valor divergente, pagamento tardio, comando expirado ou incerto) que **bloqueia a mesa até decisão do atendente**.

Comando (uma linha por crédito; é o que o ESP32 vê):

| Estado | Significado | Quem muda |
|---|---|---|
| `PENDENTE` | crédito disponível (pagamento aprovado) | backend |
| `ENTREGUE` | **comando recebido** pelo controlador (ele consultou) | `GET proximo` |
| `INICIADO` | **acionamento iniciado** | `POST iniciar` (opcional) |
| `EXECUTADO` | **acionamento concluído** + **confirmação persistida**; pedido vira `LIBERADO` | `POST confirmar` |
| `INCERTO` | controlador reiniciou entre iniciar e concluir; **nunca** repete sozinho; pedido `EM_ANALISE` | `POST incerto` |
| `EXPIRADO` / `CANCELADO` | não iniciado a tempo / substituído pelo atendente | backend / atendente |

`HTTP 200` em `proximo` significa só "entregue". A página do cliente mostra "Mesa liberada" apenas com `EXECUTADO`. Um ACK tardio vale mesmo se o comando expirou (o pulso físico ocorreu), levando `EM_ANALISE → LIBERADO`.

## Integridade
- Índices parciais únicos: **uma cobrança aberta por mesa**, **um comando ativo por pedido**, **uma execução por pedido**.
- Toda escrita usa transação imediata; aprovação é feita em um único ponto (`_approve`), idempotente. Notificações de pagamento repetidas (mesmo `evento_id` ou outro evento da mesma cobrança) não criam segundo crédito (testado com 20 requisições simultâneas).
- O servidor valida valor e mesa; o navegador só envia o identificador da cobrança.

## Pagamento: dois modos totalmente separados
- `PAYMENT_MODE=demo` (padrão): `/api/demo/pagar` simula aprovado/recusado/processando; pedidos têm `origem=DEMO`; por padrão só aceita o computador do servidor.
- `PAYMENT_MODE=webhook`: rota de demo **não existe**; `/api/webhook/pagamento` exige `X-Signature` = HMAC-SHA256(corpo, `WEBHOOK_SECRET`), valida valor, idempotência por `evento_id`, e trata pagamento tardio como `EM_ANALISE`. **Falta o adaptador do provedor** (criar cobrança Pix e devolver QR/copia-e-cola): não existe nem foi validado com Pix real.

## Redes e acesso do cliente
Um QR que aponta para `http://192.168.x.x:8765/mesa/01` **só funciona para quem está no mesmo Wi-Fi**. Opções:

| Opção | Prós | Contras |
|---|---|---|
| 1. Tudo local (PC do bar) | custo zero, latência mínima, dados locais | cliente precisa do Wi-Fi do bar; PC precisa ficar ligado |
| 2. Local + provedor externo de pagamento | webhook precisa ser alcançável de fora → exige túnel/proxy seguro | uma superfície pública mínima |
| 3. Serviço público mínimo (página do cliente + webhook) e sincronização com o local | QR funciona em 4G | custo e complexidade recorrentes; mais risco |

Recomendação para piloto: **opção 1** (Wi-Fi do bar para clientes, QR com IP fixo/nome local). Para Pix real, avaliar túnel com autenticação (Cloudflare Tunnel / Tailscale Funnel) apenas para o caminho do webhook. **Não exponha a porta 8765 à internet**; defina `TRUST_PROXY` e `COOKIE_SECURE` só atrás de um proxy confiável com TLS.

## Limites conhecidos
Tráfego ESP32↔backend é HTTP em claro na LAN (token Bearer visível a quem espiona a rede) — usar rede dedicada/VLAN; TLS no ESP32 é trabalho futuro. Sessões de admin ficam em memória (reiniciar o servidor desloga).
