# syntax=docker/dockerfile:1

FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Europe/Madrid \
    ENERGYHUB_DATA_DIR=/data \
    ENERGYHUB_STATIC_DIR=/app/static
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY CHANGELOG.md ./CHANGELOG.md
COPY tariffs ./tariffs
COPY --from=frontend /build/dist ./static
EXPOSE 8099
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8099/api/health', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8099", "--proxy-headers", "--forwarded-allow-ips", "*"]
