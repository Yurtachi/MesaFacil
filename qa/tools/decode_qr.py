"""Lê os QR codes das capturas das placas (OpenCV) e confere se apontam para /mesa/NN. Uso: python qa/tools/decode_qr.py <png>..."""
import re
import sys

import cv2

bad = 0
for path in sys.argv[1:]:
    ok, info, _, _ = cv2.QRCodeDetector().detectAndDecodeMulti(cv2.imread(path))
    urls = [i for i in info if i]
    good = sorted(m.group(1) for u in urls if (m := re.search(r'/mesa/(\d{2,4})$', u)))
    print(f'{path}: {len(good)} QR lidos {good}')
    bad += 0 if ok and len(good) == len(urls) and urls else 1
sys.exit(bad)
