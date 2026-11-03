# Testes funcionais

**Tudo aqui é software.** Os "controladores" são `FakeDevice` (`testes/helpers.py`), que reproduz a lógica do firmware (NVS `started/done`, pulso contado, falhas injetadas). **Nenhum teste foi executado em ESP32, relé ou mesa físicos.** O sketch v0.4 não foi compilado.

Comando: `python -W ignore -m unittest discover -s testes -v` (servidor real em subprocesso + HTTP real + SQLite temporário).
Resultado final: **34 testes, 34 aprovados, 0 falhas** (29 novos em `test_backend.py` + 5 legados do v0.3 que continuam passando sem alteração, comprovando o contrato do firmware). Baseline antes das mudanças: 5/5.

## Cenários pedidos (seção 10 do escopo)

| # | Cenário | Teste | Resultado |
|---|---|---|---|
| 1 | Pagamento fictício aprovado → crédito → botão → liberada | `test_01_pagamento_aprovado_ate_liberacao` | ok |
| 2 | Pagamento recusado (sem crédito) | `test_02_...recusado...` | ok |
| 3 | Pagamento pendente → depois aprovado | `test_03_...pendente...` | ok |
| 4 | Reenvio da confirmação da mesma cobrança | `test_04_reenvio...` (3 pagamentos, ACK duplicado, pagamento após liberar) | ok |
| 5 | Requisições simultâneas | `test_05_requisicoes_simultaneas` (12 criações → exatamente 1 × 201; 20 aprovações → 1 comando) | ok |
| 6 | Mesas distintas isoladas | `test_06_mesas_distintas_e_mesa_errada` | ok |
| 7 | Liberar a mesa errada | mesmo teste: ACK com token da 07 em comando da 06 → 404; token da 07 na rota 06 → 401 | ok |
| 8 | Consumo duplicado de crédito | `test_04` (um pulso, ACK repetido idempotente) | ok |
| 9 | Reconexão do controlador | `test_09_reconexao...` | ok |
| 10 | Reinício com crédito pendente | `test_09` (novo dispositivo sem NVS recebe o mesmo comando, 1 pulso) | ok |
| 11 | Interrupção durante o acionamento | `test_11_interrupcao...` (estado incerto → `EM_ANALISE`, servidor não reoferece, operador reabre, novo comando, auditoria) | ok |
| 12 | Falha no ACK | `test_12_falha_no_ack...` (pulso feito, ACK perdido; reenvio sem 2º pulso) | ok |
| 13 | Backend indisponível | `test_13_14...` (processo parado; ACK falha) | ok |
| 14 | Recuperação do backend | idem (religa com o mesmo banco; estado preservado; ACK conclui) | ok |
| 15 | 10 mesas operando | `test_15_dez_mesas_operam` | ok |
| 16 | Cadastro de mesas | `test_16_cadastro...` (id 11, preço próprio, credencial única, rotação, desativação, validações) | ok |
| 17 | Acesso admin não autorizado | `test_17_...` (todas as rotas admin → 401; token de dispositivo não abre admin), CSRF → 403, Origin externo → 403, logout, limite de login → 429 | ok |
| 18 | Validação de entrada / isolamento | `test_validacao_de_entrada` (JSON inválido, corpo >16 KB, SQLi, path traversal, token errado), `test_nenhum_segredo...`, `test_cabecalhos...` | ok |

Extras: expiração de comando (`COMMAND_TTL_S=1`) → `EM_ANALISE`, resolução pelo atendente; expiração de cobrança libera a mesa; **migração do banco v0.3**; modo `webhook` (assinatura, valor divergente, idempotência por evento, pagamento tardio, rota demo inexistente, exige controlador online); backup contém SQLite válido e **não** contém tokens.

## Defeitos encontrados durante o QA e correção (ciclo implementar → testar → corrigir → retestar)

| Defeito | Como apareceu | Correção | Reteste |
|---|---|---|---|
| Migração v0.3 falhava (`FOREIGN KEY constraint failed`) ao dropar tabelas | teste manual com o SQLite real da v0.3 | ordem de `DROP` (comandos → eventos → pedidos) | `test_migracao_do_banco_v03` ok |
| Expiração não disparava (timestamps em segundos truncam o prazo) | `test_expiracao...` e `test_pedido_pendente_expira...` falharam | timestamps com milissegundos | ambos ok |
| Limitador de login contava logins corretos e bloqueava o atendente | `test_zz_limite...` | só falhas contam; sucesso zera | ok |
| Limite de criação de pedidos (20/min) atrapalhava a suíte | 9 falhas 429 | parametrizado (`RATE_ORDERS_PER_MIN`); padrão mantido em 20 | suíte verde |
| Helper de teste mandava `{}` no lugar do corpo cru (testes de JSON inválido passavam por engano) | revisão do 400 esperado | helper corrigido | ok |
| Rota `/api/admin/sessao` gerava erro 401 no console (Lighthouse best-practices 96) | Lighthouse | nova rota `/api/admin/estado` (200 sempre) | best-practices 100 |

## Lint e análise estática (resultado real)
`ruff`: 0 problemas · `bandit`: 0 problemas (após trocar SHA-1 do ETag por SHA-256 e justificar 6 falsos positivos B608 sobre constante interna) · `pip-audit`: nenhuma vulnerabilidade conhecida · `npm audit` (ferramentas de QA): 0.

## Não testado
Hardware real, Wi-Fi do ESP32, firmware compilado, Pix real/webhook de provedor real, carga >10 mesas, queda de energia no PC com escrita em curso (SQLite WAL mitiga, mas não foi provocada).
