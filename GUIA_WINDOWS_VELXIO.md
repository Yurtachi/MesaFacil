# MesaFácil 0.3 — ligar painel local ao ESP32 do Velxio (Windows + Docker Desktop)

> **APENAS POC. Não tem Pix verdadeiro. Não conecte em contatores ou gavetas reais.**

## Arquitetura

- API Python/SQLite no Windows (porta TCP 8765 em `127.0.0.1` por padrão).
- Velxio no Docker existente, via `http://localhost:3080`.
- ESP32 virtual da mesa **01** consulta a API por HTTP a cada 2 s e exige o botão para autorizar um pulso GPIO26.
- Mesas **02 a 10** permanecem com agentes Python, isolados da mesa 01.
- Os tokens dos dispositivos são diferentes para cada mesa; ficam salvos em `device_keys.json` (não fazer commit).

## Passo 1 — rodar painel e API

Abra o PowerShell nesta pasta e execute:

```powershell
py -m pip install -r requirements.txt
py iniciar_integrado.py
```

**Não use `py iniciar.py`** neste teste: ele liga também o simulador Python da mesa 01 e competirá com o Velxio.

Abra `http://127.0.0.1:8765/admin` e deixe o terminal funcionando.

## Passo 2 — verificar Docker → Windows

Em um segundo PowerShell:

```powershell
curl.exe http://127.0.0.1:8765/api/health
docker exec velxio curl -v --max-time 5 http://host.docker.internal:8765/api/health
```

O resultado de sucesso é `{ "status": "ok", "demo": true }`.

O segundo teste só comprova **Velxio Docker → Windows**, não a rota de dentro do ESP32 emulado. Se não funcionar, não abra o firewall nem exponha a API na rede ainda; forneça a saída do comando para decidir uma alternativa local segura.

## Passo 3 — gerar firmware com token secreto (não compartilhar)

```powershell
py gerar_firmware.py --mesa 01 --servidor http://host.docker.internal:8765
```

O gerador cria `privado/mesa_01_velxio.ino`. Abra esse arquivo no Bloco de Notas, copie o conteúdo e substitua o `sketch.ino` do ESP32 DevKit V1 que você já criou no Velxio. Preserve o circuito atual.

**Não publique o arquivo `privado/mesa_01_velxio.ino`: ele contém o token secreto da mesa 01.**

## Passo 4 — executar no Velxio

1. Clique Play e abra Serial.
2. Espere `WiFi conectado`.
3. Se a rota funcionar, não haverá `POLL: HTTP ...` repetido. `POLL: HTTP -1` normalmente indica falha de conexão/DNS.
4. Abra `http://127.0.0.1:8765/mesa/01` no **mesmo Windows**, gere a cobrança fictícia e clique `Simular Pix aprovado`.
5. O Serial deverá informar `Pagamento de TESTE confirmado. Pressione o botao.`
6. Pressione o botão virtual conectado a D27/GND no Velxio.
7. Confira no Serial `FICHAS LIBERADAS` + `Saida desligada` + `ACK: HTTP 200`.
8. No painel a compra muda de `PAGO` para `LIBERADO`.
9. Sem outro pagamento, pressionar novamente não deve liberar outra vez.

## Se falhar a conectividade do ESP32 virtual

O Velxio documenta Wi-Fi emulado com NAT/SLIRP, mas **a rota exata até `host.docker.internal` depende da versão, DNS do Docker e rede do seu PC**. Ainda não foi executada nesta máquina.

Experimentos de diagnóstico (uma alteração por vez):

- Confirmar que o Docker chega no servidor: `docker exec velxio curl -v --max-time 5 http://host.docker.internal:8765/api/health`.
- Se o Docker consegue e o ESP32 dá `HTTP -1`, pode ser DNS do emulador. Investigar resolução QEMU/SLIRP, sem mudar o firewall do Windows prematuramente.
- Se a rota do NAT oferecer `10.0.2.2` como host QEMU, verificar primeiro se existe algum serviço ouvindo em `10.0.2.2:8765` no espaço de rede correspondente. Não é necessariamente o Windows.
- Em último caso, usar um endereço de teste acessível ao QEMU e não expor tokens de dispositivos na internet.

Não compre plano Maker antes de confirmar a limitação específica da instância Docker.

## Segurança e limitações do experimento

- Aprovações fictícias e cancelamentos só são aceitos de `127.0.0.1`/`::1`.
- O backend escuta somente `127.0.0.1` (salvo configuração explicita diferente); não possui interface de administração segura para público externo.
- Entre ESP32 e API ainda há **HTTP simples** — aceitável apenas no ambiente isolado de testes sem dinheiro. Para uma mesa física, use rede IoT isolada e valide TLS, credenciais e autorização.
- A persistência NVS marca a tentativa antes do pulso para evitar repetição automática após reset. Em perda de energia no meio do pulso, o estado pode ficar INCERTO: é necessário conciliar manualmente e eventualmente emitir um novo comando. Não existe garantia de execução física exatamente uma vez.
- Dependemos do PC ficar ligado, do Wi-Fi, da energia e da rede; plano operacional deve prever liberação manual e recuperação de pagamentos.
- QR Code fixo aponta para a página web local. **Cliente só acessa essa página se estiver conectado à rede que alcança o servidor**. Para Pix verdadeiro, o backend precisa internet para consultar o provedor, mas não precisa necessariamente receber webhooks externos se usar reconciliação de cobranças por polling autenticado.
