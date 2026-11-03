"""Restaura um backup. PARE o servidor antes. Uso: python scripts/restore.py caminho/backup.sqlite3"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mesafacil.config import settings  # noqa: E402

if len(sys.argv) != 2:
    raise SystemExit(__doc__)
src = Path(sys.argv[1])
check = sqlite3.connect(src)
if check.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
    raise SystemExit('Backup corrompido: integrity_check falhou')
check.close()
if settings.db.exists():
    keep = settings.db.with_name(settings.db.name + f'.antes-restauracao-{datetime.now():%Y%m%d-%H%M%S}')
    shutil.copy2(settings.db, keep)
    print(f'Banco atual preservado em {keep}')
for suffix in ('-wal', '-shm'):
    Path(str(settings.db) + suffix).unlink(missing_ok=True)
shutil.copy2(src, settings.db)
print('Restaurado. Inicie o servidor e confira o painel.')
