# ESP32 — Wokwi (somente simulação)

## Teste sem servidor (gratuito)
1. Acesse https://wokwi.com/projects/new/esp32
2. Substitua o conteúdo do arquivo `sketch.ino` pelo arquivo desta pasta.
3. Substitua `diagram.json` pelo arquivo desta pasta.
4. Adicione `libraries.txt` com o conteúdo `ArduinoJson` (biblioteca opcional para o simulador).
5. Clique em **Start Simulation**.
6. No **Serial Monitor**, digite `p` e Enter: simula o pagamento **sem transferência real**.
7. Clique no botão azul na simulação: ativa o relé e acende o LED por 350 ms.
8. Clique de novo sem novo pagamento: nada é liberado.

## Integração Wokwi + backend local
1. Rode o servidor **sem o simulador virtual**: `python app.py`.
2. Em outro terminal, rode `python app.py --token 01` e copie o token de teste.
3. Em `sketch.ino`, altere `#define DEMO_OFFLINE 0`, preencha o token e preserve `MESA = "01"`.
4. Wokwi **Private IoT Gateway**: instale e habilite conforme a documentação oficial; exige plano pago. `SERVER` já está configurado para `http://host.wokwi.internal:8765`.
5. Inicie a simulação Wokwi e entre em `http://127.0.0.1:8765/mesa/01`.
6. Gere o pedido e simule o pagamento. O Wokwi deverá mostrar `APERTE O BOTÃO AZUL`.
7. Clique no botão; o relé pulsa e o backend registra confirmação.

**Importante:** O Wokwi Public Gateway gratuito consegue acessar servidores públicos na internet, mas NÃO endereços locais. Uma alternativa é criar URL pública HTTPS temporária por túnel, com configuração adequada e sem segredos reais. Este projeto não inclui nem configura túneis.

**Não utilizar este projeto diretamente na mesa física.** GPIO, tensão, polaridade e lógica de acionamento devem ser determinados a partir do hardware real.
