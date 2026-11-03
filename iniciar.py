"""Servidor + simuladores de ESP32 para as mesas do arquivo de chaves (demonstração sem hardware)."""
import json
import sys
import threading

from mesafacil import db
from mesafacil.config import settings
from mesafacil.server import serve
from sim_esp32 import start

if __name__ == '__main__':
    skip = {'01'} if '--sem-mesa-01' in sys.argv else set()  # mesa 01 reservada ao ESP32 do Velxio
    db.init()
    keys = json.loads(settings.keys.read_text(encoding='utf-8'))
    threading.Timer(1.5, start, args=([m for m in sorted(keys) if m not in skip],)).start()
    serve()
