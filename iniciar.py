"""Uma única execução inicia servidor + 10 ESP32s simulados em software."""
import threading
import time
from sim_esp32 import start
from app import serve

if __name__ == '__main__':
    # As threads do simulador esperam até o backend responder.
    start([f'{i:02}' for i in range(1, 11)])
    serve()
