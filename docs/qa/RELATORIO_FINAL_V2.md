# Relatório final — rodada 2 (redesign + Velxio)

Branch `redesign-v2` a partir de `main` @ `1e8ece51bcf8` (conferido: era a HEAD local e remota no início).

## Resumo
Frontend substituído por uma identidade própria de sinuca ("Salão de bilhar"), com arte SVG original e três sequências de animação ligadas ao estado real do backend. Backend, segurança e contratos preservados. Firmware v0.4 **compilado e executado no ESP32 emulado do Velxio** contra o backend real.

## Entregas
- **Design** (`docs/design/`): direção visual com 4 alternativas avaliadas; assets e licenças (só fontes OFL; arte própria; nada de terceiros copiado).
- **Frontend** (`web/`): home com abertura (tacada que abre o triângulo) e mesas vistas de cima com estado; checkout com "palco" animado, placar, etapas, ilustração do botão físico; painel com bolas numeradas; placas impressas com QR (margem de 4 módulos); movimento reduzido respeitado.
- **Animação** (`docs/qa/ANIMACOES.md`): SVG + WAAPI; aprovação → bola ao ponto do botão; **caçapa só após acionamento confirmado**; 157 quadros, máx. 17 ms, 0 tarefas longas (Chromium headless).
- **QA** (`docs/qa/REDESIGN_V2.md`): 34 backend + 118 navegador (102 telas×larguras com axe, 9 jornadas/segurança, 7 animação) aprovados; Lighthouse 100/100/100 (LCP 0,9–1,5 s, CLS 0); 16/16 QR decodificados das placas; ruff, bandit, pip-audit, npm audit sem achados; 10 defeitos da v2 achados e corrigidos.
- **Velxio** (`docs/qa/INTEGRACAO_VELXIO.md`): compilação pelo Velxio sem warnings; Serial real; botão virtual pela UI.

## Velxio — resultado por caso (ESP32 emulado, QEMU real)

| Caso | Resultado |
|---|---|
| T1 fluxo completo (pagamento → recebido → botão → pulso 0,364 s → ACK 200 → LIBERADO) | PASS |
| T2 botão sem novo crédito | PASS (0 pulsos) |
| T3 segundo pagamento | PASS |
| T4 reinício antes do acionamento | PASS (mesmo crédito, 1 pulso) |
| T5 reinício durante o pulso | PASS **só com flash persistente** (estado incerto, 0 pulsos novos, `EM_ANALISE`); NOT TESTABLE no Velxio padrão |
| T6 backend fora | PASS (sem crédito local) |
| T7 ACK perdido | PASS (HTTP -1 ×3, depois 200, 1 pulso) |
| T8 mesa errada | PASS (401/404; firmware com token trocado: 0 pulsos) |
| T9 NVS | PASS **só com flash persistente**; no Velxio padrão a NVS não persiste (limite do emulador, não do firmware) |
| T10 mesa 01 no Velxio + mesa 02 simulada em Python | PASS (a 02 é simulador de software, não ESP32 emulado) |

Para T5/T9 foi usada, **dentro do container**, uma cópia do worker QEMU com flash persistente (a imagem não foi alterada); queda de energia simulada com `pkill -9` no QEMU ao descer GPIO26. É um arranjo de teste, não o comportamento padrão do Velxio.

### Riscos e achados do firmware (não confirmados em hardware)
1. **Glitch no boot:** GPIO26 vai a nível baixo por ~60 µs a 4 ms antes de `digitalWrite(HIGH)` (`pinMode` antes do nível). Pode acionar a mesa no reset. Mitigar com pull-up externo e medir em placa real. Não corrigido por software (tentativa não eliminou o evento no emulador).
2. **`/iniciar` nunca é chamado** pelo firmware: o backend não mostra `INICIADO` (a rota existe e é testada no backend).
3. **Polling e botão no mesmo laço:** `pollServer()` bloqueia até 3 s; teoricamente pode atrasar a leitura do botão (não observado).

## Não validado (explícito)
Pix real; ESP32/relé/mesa físicos; Safari/iOS/Firefox e aparelhos reais; leitor de tela real; câmera lendo o QR impresso; impressão física; TLS ESP32↔backend.

## Classificação
- **Pronto para demonstração local: SIM.**
- **Pronto para piloto com hardware físico: NÃO.** Falta teste em ESP32 real, projeto/medição elétrica (inclui o glitch de boot) e teste de campo.
- **Pronto para operação financeira real: NÃO.** Sem Pix real, homologação, TLS e revisão de segurança independente.
