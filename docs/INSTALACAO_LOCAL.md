# Instalação local

Requisitos: Python 3.10+ (testado com 3.12 no Docker e 3.14 no Windows). Opcional: Docker; Node 20+ só para os testes de navegador.

## Windows (PowerShell)

```powershell
git clone https://github.com/Yurtachi/MesaFacil.git
cd MesaFacil
py -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:ADMIN_PASSWORD = "troque-esta-senha"      # só no primeiro início
python iniciar.py                              # servidor + 10 controladores SIMULADOS
```

Atalho: `iniciar_windows.bat`. Abra `http://127.0.0.1:8765/` (cliente) e `/admin` (atendente). Sem `ADMIN_PASSWORD`, uma senha aleatória é exibida **uma vez** no console; troque com `python app.py --senha-admin`.

Só o servidor (sem simuladores, para ESP32 real ou Velxio): `python app.py`. Mesa 01 para o Velxio: `python iniciar_integrado.py` (veja `GUIA_WINDOWS_VELXIO.md`).

## Testar no celular (mesma rede, apenas demonstração)

```powershell
$env:HOST = "0.0.0.0"
$env:PUBLIC_BASE_URL = "http://IP_DO_PC:8765"   # vai nos QR codes
$env:DEMO_REMOTE_PAY = "1"                        # permite aprovar o pagamento FICTÍCIO pelo celular
python iniciar.py
```
Libere a porta 8765 no firewall **somente para a rede privada**. Nunca para a internet.

## Docker

```bash
cp .env.example .env     # edite ADMIN_PASSWORD, PUBLIC_BASE_URL
docker compose up -d --build
```
Dados em volume `mesafacil-data` (`/data`). Contêiner roda como usuário não root e tem `HEALTHCHECK`.

## Firmware

`python gerar_firmware.py --mesa 01 --servidor http://IP_DO_PC:8765` gera `privado/mesa_01_velxio.ino` com a credencial (arquivo ignorado pelo Git). Para mesas novas ou credenciais rotacionadas pelo painel: `--token <credencial exibida uma vez>`. O sketch v0.4 **não foi compilado neste ambiente** (sem toolchain Arduino/Velxio); a mudança em relação ao v0.3 é pequena (cabeçalho, `duracao_ms`, `POST incerto`) e precisa ser compilada e testada no Velxio/ESP32.

## Testes

```bash
python -m unittest discover -s testes -v                 # backend/integração (34)
cd qa && npm ci && npx playwright install chromium && npm test   # visual + axe + E2E (109)
python -m ruff check . && python -m bandit -q -r mesafacil app.py
```
