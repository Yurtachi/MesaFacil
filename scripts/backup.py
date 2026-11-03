"""Backup consistente do banco (API de backup do SQLite; seguro com o servidor rodando).

Uso: python scripts/backup.py [pasta_destino]   (padrão: ./backups)
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mesafacil.config import settings  # noqa: E402

dest = Path(sys.argv[1] if len(sys.argv) > 1 else 'backups')
dest.mkdir(parents=True, exist_ok=True)
target = dest / f'mesafacil-{datetime.now():%Y%m%d-%H%M%S}.sqlite3'
src = sqlite3.connect(settings.db)
out = sqlite3.connect(target)
src.backup(out)
out.close()
src.close()
print(f'Backup criado: {target}\nGuarde também o arquivo de chaves se precisar reaproveitar os firmwares: {settings.keys}')
