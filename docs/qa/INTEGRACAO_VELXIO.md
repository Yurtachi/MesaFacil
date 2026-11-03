# Integração MesaFácil v0.4 x Velxio (ESP32 emulado) — validação real

Data: 2026-11-02. Firmware: `velxio/sketch_template.ino` (v0.4, **sem alterações** nesta validação). Backend: `python app.py` (v0.4.0, modo demo).
Escopo: **simulador**. Nada aqui comprova comportamento em hardware físico, Pix real, relé, contator ou rede de produção.

## 1. Ambiente

| Item | Valor |
|---|---|
| Velxio | imagem `ghcr.io/davidmonterocrespo24/velxio:master`, digest `sha256:5b52dc915e984871ad4c1391d79f6eb16792aba316164296934a787524d1b8e4`, criada em 2026-11-02T15:09Z, revisão git `68b2ce8fc17f1029244f0f42500a8457a2fe138a` |
| Docker | cliente e servidor 29.6.1 (Docker Desktop, Windows 11) |
| Emulação | QEMU Xtensa (`libqemu-xtensa.so`, máquina `esp32-picsimlab`) com NIC Wi-Fi emulado (SLIRP, `192.168.4.0/24`); compilação via ESP-IDF v5 dentro do container |
| Backend | Python 3.14 stdlib, banco e chaves **temporários** fora do repositório (`%TEMP%\mf_run`) |
| Porta do backend | **8777**, não 8765: a 8765 já estava ocupada por outro servidor (`iniciar_integrado.py`, PID 15620, não é meu) e não foi tocado |
| Bind | `HOST=127.0.0.1` bastou: o container alcança `http://host.docker.internal:8777` (verificado com `docker exec velxio curl`). Não foi preciso `0.0.0.0` nem mexer no firewall |
| Segurança | tokens nunca gravados em relatório/logs (verificado por busca de todos os tokens do arquivo de chaves em `docs/qa/velxio/**`: 0 ocorrências); sketch gerado fica só em `privado/` (removido ao final) |

## 2. Compilação (passo 2)

Sketch gerado com `python gerar_firmware.py --mesa 01 --servidor http://host.docker.internal:8777` e compilado **pelo próprio Velxio** (`POST /api/compile/start`, `board_fqbn=esp32:esp32:esp32`, polling de `/api/compile/status/<id>`; script `docs/qa/velxio/compilar.py`).

- Resultado: `success=True`, `has_wifi=True`, `velxio-sketch.bin binary size 0xe71e0 bytes ... (70%) free`, sem `warning:`/`error:`.
- Log: `docs/qa/velxio/logs/compile_log.txt`.
- Serial no primeiro boot: `MesaFacil v0.4, mesa 01 - SOMENTE SIMULACAO` / `Servidor: http://host.docker.internal:8777` / `WiFi conectado: 192.168.4.15, gateway 192.168.4.2`.
- Também compilado e executado **pela interface web** (Playwright, botão Run do editor): mesmo resultado (seção 5).

## 3. Método de execução

Dois caminhos, ambos com o **QEMU real do Velxio** (não é o `FakeDevice`):

1. **Headless pelo WebSocket do Velxio** (`/api/simulation/ws/<id>`, mensagens `start_esp32`, `stop_esp32`, `esp32_gpio_in`; é exatamente o que a UI usa — conferido no bundle JS). `docs/qa/velxio/emu.py` lê o Serial (`serial_output`) e os eventos de GPIO (`gpio_change`, pino 26 = pulso) e aperta o botão virtual (GPIO27: nível alto, depois baixo por 0,6 s). Usado em T1–T3, T4, T6, T7, T8b, T10.
2. **Interface web** com Playwright (`ui_screenshots.cjs`): monta o circuito (ESP32 DevKit V1 + pushbutton D27/GND), cola o sketch, clica Run, abre o Serial, **clica com o mouse no botão virtual**. Gera as capturas da seção 5.

**Limite importante do Velxio (verificado no código do container, `esp32_worker.py`):** a flash do ESP32 emulado é um arquivo temporário novo a cada partida e é apagado ao parar. **A NVS não sobrevive a parar/iniciar a simulação** (T9 abaixo comprova: `started NOT_FOUND`/`done NOT_FOUND` voltam a aparecer). Não existe comando de reset que preserve a flash. Para testar a lógica de NVS (T5, T9) usei `docs/qa/velxio/preparar_worker_persistente.py`: cria **no `/tmp` do container** uma cópia do mesmo worker (imagem intocada) que usa um arquivo de flash fixo `/tmp/mesafacil_flash.bin`, preservado entre reinícios (`EmuPersist` em `emu.py`). É o mesmo QEMU, firmware e rede; só a persistência da flash difere do Velxio padrão. "Queda de energia" = `pkill -9` no processo QEMU no instante em que GPIO26 vai a nível baixo.

Comandos (PowerShell, a partir da raiz do repositório; `$t` = diretório temporário fora do repositório):

```powershell
$t="$env:TEMP\mf_run"; New-Item -ItemType Directory $t
$env:PYTHONIOENCODING='utf-8'; $env:SINUCA_DB="$t\db.sqlite3"; $env:SINUCA_KEYS="$t\keys.json"; $env:PORT='8777'; $env:HOST='127.0.0.1'; $env:ADMIN_PASSWORD='<qualquer>'
pip install --target "$env:TEMP\mf_pylib" websockets
# 1) subir o backend uma vez (gera as chaves), gerar e compilar o sketch
python gerar_firmware.py --mesa 01 --servidor http://host.docker.internal:8777
python docs\qa\velxio\compilar.py privado\mesa_01_velxio.ino $t        # grava $t\firmware.b64
# 2) casos (cada script sobe/derruba o backend sozinho)
$env:MF_TMP=$t; $env:MF_PORT='8777'; $env:PYTHONPATH="$env:TEMP\mf_pylib"
python docs\qa\velxio\casos_a.py                         # T1 T2 T3 T6 T7 T8 T10
python docs\qa\velxio\preparar_worker_persistente.py     # necessário só para T5/T9
python docs\qa\velxio\casos_b.py                         # T4 T5 T9
python docs\qa\velxio\caso_t8b.py                        # requer firmware.b64 compilado com o token da mesa 02 (firmware_tokenerrado.b64)
# 3) UI
node docs\qa\velxio\ui_screenshots.cjs privado\mesa_01_velxio.ino docs\qa\velxio http://127.0.0.1:8777
```

Logs completos (Serial, HTTP, estados): `docs/qa/velxio/logs/casos_a.txt`, `casos_b.txt`, `caso_t8b.txt`.

## 4. Resultados por caso

| Caso | Resultado | Evidência (extratos dos logs) |
|---|---|---|
| **T1** fluxo completo | **PASS** | `POST /api/demo/pagar -> HTTP 200 PAGO`; backend `comando=ENTREGUE etapa=aguardando_botao`; Serial: `Mesa 01: pagamento de TESTE confirmado. Pressione o botao.` → clique → `FICHAS LIBERADAS (simuladas): iniciando pulso 350ms.` → `Saida desligada: 350 ms encerrados.` → `ACK: HTTP 200` → `Mesa liberada confirmada no painel.`. GPIO26 em nível baixo 1 vez por 0,364 s (relógio de parede). Final: `status=LIBERADO comando=EXECUTADO etapa=concluido` |
| **T2** novo clique sem pagamento | **PASS** | 2 cliques: Serial `BOTAO: sem credito liberado; nenhuma acao.` ×2; 0 pulsos novos em GPIO26; pedido segue `LIBERADO` |
| **T3** segundo pagamento | **PASS** | novo pedido (id distinto) pago → novo comando → clique → exatamente 1 pulso novo → `ACK: HTTP 200` → `LIBERADO` (`comandos` por pedido: 1 `EXECUTADO` cada) |
| **T4** reinício antes do acionamento | **PASS** | pedido pago e comando `ENTREGUE`, sem clique; simulação parada e iniciada (Velxio padrão): firmware voltou a receber **o mesmo** crédito (backend reoferece `ENTREGUE`), 0 pulsos sem clique; 1 clique = 1 pulso, 2º clique `BOTAO: sem credito`; `comandos=['EXECUTADO']`, pedido `LIBERADO`. Repetido com flash persistente (T4b): idem, 1 pulso. Sem crédito duplicado |
| **T5** reinício durante o pulso | **PASS** (flash persistente; ver nota) | QEMU morto (SIGKILL) ao detectar GPIO26 baixo; Serial até a queda termina em `FICHAS LIBERADAS ...` (sem `Saida desligada`); backend logo após: `PAGO / ['ENTREGUE']`. Após religar: `ATENCAO: ESTADO INCERTO, verificar manualmente antes de nova autorizacao.`; backend `pedido=EM_ANALISE comandos=['INCERTO']`; 3 cliques + 10 s de polling: **0 pulsos**, só `BOTAO: sem credito`. Aparece em `/api/admin/resumo` > `pendencias`. Epílogo: `POST /api/admin/pedidos/<id>/resolver {acao:reabrir}` -> HTTP 200 -> novo comando (`['CANCELADO','EXECUTADO']`) -> 1 pulso legítimo -> `LIBERADO`. **No Velxio padrão este caso NÃO É TESTÁVEL** (NVS apagada no reinício: o firmware não teria como saber que já iniciou) |
| **T6** backend fora | **PASS** | backend parado com firmware ocioso: `POLL: HTTP -1 (sem liberar)` a cada 2 s, cliques → `BOTAO: sem credito liberado`; 0 pulsos. Ao voltar o backend sem pedido: 0 pulsos, clique ainda `sem credito`. (T8b mostra o mesmo para `HTTP 401`.) O firmware nunca cria autorização local |
| **T7** ACK perdido | **PASS** | backend derrubado logo após `FICHAS LIBERADAS`; 3 × `ACK: HTTP -1` (reenvio a cada 2 s), 1 único pulso; backend religado (mesmo banco): `ACK: HTTP 200` → `Mesa liberada confirmada no painel.`; pulsos totais 1 (`FICHAS LIBERADAS` aparece 1 vez); pedido `LIBERADO` |
| **T8** mesa errada | **PASS** | token da 02 em `/01/proximo.txt`: 401; token da 01 em `/02/proximo.txt`: 401; sem token: 401; mesa inexistente `/99`: 401; token da 02 em `/01/confirmar`: 401; token da 01 em `/01/confirmar` com comando da mesa 02: **404** `Comando não pertence a esta mesa`; token da 02 em `/02/incerto` com comando da 01: 404. **T8b (firmware real)**: sketch da mesa 01 compilado com o token da 02, pedido da mesa 01 pago: 8 s de `POLL: HTTP 401 (sem liberar)`, cliques `sem credito`, 0 pulsos, comando segue `PENDENTE`. Ressalva: no T8 os pedidos já estavam `LIBERADO` ao testar 404 (a prova é o 404 do vínculo comando–mesa; o estado "intacto" é pouco informativo) |
| **T9** persistência NVS | **PASS** com flash persistente; **Velxio padrão: NVS NÃO persiste** | Velxio padrão: após ciclo completo e parar/iniciar, boot imprime `nvs_get_str len fail: started NOT_FOUND` e `done NOT_FOUND`. Flash persistente: após ciclo completo, o boot **não** imprime NOT_FOUND (chaves `started`/`done` lidas). Ramo `done`: backend derrubado antes do clique, pulso feito, `ACK: HTTP -1`×3, ESP32 reiniciado, backend religado: `Comando concluido antes de reiniciar. Reenviando ACK sem novo pulso.` → `ACK: HTTP 200` → `LIBERADO`; **0 pulsos** após o reinício e clique seguinte `sem credito`. T5 prova o ramo `started` |
| **T10** mesa 01 (Velxio) + mesa 02 (`sim_esp32.py --mesa 02`) | **PASS** | pedidos pagos nas duas mesas; em 6 s a 02 (simulador de software) pulsou e foi a `LIBERADO` enquanto a 01 permaneceu `PAGO/ENTREGUE` aguardando botão; clique virtual na 01 → 1 pulso → `LIBERADO`. 1 pulso em GPIO26 (Velxio) e 1 `[sim 02] pulso 350 ms` (cada um só do seu comando); 0 comandos cuja mesa difere da mesa do pedido (consulta ao banco). Nota: a mesa 02 aqui é **simulador de software**, não ESP32 emulado |

Nota T5/T9: a morte do QEMU por SIGKILL aproxima uma queda de energia no ponto mais crítico (pino já em nível baixo, `done` ainda não gravado), mas a gravação em flash do QEMU não modela a janela de corrupção/escrita parcial de uma NVS real.

## 5. Capturas de tela (UI do Velxio)

Sem o editor de código visível (o sketch contém o token). Execução real pela UI: circuito montado por cliques, compilação pelo botão Run, clique do mouse no botão virtual.

- `docs/qa/velxio/ui_01_circuito.png` — ESP32 DevKit V1 + pushbutton ligado a D27 e GND
- `ui_02_serial_wifi.png` — Serial: `MesaFacil v0.4`, `WiFi conectado`
- `ui_03_pagamento_recebido.png` — `pagamento de TESTE confirmado. Pressione o botao.`
- `ui_04_botao_pressionado.png` — botão virtual pressionado, `FICHAS LIBERADAS`
- `ui_05_ack_liberado.png` — `ACK: HTTP 200` / `Mesa liberada confirmada no painel.`; backend: `LIBERADO / EXECUTADO`

Na UI, o LED do exemplo padrão está em GPIO4 (não foi religado ao GPIO2/26); o pulso é comprovado pelo Serial e, nos scripts, pelos eventos de GPIO26.

## 6. Bugs e riscos encontrados

Nenhum bug de firmware confirmado; **o sketch não foi modificado** (uma tentativa de correção está descrita abaixo e foi revertida).

1. **Glitch em GPIO26 no boot (risco, não confirmado como bug de hardware).** No emulador GPIO26 vai a nível baixo por ~60 µs a ~4 ms durante o boot (`pinMode(OUTPUT)` antes de `digitalWrite(HIGH)`; evento `gpio_change 26=0` seguido de `26=1`, visto em todos os boots). Num relé/contator ativo em baixo isso pode ser um pulso espúrio. Tentei o idiom `digitalWrite(HIGH)` antes de `pinMode`: no emulador o evento continuou, então **não consegui provar a correção e a reverti**. Na placa real, medir com osciloscópio e usar pull-up externo no sinal ativo em baixo; o pino fica em alta impedância antes do `setup()` de qualquer forma.
2. **O firmware nunca chama `/iniciar`** (só `/proximo.txt`, `/confirmar`, `/incerto`). Por isso o backend nunca mostra `INICIADO`; durante o pulso o comando segue `ENTREGUE`. É coerente com T5 (a detecção é feita pelo firmware ao religar), mas uma queda com o backend também fora só será conciliada quando ambos voltarem.
3. **Botão e HTTP no mesmo laço.** `pollServer()` bloqueia até 3 s (`setTimeout(3000)`) e `loop()` só lê o botão entre as chamadas. Não observei clique perdido, mas é um risco teórico (falha segura: o cliente aperta de novo).
4. **Artefato do emulador, não do firmware:** no boot GPIO27 lê nível baixo até alguém driveá-lo. Pela UI o botão com pull-up define o nível; no meu cliente headless forço nível alto antes de cada clique (sem isso a primeira descida não gera borda).
5. Funcionamento do Velxio: `POLL: HTTP -1` aparece como `Connection reset by peer` quando o backend cai (comportamento do SLIRP), sem consequência.
6. Casos T1/T2 cobrem `PAGO -> LIBERADO`; `EM_ANALISE` por expiração de comando (`COMMAND_TTL_S`) não foi exercitado aqui.

## 7. Limites desta validação

- Simulador (QEMU + SLIRP) não é hardware: temporização de Wi-Fi, ruído elétrico, brown-out, corrupção parcial de NVS, desgaste de flash e comportamento real do relé não são testados. Duração do pulso medida em tempo de parede (0,364 s), sujeita à agenda do host.
- A mesa 01 no Velxio usa `host.docker.internal:8777` por HTTP simples; TLS e autenticação forte em rede real não foram validados.
- T5 e T9 dependem do worker persistente descrito na seção 3 (cópia no container, fora da imagem); no Velxio padrão são **NOT TESTABLE** pela perda da NVS. A lógica "iniciado/concluído persistidos" só foi comprovada nesse arranjo.
- Pagamento é fictício (`/api/demo/pagar`), aceito só de 127.0.0.1.
- Apenas uma mesa foi emulada em ESP32; a mesa 02 do T10 é o simulador de software existente.

## 8. Limpeza

Backend de teste e servidores auxiliares encerrados; container `velxio` mantido em execução; `/tmp/svc` e a flash persistente removidos do container; `privado/mesa_01_velxio.ino` e `privado/nvs_02.json` (gerados pelos testes) removidos; banco/chaves temporários em `%TEMP%\mf_run`.
