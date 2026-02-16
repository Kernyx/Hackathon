FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim

RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=app:app . .

USER app
EXPOSE 8083
CMD ["python", "app.py"]
