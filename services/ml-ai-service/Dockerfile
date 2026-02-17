# ── Stage 1: установка зависимостей ──
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ python3-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Stage 2: минимальный runtime ──
FROM python:3.12-slim

LABEL maintainer="hackathon-ml"

RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 procps && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app

COPY . .

# Создаём директорию для ChromaDB
RUN mkdir -p /app/data/chroma_db

RUN groupadd -r ml && useradd -r -g ml -d /app ml && \
    chown -R ml:ml /app
USER ml

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

CMD ["python", "main.py"]
