FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh \
    && adduser --disabled-password --no-create-home --gecos "" app

USER app

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
