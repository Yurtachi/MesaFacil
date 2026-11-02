# MesaFácil v0.3 — integração LOCAL com Velxio ESP32

**Para executar a integração de verdade, abra primeiro `GUIA_WINDOWS_VELXIO.md`.**

- Execute `py iniciar_integrado.py` (**não** `py iniciar.py`), para não haver dois controladores disputando a Mesa 01.
- Execute `py gerar_firmware.py --mesa 01 --servidor http://host.docker.internal:8765` para gerar o firmware para o ESP32 virtual, com credencial própria da Mesa 01.
- Verifique o acesso do Docker ao backend, e depois a conectividade Wi-Fi do ESP32 emulado. O segundo teste **não** foi reproduzido no Windows do usuário.
- O pagamento continua fictício e o sistema **NÃO** deve ser usado em mesas reais.

---

# MesaFácil — prova de conceito para 10 mesas de sinuca

**ATENÇÃO:** SOFTWARE DE DEMONSTRAÇÃO. Não recebe dinheiro; não gera Pix verdadeiro; não se comunica com o Mercado Pago. Não está pronto para o público nem para acionamento de máquinas reais.

## O que foi implementado
- 10 mesas identificadas de `01` a `10`, expansíveis no código.
- Página individual da mesa (`/mesa/01`) com valor ilustrativo de R$ 5,00.
- Um QR Code fixo por mesa (`/placas`) que leva à página da mesa correspondente.
- Simulação de confirmação de pagamento e fila de comando.
- Autorização por token específico de dispositivo, criada localmente.
- Um comando por pedido confirmado: confirmação repetida NÃO cria novos comandos.
- 10 agentes **virtuais em Python**, simulando ESP32, pulso do relé e confirmação.
- Dashboard `/admin` com mesas, pagamentos e eventos recentes.
- Código ESP32 para Wokwi com botão azul, relé e LED. Suporta modo independente e modo integrado ao backend.
- SQLite para registrar pedidos e eventos, sem exigir PostgreSQL.

## Requisitos
- Python 3.10 ou superior, com pip.

## Executar no Windows (PowerShell)

Abra esta pasta no terminal e execute:

```powershell
py -m pip install -r requirements.txt
py iniciar.py
```

Acesse: `http://127.0.0.1:8765/admin` no navegador.

Selecione uma mesa → `Gerar cobrança de teste` → `Simular Pix aprovado` → aguarde cerca de 2–4 segundos → `Liberação confirmada!`.

Para ver os QR Codes, acesse `http://127.0.0.1:8765/placas`.

**Observação:** a simulação em Python imita o comportamento do ESP32. Ela NÃO executa o firmware ESP32. Para isso, use o Wokwi, conforme `wokwi/README.md`.

## Linux / macOS

```bash
python3 -m pip install -r requirements.txt
python3 iniciar.py
```

## Testar o Wokwi na versão gratuita

Veja `wokwi/README.md`. É possível simular o botão e o relé com `DEMO_OFFLINE=1` sem qualquer backend.

## Testar Wokwi integrado à página

Use `python app.py` em vez de `python iniciar.py` (senão o agente virtual pode consumir o comando antes do Wokwi).

No Wokwi, use `DEMO_OFFLINE=0` e o **Private IoT Gateway** (pago) para acessar o backend local, ou hospede o backend temporariamente em um endereço HTTPS público e ajuste a URL. Nunca exponha tokens reais pela conexão pública monitorada do Wokwi.

## Smartphone e QR Code

Por padrão o QR tem `http://127.0.0.1:8765/mesa/XX`, **que só funciona no computador servidor**.

Para testar o QR em um celular na mesma rede local, inicie **exclusivamente em rede de confiança**:

```powershell
$env:HOST="0.0.0.0"
$env:PUBLIC_BASE_URL="http://IP_DO_COMPUTADOR:8765"
py iniciar.py
```

Substitua `IP_DO_COMPUTADOR` pelo IP real do computador (ex.: resultado de `ipconfig`). Valide as permissões de firewall. **Não abra a porta 8765 para a internet**: esta POC permite confirmar pagamentos sem autenticação porque é intencionalmente fictícia.

## Segurança / riscos / pendências antes de produção

1. **PIX real:** substituir o botão de pagamento fictício por criação de cobrança autenticada no backend; verificar assinatura do webhook, valor, identificador, status e idempotência por evento.
2. **Credenciais:** armazenar segredos em local seguro, revogação e chaves diferentes por mesa. O `device_keys.json` gerado é segredo e não deve ser commitado.
3. **Autorização:** painel administrativo e endpoints operacionais devem ter autenticação, autorização e proteção contra CSRF/abuso.
4. **Exatamente uma liberação:** o ESP32 deve persistir o identificador de execução em NVS e ter protocolo de reconciliação de comandos; aqui um reset entre pulso e confirmação pode liberar novamente. A solução de produção precisa definir política de reconciliação e modo seguro.
5. **Eletrônica:** não há esquema elétrico confirmado. Um relé na simulação NÃO valida ligar diretamente na placa da mesa. Medir tensão, corrente, nível lógico, isolamento, duração do pulso e retenção do botão.
6. **Confiabilidade:** internet, Wi-Fi, filas, tempo limite de pagamento, recuperação após queda de energia, divergências entre pagamento e acionamento, suporte e estorno.
7. **Escala:** SQLite é adequado para esta POC, mas serviços reais demandam observabilidade, backups e controles de concorrência/carga apropriados.
8. **Preço:** R$ 5,00 é fictício; confirmar regra real de cobrança (por ficha, pacote, partida ou tempo).
9. **Capacidade:** 10 mesas são configuradas em `app.py`, não descoberta automática; novas mesas exigem provisionamento e geração de credenciais.

## Arquivos

```text
iniciar.py             # inicia servidor e 10 ESP32 simulados em Python
app.py                 # API + SQLite + páginas + QR Codes
sim_esp32.py           # simulação software dos ESP32s
requirements.txt       # biblioteca de QR Code
web/index.html         # dashboard e checkout
web/style.css
web/app.js
wokwi/sketch.ino       # firmware ESP32 simulável no Wokwi
wokwi/diagram.json     # botão + relé + LED
wokwi/libraries.txt
wokwi/README.md
```

## Projetos abertos consultados (não copiados)

- Chalkboard.id — https://github.com/kugie-app/chalkboard.id
- Kasir Billing — https://github.com/rizuji23/kasir-billing
- Payme-QR-Payment-Terminal — https://github.com/myseringan/Payme-QR-Payment-Terminal
- Documentação oficial Wokwi — https://docs.wokwi.com/guides/esp32-wifi

Todo o código entregue aqui foi escrito para esta prova de conceito. Nenhum dos projetos acima foi incluído no pacote.
