"""Infraestrutura dos casos: servidor MesaFacil de teste (porta propria, DB/chaves temporarios), log redigido."""
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TMP = Path(os.environ['MF_TMP'])
PORT = os.environ.get('MF_PORT', '8777')
LOGDIR = Path(__file__).resolve().parent / 'logs'
LOGDIR.mkdir(exist_ok=True)
NOISE = re.compile(r'^W \(\d+\) periph_ctrl.*$', re.M)
TOKEN_RX = re.compile(r'[\w-]{43}')


def clean(text):
    return TOKEN_RX.sub('<TOKEN>', NOISE.sub('', text)).replace('\r', '')


class Log:
    def __init__(self, name):
        self.f = open(LOGDIR / f'{name}.txt', 'w', encoding='utf-8')

    def __call__(self, *a):
        line = clean(' '.join(str(x) for x in a))
        print(line, flush=True)
        self.f.write(line + '\n')
        self.f.flush()

    def block(self, title, text):
        self('--- ' + title + ' ---')
        text = '\n'.join(l for l in clean(text).split('\n') if l.strip())
        self(text)
        self('--- fim ---')


class Server:
    def __init__(self):
        self.p = None

    def env(self):
        e = dict(os.environ)
        e.update(PYTHONIOENCODING='utf-8', SINUCA_DB=str(TMP / 'db.sqlite3'), SINUCA_KEYS=str(TMP / 'keys.json'),
                 PORT=PORT, HOST='127.0.0.1', ADMIN_PASSWORD='qa-velxio-pass-123')
        return e

    def start(self):
        if self.p and self.p.poll() is None:
            return
        self.out = open(TMP / 'srv.log', 'ab')
        self.p = subprocess.Popen([sys.executable, '-u', 'app.py'], cwd=REPO, env=self.env(), stdout=self.out, stderr=self.out)
        for _ in range(50):
            time.sleep(0.2)
            try:
                import urllib.request
                urllib.request.urlopen(f'http://127.0.0.1:{PORT}/api/health', timeout=1)
                return
            except Exception:
                pass
        raise RuntimeError('servidor nao subiu')

    def stop(self):
        if self.p and self.p.poll() is None:
            self.p.terminate()
            try:
                self.p.wait(5)
            except Exception:
                self.p.kill()
        self.p = None
