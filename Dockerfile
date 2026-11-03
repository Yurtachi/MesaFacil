FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOST=0.0.0.0 PORT=8765 \
    SINUCA_DB=/data/mesafacil.sqlite3 SINUCA_KEYS=/data/device_keys.json
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd -r -u 10001 mesafacil && mkdir /data && chown mesafacil /data
COPY app.py ./
COPY mesafacil ./mesafacil
COPY web ./web
USER mesafacil
VOLUME /data
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request,os;urllib.request.urlopen('http://127.0.0.1:'+os.environ['PORT']+'/api/health',timeout=2)"
CMD ["python", "app.py"]
