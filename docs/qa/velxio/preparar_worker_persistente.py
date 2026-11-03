"""Cria DENTRO do container (em /tmp/svc, nada da imagem e alterado) uma copia do worker QEMU do Velxio cuja flash
e o arquivo fixo /tmp/mesafacil_flash.bin (criado na primeira partida e nao apagado ao parar). Usado por emu.EmuPersist.
Remocao: docker exec velxio sh -c "rm -rf /tmp/svc /tmp/mesafacil_flash.bin"
"""
import subprocess

PATCH = r'''
import re
p = '/tmp/svc/esp32_worker_persist.py'
s = open('/app/app/services/esp32_worker.py').read()
old = """        tmp = tempfile.NamedTemporaryFile(suffix='.bin', delete=False)
        tmp.write(fw_bytes)
        tmp.close()
        firmware_path: str | None = tmp.name"""
new = """        _FLASH = '/tmp/mesafacil_flash.bin'
        if not os.path.exists(_FLASH):
            with open(_FLASH, 'wb') as _f:
                _f.write(fw_bytes)
        firmware_path: str | None = _FLASH"""
assert old in s and 'os.unlink(firmware_path)' in s
s = s.replace(old, new).replace('os.unlink(firmware_path)', 'pass')
open(p, 'w').write(s)
print('worker persistente criado:', p)
'''
subprocess.run(['docker', 'exec', 'velxio', 'sh', '-c', 'rm -rf /tmp/svc && cp -r /app/app/services /tmp/svc'], check=True)
subprocess.run(['docker', 'exec', '-i', 'velxio', 'python3', '-'], input=PATCH.encode(), check=True)
