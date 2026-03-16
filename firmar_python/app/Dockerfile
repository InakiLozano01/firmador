FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=America/Argentina/Tucuman \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Keep the native layer small enough for constrained Docker hosts.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        apache2 \
        apache2-dev \
        gcc \
        make \
        pkg-config \
        libarchive13t64 \
        tzdata \
    && ln -fs /usr/share/zoneinfo/${TZ} /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

RUN pip install --no-cache-dir \
        Flask \
        PyPDF2 \
        Werkzeug \
        cryptography \
        python-dotenv \
        pillow \
        pdfrw \
        psycopg2-binary \
        libarchive-c \
        reportlab \
        redis \
        requests \
        mod_wsgi

WORKDIR /app

RUN mkdir -p /app/assets/images /app/certs/own /var/documentos_firmados /var/documentos

COPY . .

RUN chown -R www-data:www-data /app /var/documentos_firmados /var/documentos \
    && chmod -R 755 /app \
    && chmod 600 /app/certs/own/yunga_private_csr.key

RUN sed -i "s/default=10485760,/default=1048576000,/" /usr/local/lib/python3.12/site-packages/mod_wsgi/server/__init__.py

EXPOSE 5000

CMD ["mod_wsgi-express", "start-server", "/app/config/sign.wsgi", "--reload-on-changes", "--user", "www-data", "--group", "www-data", "--port", "5000"]
