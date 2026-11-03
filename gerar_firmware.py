"""Gera sketch local personalizado com a credencial da mesa. NUNCA publique o arquivo gerado."""
import argparse
import json
import re

from mesafacil.config import BASE, settings

parser = argparse.ArgumentParser(description='Gerador de firmware MesaFacil (Velxio / ESP32)')
parser.add_argument('--mesa', default='01')
parser.add_argument('--servidor', default='http://host.docker.internal:8765')
parser.add_argument('--token', help='credencial da mesa (mostrada ao cadastrar/rotacionar no painel). Padrão: arquivo de chaves.')
args = parser.parse_args()
if not re.fullmatch(r'\d{2,4}', args.mesa):
    parser.error('Mesa inválida')
if not re.fullmatch(r'https?://[a-zA-Z0-9.:-]+', args.servidor):
    parser.error('Servidor inválido: use http://host.docker.internal:8765 ou IP:porta (sem caminho)')
token = args.token
if not token:
    keys = json.loads(settings.keys.read_text(encoding='utf-8')) if settings.keys.exists() else {}
    token = keys.get(args.mesa)
if not token or not re.fullmatch(r'[\w-]{20,64}', token):
    parser.error('Credencial não encontrada: informe --token ou inicie o servidor uma vez para gerar o arquivo de chaves')
template = (BASE / 'velxio' / 'sketch_template.ino').read_text(encoding='utf-8')
source = template.replace('{{SERVER}}', args.servidor.rstrip('/')).replace('{{MESA}}', args.mesa).replace('{{TOKEN}}', token)
out = BASE / 'privado' / f'mesa_{args.mesa}_velxio.ino'
out.parent.mkdir(exist_ok=True)
out.write_text(source, encoding='utf-8')
print(f'Arquivo gerado: {out}\nNão envie esse arquivo a repositórios: ele contém a credencial da mesa.')
