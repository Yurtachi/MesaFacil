"""Cliente do ESP32 emulado do Velxio (QEMU real) via WebSocket /api/simulation/ws, sem navegador.

Dois modos:
  Emu(...)          -> Velxio padrao (stop/start = flash NOVA, NVS apagada).
  EmuPersist(...)   -> mesmo worker QEMU do Velxio, mas com copia do worker em /tmp do container que
                       mantem o arquivo de flash entre reinicios (para testar a NVS). Veja o relatorio.
Dependencia: pip install websockets (use --target fora do repositorio e ponha em PYTHONPATH).
"""
import base64
import json
import subprocess
import threading
import time
import uuid

PIN_BUTTON, PIN_RELAY, PIN_LED = 27, 26, 2


class _Base:
    def __init__(self, fw_b64):
        self.fw = fw_b64
        self.lock = threading.Lock()
        self.serial = ''          # texto acumulado da UART0
        self.gpio = []            # (t, pin, estado)
        self.t0 = time.time()
        self.events = []

    # ---- consulta
    def mark(self):
        with self.lock:
            return len(self.serial)

    def text_since(self, mark=0):
        with self.lock:
            return self.serial[mark:]

    def wait_for(self, needle, timeout=30, since=0):
        end = time.time() + timeout
        while time.time() < end:
            if needle in self.text_since(since):
                return True
            time.sleep(0.1)
        return False

    def pulses(self):
        """Lista de (t_inicio, duracao_s) em que GPIO26 ficou em nivel BAIXO."""
        out, start = [], None
        with self.lock:
            ev = list(self.gpio)
        for t, pin, st in ev:
            if pin != PIN_RELAY:
                continue
            if st == 0 and start is None:
                start = t
            elif st == 1 and start is not None:
                if t - start >= 0.1:      # ignora o glitch de ~50 us do boot (GPIO26 vai a 0 e volta a 1 ao configurar o pino)
                    out.append((start, t - start))
                start = None
        if start is not None:
            out.append((start, None))
        return out

    def press(self, hold=0.6):
        # o botao do circuito tem pull-up e comeca solto: garante nivel ALTO antes da borda de descida
        self.set_pin(PIN_BUTTON, 1)
        time.sleep(0.5)
        self.set_pin(PIN_BUTTON, 0)
        time.sleep(hold)
        self.set_pin(PIN_BUTTON, 1)

    def _on_event(self, ev):
        typ, data = ev.get('type'), ev.get('data', {})
        with self.lock:
            if typ == 'serial_output' and data.get('uart', 0) == 0:
                self.serial += data.get('data', '')
            elif typ == 'gpio_change':
                self.gpio.append((time.time() - self.t0, data.get('pin'), data.get('state')))
            else:
                self.events.append(ev)


class Emu(_Base):
    def __init__(self, fw_b64, host='localhost:3080'):
        super().__init__(fw_b64)
        from websockets.sync.client import connect
        self.cid = 'qa-' + uuid.uuid4().hex[:8]
        self.ws = connect(f'ws://{host}/api/simulation/ws/{self.cid}', max_size=None)
        self.alive = True
        threading.Thread(target=self._reader, daemon=True).start()

    def _reader(self):
        try:
            for raw in self.ws:
                self._on_event(json.loads(raw))
        except Exception:
            pass
        self.alive = False

    def _send(self, typ, data):
        self.ws.send(json.dumps({'type': typ, 'data': data}))

    def start(self):
        self.t0 = time.time()
        self._send('start_esp32', {'board': 'esp32', 'firmware_b64': self.fw, 'wifi_enabled': True})

    def stop(self):
        self._send('stop_esp32', {})

    def set_pin(self, pin, state):
        self._send('esp32_gpio_in', {'pin': pin, 'state': state})

    def close(self):
        try:
            self.stop()
            time.sleep(0.5)
            self.ws.close()
        except Exception:
            pass


WORKER_COPY = '/tmp/svc/esp32_worker_persist.py'
FLASH_FILE = '/tmp/mesafacil_flash.bin'


class EmuPersist(_Base):
    """Worker do Velxio executado por `docker exec -i`, com a flash num arquivo fixo (persistente entre reinicios)."""

    def __init__(self, fw_b64, wifi=True):
        super().__init__(fw_b64)
        self.proc = None
        self.wifi = wifi
        self.crash_armed = False   # se True, mata o QEMU (SIGKILL) no instante em que GPIO26 vai a nivel BAIXO
        self.crashed_at = None
        self.helper = None

    def start(self, fresh_flash=False):
        if fresh_flash:
            subprocess.run(['docker', 'exec', 'velxio', 'rm', '-f', FLASH_FILE], check=False)
        self.t0 = time.time()
        with self.lock:
            self.gpio = []      # contagem de pulsos por partida
        self.crash_armed = False
        if self.helper is None or self.helper.poll() is not None:   # shell ja aberto: pkill sem latencia de 'docker exec'
            self.helper = subprocess.Popen(['docker', 'exec', '-i', 'velxio', 'sh'], stdin=subprocess.PIPE,
                                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.proc = subprocess.Popen(['docker', 'exec', '-i', 'velxio', 'python3', WORKER_COPY],
                                     stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        cfg = {'lib_path': '/app/lib/libqemu-xtensa.so', 'firmware_b64': self.fw, 'machine': 'esp32-picsimlab',
               'sensors': [], 'wifi_enabled': self.wifi, 'wifi_hostfwd_port': 0}
        self.proc.stdin.write((json.dumps(cfg) + '\n').encode())
        self.proc.stdin.flush()
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()

    def _reader(self, proc):
        ubuf = bytearray()
        for line in proc.stdout:
            line = line.strip()
            i = line.find(b'{"type":')
            if i < 0:
                continue
            try:
                ev = json.loads(line[i:])
            except ValueError:
                continue
            typ = ev.get('type')
            if typ == 'uart_tx' and ev.get('uart', 0) == 0:
                ubuf.append(ev.get('byte', 0) & 0xFF)
                if ev.get('byte') == 10:
                    with self.lock:
                        self.serial += bytes(ubuf).decode('utf-8', 'replace')
                    ubuf.clear()
            elif typ == 'gpio_change':
                with self.lock:
                    self.gpio.append((time.time() - self.t0, ev.get('pin'), ev.get('state')))
                if self.crash_armed and ev.get('pin') == PIN_RELAY and ev.get('state') == 0:
                    self.crash_armed = False
                    self.crashed_at = time.time() - self.t0
                    self.helper.stdin.write(b'pkill -9 -f esp32_worker_persist' + bytes([10]))
                    self.helper.stdin.flush()

    def _cmd(self, obj):
        if self.proc and self.proc.poll() is None:
            self.proc.stdin.write((json.dumps(obj) + '\n').encode())
            self.proc.stdin.flush()

    def set_pin(self, pin, state):
        self._cmd({'cmd': 'set_pin', 'pin': pin, 'value': state})

    def stop(self, kill=False):
        """kill=True simula perda de energia (SIGKILL no QEMU, sem 'stop' limpo)."""
        if not self.proc:
            return
        if kill:
            subprocess.run(['docker', 'exec', 'velxio', 'pkill', '-9', '-f', WORKER_COPY], check=False)
        else:
            self._cmd({'cmd': 'stop'})
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()
        self.proc = None

    def close(self):
        self.stop()
        if self.helper and self.helper.poll() is None:
            self.helper.kill()
