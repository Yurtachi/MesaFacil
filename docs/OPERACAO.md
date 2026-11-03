# Operação diária

## Painel (`/admin`)
- **Mesas**: situação (Livre / Aguardando pagamento / Pago, aguardando botão / Em análise), controlador online/offline (último contato), preço, último comando em linguagem clara.
- **Pendências**: pedidos `EM_ANALISE` com botão *Resolver*.
- **Histórico**: cobranças e eventos recentes. **Auditoria**: toda ação administrativa (quem, o quê, quando, IP, motivo).
- **Ajustes**: nome do estabelecimento, preço padrão, QR codes para imprimir, backup.

## Situações comuns

| Situação | O que fazer |
|---|---|
| Controlador *offline* | Verificar energia e Wi-Fi da mesa. O contador "visto há" mostra o último contato. Em modo `webhook` o sistema não cobra mesa offline. |
| Cliente pagou e a mesa não libera | Ver o último comando: *crédito disponível* = controlador não buscou (offline); *recebido pela mesa* = aguardando o botão; se virou **Pendência**, ir ao próximo item. |
| **Pendência** (estado incerto, comando expirado, valor divergente, pagamento tardio) | **Conferir fisicamente** se as fichas saíram e escolher: *Reabrir crédito* (cria novo comando e cancela o antigo), *Marcar como liberado* ou *Cancelar* (estorno é feito fora do sistema). O motivo é obrigatório e fica na auditoria. Nunca reabra sem conferir: o pulso anterior pode ter ocorrido. |
| Liberação de cortesia / ficha presa | Cartão da mesa → *Liberar* (exige motivo; só se a mesa estiver livre). Gera crédito sem cobrança; a mesa libera ao apertar o botão. |
| Nova mesa | *Nova mesa* → a credencial do controlador aparece **uma vez**; grave-a no firmware (`gerar_firmware.py --token`). Imprima o QR em *Imprimir QR codes*. |
| Credencial vazou / trocar controlador | Cartão → *Credencial* (rotaciona; a antiga deixa de valer na hora). |
| Cliente abandonou o Pix | Cobrança expira sozinha (`ORDER_TTL_S`, padrão 10 min) e libera a mesa. |

## Backup e restauração
- Manual: `python scripts/backup.py` (cópia consistente, com servidor rodando) ou *Ajustes → Baixar backup*. Agende diariamente (Agendador de Tarefas do Windows) e copie para fora do PC.
- Restaurar: **pare o servidor** → `python scripts/restore.py caminho\backup.sqlite3` (verifica integridade e preserva o banco atual) → inicie e confira o painel.
- O backup **não contém credenciais** (só hashes). Guarde `device_keys.json` separadamente se quiser reaproveitar firmwares; senão, rotacione as credenciais.

## Saúde
`GET /api/health` → `{"status":"ok"}`. Logs no console (não registram tokens nem senhas). Reinício do servidor preserva todo o estado (testado); sessões de admin são perdidas.
