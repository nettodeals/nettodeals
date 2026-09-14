FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 nettodeals \
    && useradd --uid 10001 --gid nettodeals --no-create-home --shell /usr/sbin/nologin nettodeals \
    && mkdir -p /data \
    && chown nettodeals:nettodeals /data

COPY requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt

COPY --chown=nettodeals:nettodeals main.py ./
COPY --chown=nettodeals:nettodeals nettodeals ./nettodeals

USER nettodeals
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

