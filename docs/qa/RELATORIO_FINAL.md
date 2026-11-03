# Relatório final

## Resumo
A base `MesaFacil_Local_Integrado_v03` foi auditada, migrada para um backend modular com autenticação, estados de comando distintos e idempotência, redesenhada (checkout mobile first, painel do atendente, placas QR), testada (34 testes de backend, 109 de navegador, axe, Lighthouse, ruff, bandit, pip-audit) e documentada. O contrato do firmware v0.3 foi preservado (5 testes legados passam sem alteração).

## O que mudou
- **Segurança/pagamento**: rota de aprovação fictícia isolada do modo real; modo `webhook` com HMAC, valor validado no servidor, idempotência por evento; admin com senha PBKDF2, sessão, CSRF, limitação de taxa, CSP e demais cabeçalhos; tokens de mesa só como hash.
- **Hardware/protocolo**: estados `PENDENTE → ENTREGUE → (INICIADO) → EXECUTADO`, mais `INCERTO`/`EXPIRADO`; nunca repete pulso incerto; ACK tardio reconcilia; expiração de cobrança e comando; heartbeat do controlador.
- **Operação**: cadastro/edição de mesas e preços, rotação de credencial, liberação manual e resolução de pendências com motivo e auditoria, backup/restauração, `/api/health`.
- **Visual**: sistema de design em tokens (feltro escuro + um acento latão, Manrope self-host), componentes e estados completos, sem dependências externas.
- **Engenharia**: `.env.example`, Docker (validado), CI (ruff, bandit, pip-audit, testes, Playwright/axe, docker, CodeQL).

## Validado × não validado

| Item | Status | Evidência |
|---|---|---|
| Fluxo demo ponta a ponta (cliente → pagamento simulado → controlador simulado → liberada) | **Validado** (software) | `test_01`, `flow.spec.js`, smoke do `iniciar.py` |
| Concorrência, idempotência, mesa errada, falha de ACK, reinício, queda do backend, expiração, migração | **Validado** (software) | `TESTES_FUNCIONAIS.md` |
| Autorização do admin, CSRF, limites, XSS, backup sem segredos | **Validado** (software) | `SEGURANCA.md` |
| Layout 320–1440, axe WCAG 2.2 AA (automático), Lighthouse | **Validado** em Chromium headless/localhost | `TESTES_VISUAIS.md` |
| Docker build + health + usuário não root | **Validado** local | execução manual |
| Firmware v0.4 compilado / rodando no Velxio ou ESP32 | **Validado no Velxio na rodada 2** (não em ESP32 físico) | `docs/qa/INTEGRACAO_VELXIO.md` |
| Mesa física, relé, eletrônica | **NÃO validado** | sem hardware |
| Pix real (criação de cobrança, webhook de PSP) | **NÃO implementado/validado** | falta adaptador e credenciais |
| Leitor de tela real, aparelhos reais, 4G | **NÃO validado** | — |
| Execução do CI e CodeQL no GitHub | **Validado** | CI e CodeQL verdes no commit `1e8ece5` |

## Entrega no GitHub — **CONCLUÍDA** (atualizado após a rodada 1)
O primeiro `git push` falhou (403: sessão `gh` na conta `DiegoXmart`, só leitura). O push foi refeito autenticado como **Yurtachi**; `main` publicada com o SHA `1e8ece51bcf82ec0f4df9dfc38c232040ea2f04c`, e os workflows **CI** e **CodeQL** terminaram com sucesso nesse commit. A rodada 2 (redesign) está em `docs/qa/RELATORIO_FINAL_V2.md`.

## Classificação
- **Pronto para demonstração local: SIM** (com ressalvas acima; senha de admin é definida/gerada localmente).
- **Pronto para piloto com hardware físico: NÃO.** Falta compilar e testar o firmware, projeto e validação elétrica, teste de campo, rede dedicada.
- **Pronto para operação financeira real: NÃO.** Falta integração Pix real, homologação, TLS/hardening, revisão de segurança independente.

## Notas (rubrica ancorada, 0–10; sem arredondar para cima)
| Item | Nota | Medida |
|---|---|---|
| Checkout mobile | 8 | CTA na 1ª tela, 0 violações axe, alvos ≥44 px, Lighthouse 100; sem teste em aparelho real nem com usuários |
| Painel do atendente | 8 | fluxo completo testado; um único usuário; sem paginação além de 40 linhas |
| Integridade de pagamento/comando | 8 | testes de concorrência e falha; ausência de teste em hardware |
| Segurança | 7 | controles listados; TLS ESP32↔backend e revisão externa pendentes |
| Entrega GitHub | 8 | publicado, CI e CodeQL verdes |
