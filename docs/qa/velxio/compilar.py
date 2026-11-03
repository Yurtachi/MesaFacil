"""Compila um sketch no Velxio (API HTTP /api/compile/start) e salva o firmware base64.

Uso: python compilar.py <sketch.ino> <saida_dir>   (saida_dir FORA do repositorio: contem token no binario)
Salva: <saida_dir>/firmware.b64 e <saida_dir>/compile_log.txt (stdout/stderr do compilador; sem o sketch).
"""
import json
import sys
import time
import urllib.request

BASE = 'http://localhost:3080/api/compile'


def post(path, obj):
    req = urllib.request.Request(BASE + path, data=json.dumps(obj).encode(), headers={'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=60).read().decode('utf-8-sig'))


def get(path):
    return json.loads(urllib.request.urlopen(BASE + path, timeout=60).read().decode('utf-8-sig'))


def main():
    src = open(sys.argv[1], encoding='utf-8').read()
    out = sys.argv[2]
    job = post('/start', {'files': [{'name': 'sketch.ino', 'content': src}], 'board_fqbn': 'esp32:esp32:esp32'})
    jid = job['job_id']
    t0 = time.time()
    while True:
        st = get(f'/status/{jid}')
        if st['state'] in ('done', 'error'):
            break
        time.sleep(3)
    res = st.get('result') or {}
    log = f"estado={st['state']} duracao={time.time() - t0:.0f}s success={res.get('success')} error={res.get('error')}\n--- stdout ---\n{res.get('stdout') or st.get('stdout')}\n--- stderr ---\n{res.get('stderr')}\n"
    open(out + '/compile_log.txt', 'w', encoding='utf-8').write(log)
    fw = res.get('binary_content') or res.get('hex_content')
    if res.get('success') and fw:
        open(out + '/firmware.b64', 'w').write(fw)
    print(log[-3000:])
    print('has_wifi', res.get('has_wifi'), 'firmware_b64_len', len(fw or ''))
    return 0 if res.get('success') else 1


sys.exit(main())
