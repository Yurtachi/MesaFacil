# Auditoria inicial (base `MesaFacil_Local_Integrado_v03`)

Escopo: leitura integral do código disponível em `D:\Docs\Git\Sinuca\MesaFacil_Local_Integrado_v03` (22 arquivos: `app.py`, `sim_esp32.py`, `web/*`, `velxio/`, `wokwi/`, `testes/`, docs). O repositório GitHub `Yurtachi/MesaFacil` estava **vazio** (`isEmpty: true`); a base foi importada sem alterações no primeiro commit (`efbff29`).

## Baseline de testes (antes de qualquer mudança)

`python -m unittest discover -s testes` → **5 testes, 5 aprovados** (contrato da API, 10 mesas, idempotência de pagamento/ACK, mesa cruzada, QR PNG). Somente simulados em software.

## Mapa

| Item | Estado na base |
|---|---|
| Backend | `http.server` + SQLite em um único `app.py` (~300 linhas), `RLock` global |
| Rotas | `/api/mesas`, `/api/pedidos`, `/api/demo/pagar`, `/api/dispositivos/NN/{proximo,proximo.txt,confirmar}`, `/qr/NN.png` |
| Mesas | lista fixa `01..10` no código; sem cadastro |
| Preço | constante `PRICE_CENTS=500` |
| Comando | `PENDENTE → EXECUTADO`; pedido `PENDENTE → PAGO → LIBERADO` |
| Autenticação de dispositivo | token por mesa em `device_keys.json` (texto puro), comparação em tempo constante |
| Autenticação admin | **inexistente** (`/admin`, `/api/mesas` públicos) |
| Frontend | SPA vanilla com `innerHTML`, CSS único, polling de 1,5 s |
| Firmware | `velxio/sketch_template.ino`: persiste `started` antes do pulso e `done` depois; não repete pulso de comando iniciado |

## Achados

Legenda: **[F]** fato comprovado por leitura de código/teste; **[H]** hipótese a validar; **[R]** reproduzido.

### P0 (bloqueia qualquer uso real)
- **[F] Aprovação de pagamento sem autenticação forte.** `/api/demo/pagar` só verifica `client_address in (127.0.0.1, ::1)`. Atrás de proxy reverso/túnel (necessário para o QR funcionar fora do Wi-Fi) todo cliente aparece como `127.0.0.1`. **[H]** → qualquer pessoa aprova pagamento falso. Corrigido: rota inexistente fora do modo demo, separada do webhook assinado.
- **[F] Painel e dados operacionais públicos.** `/` e `/admin` servem o painel; `/api/mesas` devolve pedidos e eventos sem login.

### P1
- **[F] Sem estados distintos para "comando recebido / acionamento iniciado / concluído".** O backend só conhecia `PENDENTE/EXECUTADO`; um reset entre pulso e ACK não tinha caminho de reconciliação (o README original admite).
- **[F] Cobrança aberta nunca expira.** O índice único `uma_cobranca_aberta_por_mesa` mantém a mesa bloqueada indefinidamente se o cliente abandonar o pagamento. Comandos também não expiram.
- **[F] Sem CSRF, sem limitação de taxa, sem cabeçalhos de segurança (CSP, nosniff, frame-options).**
- **[F] Tokens em texto puro** no arquivo e na memória do processo.
- **[F] Sem cadastro de mesas**, preços por mesa, nem ação de liberação manual com auditoria.

### P2
- **[F]** Renderização via `innerHTML` com dados de servidor (risco de XSS se algum campo vier a aceitar texto livre).
- **[F]** Sem recusa/processamento no fluxo de pagamento; sem noção de "controlador offline".
- **[F]** Firmware não reporta estado incerto ao backend; sem observabilidade do dispositivo (último contato, versão).
- **[F]** Interface expõe jargão técnico ("ESP32 virtual do Velxio") ao cliente; alvos de toque e contraste não verificados.
- **[F]** `Cache-Control: no-store` em todos os assets (sem ETag).

### P3
- **[F]** Sem CI, `.env.example`, Docker, backup/restauração documentados; README mistura v0.3 e POC.
- **[F]** Import de `qrcode` a cada requisição; `sim_esp32.py` sem persistência de estado.
- **[F]** Arquivos com credenciais presentes no workspace (`device_keys.json`, `privado/*.ino`, SQLite) — já estavam no `.gitignore` e **não foram importados** ao Git.

## Não verificado
Eletrônica real, mesa física, Pix real, Wi-Fi do ESP32 no Windows do usuário (o README original diz que não foi reproduzido).
