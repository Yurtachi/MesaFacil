# MesaFácil

Pagamento por QR code e liberação de mesas de sinuca. Cada mesa tem um QR fixo; o cliente paga no celular, o backend autoriza e um ESP32 na mesa libera as fichas quando o cliente aperta o botão físico.

> **Estado: pronto para demonstração local.** O pagamento é **simulado** (nenhum Pix real) e **nenhum hardware físico foi validado**. Não use em mesas reais nem para receber dinheiro. Veja [Limitações](#limitações).

## O que tem

- **Cliente (mobile first)**: `/mesa/NN` — preço em reais, etapas (Pagamento → Crédito na mesa → Mesa liberada), estados claros para aprovado, recusado, processando, em análise e falha; "liberada" só aparece quando o controlador **reporta** o acionamento concluído.
- **Atendente** (`/admin`, com login): situação das mesas e controladores (online/offline), pendências, histórico, auditoria, cadastro/edição de mesas e preços, rotação de credenciais, liberação manual com motivo, QR codes para imprimir, backup.
- **Backend** Python (biblioteca padrão) + SQLite. Crédito por pagamento é único e idempotente; estados separados de comando recebido / iniciado / concluído / incerto; expiração; auditoria.
- **Firmware** ESP32 (`velxio/sketch_template.ino` v0.4, não compilado neste ambiente) e simulador em Python.
- **QA**: 34 testes de backend, 109 de navegador (6 larguras, axe, E2E), Lighthouse, ruff, bandit, pip-audit, CI no GitHub Actions.

## Início rápido (Windows ou Linux)

```bash
pip install -r requirements.txt
ADMIN_PASSWORD="troque-esta-senha" python iniciar.py   # PowerShell: $env:ADMIN_PASSWORD="..."
```
Abra `http://127.0.0.1:8765/` e `http://127.0.0.1:8765/admin`. Em `/mesa/01`, pague (simulado), e o controlador simulado conclui a liberação em ~2 s. Detalhes, Docker e celular: [`docs/INSTALACAO_LOCAL.md`](docs/INSTALACAO_LOCAL.md).

## Documentação

| Documento | Conteúdo |
|---|---|
| [ARQUITETURA](docs/ARQUITETURA.md) | componentes, estados, integridade, redes, QR local vs. público |
| [INSTALACAO_LOCAL](docs/INSTALACAO_LOCAL.md) | Windows, Docker, firmware, testes |
| [OPERACAO](docs/OPERACAO.md) | uso diário, pendências, backup/restauração |
| [CUSTOS_E_OPERACAO](docs/CUSTOS_E_OPERACAO.md) | custos e alternativas |
| `docs/qa/` | auditoria inicial, skills aplicadas, testes funcionais e visuais, segurança, relatório final |

## Limitações

- **Pix real: não implementado.** Existe o modo `PAYMENT_MODE=webhook` (webhook assinado, valida valor, idempotente) testado só com mensagens simuladas; falta o adaptador do provedor e a homologação.
- **Hardware: não validado.** Sem teste em ESP32/relé/mesa; sem projeto elétrico. O pulso de 350 ms vem da POC.
- QR com endereço local só funciona na mesma rede; acesso público exige publicação segura (não exponha a porta 8765).
- HTTP sem TLS entre controlador e backend; um único usuário admin.

## Licença
O código do projeto não tem licença declarada (decisão do titular). A fonte Manrope é SIL OFL 1.1 (`web/assets/fonts/OFL-Manrope.txt`).
