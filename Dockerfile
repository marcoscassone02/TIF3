FROM node:22-alpine AS frontend-builder

WORKDIR /build/modelo_final/frontend
COPY modelo_final/frontend/package.json modelo_final/frontend/package-lock.json ./
RUN npm ci

COPY modelo_final/frontend/ ./
RUN npm run build


FROM python:3.11-slim AS application

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    MODEL_STORAGE_DIR=/var/data/models

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY modelo_final/__init__.py ./modelo_final/__init__.py
COPY modelo_final/backend/ ./modelo_final/backend/
COPY --from=frontend-builder /build/modelo_final/frontend/dist ./modelo_final/frontend/dist

RUN mkdir -p /var/data/models

EXPOSE 10000

CMD ["sh", "-c", "uvicorn modelo_final.backend.api:app --host 0.0.0.0 --port ${PORT:-10000}"]
