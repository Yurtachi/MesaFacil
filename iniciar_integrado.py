"""Inicializa backend e simuladores Python para mesas 02-10; mesa 01 é exclusiva do ESP32 Velxio."""
from app import serve
from sim_esp32 import start

if __name__ == '__main__':
    start([f'{i:02}' for i in range(2,11)])
    print('Mesa 01 reservada para o ESP32 no Velxio. NENHUM simulador Python da Mesa 01 será iniciado.', flush=True)
    serve()
