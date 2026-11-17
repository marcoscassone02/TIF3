FROM node:22-alpine AS frontend-builder

WORKDIR /build/app/frontend
COPY app/frontend/package.json app/frontend/package-lock.json ./
RUN npm ci

COPY app/frontend/ ./
RUN npm run build


FROM python:3.11-slim AS application

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    MODEL_STORAGE_DIR=/var/data/models

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/__init__.py ./app/__init__.py
COPY app/backend/ ./app/backend/
COPY --from=frontend-builder /build/app/frontend/dist ./app/frontend/dist

RUN mkdir -p /var/data/models

EXPOSE 10000

CMD ["sh", "-c", "uvicorn app.backend.api:app --host 0.0.0.0 --port ${PORT:-10000}"]
