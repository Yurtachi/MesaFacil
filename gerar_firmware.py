"""Gera sketch local personalizado. Nunca divulgue o sketch com token."""
import argparse
import re
from pathlib import Path
import app

parser = argparse.ArgumentParser(description='Gerador de firmware MesaFacil Velxio (apenas testes)')
parser.add_argument('--mesa', default='01')
parser.add_argument('--servidor', default='http://host.docker.internal:8765')
args = parser.parse_args()
if args.mesa not in app.TABLES: parser.error('Mesa invalida')
if not re.fullmatch(r'https?://[a-zA-Z0-9.:-]+',args.servidor):
    parser.error('Servidor invalido: use http://host.docker.internal:8765 ou IP:porta (sem caminho)')
app.init()
template = (app.BASE/'velxio'/'sketch_template.ino').read_text(encoding='utf-8')
source = template.replace('{{SERVER}}', args.servidor.rstrip('/')).replace('{{MESA}}',args.mesa).replace('{{TOKEN}}',app.TOKENS[args.mesa])
out=app.BASE/'privado'/(f'mesa_{args.mesa}_velxio.ino')
out.parent.mkdir(exist_ok=True)
out.write_text(source,encoding='utf-8')
print(f'Arquivo gerado: {out}\nNao envie esse arquivo para repositorios publicos: ele contem credencial da mesa.')
