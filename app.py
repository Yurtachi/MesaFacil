"""MesaFacil - ponto de entrada. `python app.py` inicia o servidor local.

Pagamentos sao FICTICIOS no modo padrao (PAYMENT_MODE=demo). Veja README.md e docs/.
"""
import getpass
import sys

from mesafacil import db, security
from mesafacil.server import serve

if __name__ == '__main__':
    if '--senha-admin' in sys.argv:
        db.init()
        pwd = getpass.getpass('Nova senha do administrador (mín. 8 caracteres): ')
        if pwd != getpass.getpass('Repita a senha: '):
            raise SystemExit('As senhas não conferem')
        security.set_admin_password(pwd)
        print('Senha atualizada.')
    else:
        serve()
