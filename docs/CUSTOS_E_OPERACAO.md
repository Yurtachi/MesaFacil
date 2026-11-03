# Custos e trade-offs

Valores de hardware/serviço são **estimativas de ordem de grandeza** (não cotadas); confirme antes de comprar.

| Componente | Custo inicial | Recorrente | Observação |
|---|---|---|---|
| Software MesaFácil | R$ 0 (open source das dependências) | R$ 0 | Python + SQLite + `qrcode`; sem licença paga |
| Computador do bar | pode ser PC existente | energia | Precisa ficar ligado; mini-PC/notebook usado basta (carga desprezível) |
| ESP32 DevKit por mesa | ~R$ 40–80 | — | Sem display. Mais fonte 5 V, caixa e cabos |
| Interface com a placa da mesa (relé/optoacoplador) | ~R$ 10–30/mesa | — | **Não validada**: exige medir tensão/corrente/lógica da máquina real e projeto elétrico seguro |
| Roteador/Wi-Fi | existente | — | Rede dedicada/VLAN para controladores recomendada |
| Pix real | taxa do PSP por transação | por transação | Depende do provedor; exige conta, credenciais, homologação e adaptador (não implementado) |
| Túnel seguro (se webhook externo) | R$ 0 (planos gratuitos) a baixo custo | variável | Só para o caminho do webhook |
| Servidor em nuvem (opção 3) | — | ~US$ 5–15/mês (VPS pequena) | Só se necessário; aumenta superfície de ataque |

## Alternativas
1. **Local puro** (recomendada para piloto): custo ≈ hardware; depende do Wi-Fi do cliente no bar.
2. **Local + túnel só para webhook**: Pix real sem expor o painel.
3. **VPS mínima**: QR funciona em 4G, mas exige sincronização com o local e mais operação/segurança.

## Quando migrar de SQLite
Acima de dezenas de mesas com vários estabelecimentos no mesmo servidor, ou necessidade de alta disponibilidade. Não é o caso de 10 mesas.

## Operação
Backup diário (script incluso), troca de credenciais quando um controlador for substituído, atualização de dependências (`pip-audit` no CI), e conferência manual de pendências (poucas se o hardware estiver estável).
