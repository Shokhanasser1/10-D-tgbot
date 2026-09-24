FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# A new named volume copies /data/media's owner, so the app user can write product photos.
RUN chmod +x docker-entrypoint.sh \
    && adduser --disabled-password --no-create-home --gecos "" app \
    && mkdir -p /data/media && chown app /data/media

USER app

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
