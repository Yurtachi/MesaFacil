"""Teste da integracao Velxio sem emulador real: valida o contrato HTTP do firmware."""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]

class FirmwareContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0)); cls.port=sock.getsockname()[1]
        cls.url=f'http://127.0.0.1:{cls.port}'
        env=os.environ.copy()
        env.update(HOST='127.0.0.1',PORT=str(cls.port),SINUCA_DB=str(Path(cls.tmp.name)/'database.sqlite3'),SINUCA_KEYS=str(Path(cls.tmp.name)/'keys.json'))
        cls.p=subprocess.Popen([sys.executable,'app.py'],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(80):
            try:
                with urlopen(cls.url+'/api/health',timeout=.5) as r:
                    if json.load(r)['status']=='ok':break
            except (URLError,TimeoutError):time.sleep(.05)
        else: raise AssertionError('Servidor nao subiu')
        cls.tokens=json.loads(Path(env['SINUCA_KEYS']).read_text(encoding='utf-8'))

    @classmethod
    def tearDownClass(cls):
        cls.p.terminate(); cls.p.wait(timeout=5); cls.tmp.cleanup()

    def request(self,path,data=None,token=None):
        headers={}
        if data is not None:headers['Content-Type']='application/json'
        if token: headers['Authorization']='Bearer '+token
        request=Request(self.url+path,headers=headers,data=None if data is None else json.dumps(data).encode())
        try:
            with urlopen(request,timeout=3) as r: return r.status,r.read().decode().strip()
        except HTTPError as e: return e.code,e.read().decode().strip()

    def test_esp32_api_command_ack(self):
        token=self.tokens['01']
        self.assertEqual(self.request('/api/dispositivos/01/proximo.txt',token=token),(200,'NONE'))
        self.assertEqual(self.request('/api/dispositivos/01/proximo.txt')[0],401)
        self.assertEqual(self.request('/api/dispositivos/02/proximo.txt',token=token)[0],401)
        status,response=self.request('/api/pedidos',{'mesa':'01'}); self.assertEqual(status,201)
        order=json.loads(response)['pedido']
        self.assertEqual(self.request('/api/dispositivos/01/proximo.txt',token=token),(200,'NONE'))
        self.assertEqual(self.request('/api/demo/pagar',{'pedido':order})[0],200)
        status,cmd=self.request('/api/dispositivos/01/proximo.txt',token=token)
        self.assertEqual(status,200); self.assertEqual(len(cmd),36)
        self.assertEqual(self.request('/api/dispositivos/01/proximo.txt',token=token),(200,cmd))
        self.assertEqual(self.request('/api/dispositivos/02/confirmar',{'comando':cmd},self.tokens['02'])[0],404)
        self.assertEqual(self.request('/api/dispositivos/01/confirmar',{'comando':cmd},token)[0],200)
        self.assertEqual(self.request('/api/dispositivos/01/confirmar',{'comando':cmd},token)[0],200)
        self.assertEqual(self.request('/api/dispositivos/01/proximo.txt',token=token),(200,'NONE'))
        self.assertEqual(json.loads(self.request('/api/pedidos/'+order)[1])['status'],'LIBERADO')

if __name__=='__main__':unittest.main()
