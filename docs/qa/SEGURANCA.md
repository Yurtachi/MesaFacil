# Segurança

Escopo validado: **demonstração local**. Não revisado por terceiros; não há pentest. Pix real e hardware físico **não validados**.

## Riscos encontrados e controles

| Risco (ver AUDITORIA_INICIAL) | Controle implementado | Verificação |
|---|---|---|
| Aprovação de pagamento sem autenticação | Rota demo só existe em `PAYMENT_MODE=demo` e só do PC do servidor (ou `DEMO_REMOTE_PAY=1`); modo `webhook` exige HMAC-SHA256 | `WebhookMode.*` |
| Painel público | Todas as rotas `/api/admin/*` exigem sessão; HTML do painel não traz dados; placas redirecionam ao login | `test_17`, E2E |
| Sessão/CSRF | Cookie `HttpOnly; SameSite=Strict` (+`Secure` com `COOKIE_SECURE`), token CSRF por sessão em todo POST, checagem de `Origin` | `test_liberacao_manual...` (403) |
| Força bruta | 5 falhas / 5 min por IP → 429; PBKDF2-SHA256 240 mil iterações; senha inicial aleatória exibida uma vez | `test_zz_limite...` |
| Abuso de endpoints | Limitador: criação de pedido (20/min/IP), demo, webhook, dispositivo (por mesa), admin, leitura | testes + revisão |
| Credenciais de mesa | Token único por mesa; **só o hash SHA-256 fica no banco**; exibido uma vez ao criar/rotacionar; rotação invalida o anterior; arquivo de chaves com `0600` e ignorado pelo Git | `test_16`, `test_backup...` |
| Isolamento entre mesas | Comando e token sempre conferidos com a mesa da rota | `test_06` |
| Duplicidade de crédito | Índices únicos parciais + transação imediata + `_approve` idempotente | `test_05`, webhook |
| Repetição de pulso | Estado `INCERTO`; backend nunca reoferece; firmware v0.4 reporta e não repete; só o operador reabre (comando antigo é cancelado) | `test_11` |
| HTTP 200 ≠ abertura física | Etapas separadas; cliente só vê "liberada" com acionamento concluído relatado | `test_01` |
| Injeção/XSS | SQL parametrizado; JS monta DOM com `textContent`; CSP `script-src 'self'; style-src 'self'`, `frame-ancestors 'none'`, `nosniff`, sem scripts/estilos inline | E2E XSS, `test_cabecalhos` |
| Entradas | Limites: corpo 16 KB, nome ≤40, preço 1–100000 centavos, ids regex; erros 500 genéricos | `test_validacao...` |
| Logs | Não registram tokens, senhas nem corpo; IP aparece (dado pessoal mínimo) | revisão |
| Segredos no Git | `.gitignore` de `.env`, SQLite, chaves, `privado/`, backups; varredura de segredos antes do push (ver relatório) | `git ls-files` |

Varreduras: bandit 0, ruff 0, pip-audit 0, npm audit 0; workflow CodeQL (python/js) configurado, **resultados dependem do GitHub**.

## Riscos remanescentes (conhecidos)
1. **HTTP sem TLS entre ESP32 e backend**: token Bearer visível na LAN. Mitigar com rede dedicada; TLS é trabalho futuro.
2. Sessões de admin em memória e login único (sem multiusuário/papéis) — um só "atendente".
3. Limitadores em memória por processo; atrás de proxy dependem de `TRUST_PROXY` correto (confiar em `X-Forwarded-For` sem proxy permitiria burlar limites).
4. Adaptador de provedor Pix inexistente: o caminho `webhook` está implementado e testado **apenas com mensagens simuladas**; a assinatura real de um PSP (formato, cabeçalhos, consulta de confirmação) precisa ser adaptada e homologada.
5. Segurança elétrica da interface com a mesa não analisada.
6. Sem auditoria de leitura (só de ações), sem retenção/rotação de logs, sem política LGPD formal (não há dados pessoais além de IP em log).
7. Pagamento de demonstração por celular (`DEMO_REMOTE_PAY=1`) deve ficar desligado fora de testes.
