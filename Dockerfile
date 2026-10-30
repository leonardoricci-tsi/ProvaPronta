# syntax=docker/dockerfile:1

# --- Stage 1: build do frontend Angular ---
# Node 24 porque o Angular CLI 21 exige >=24.0 (ou ^20.19/^22.12) — mesma
# versão usada em desenvolvimento (ver README).
FROM node:24-slim AS frontend-build
WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# outputPath do angular.json é "../app/static" (relativo a /build/frontend),
# então o build cai em /build/app/static.
RUN npm run build


# --- Stage 2: backend FastAPI + build do frontend já pronto ---
FROM python:3.13-slim AS backend
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
# DDL do domínio (db/001_dominio.sql): a migration do Alembic lê de lá.
COPY db/ ./db/

# Substitui o app/static do código-fonte pelo build de produção do Angular
# gerado no stage anterior (index.html/JS/CSS com hash + 404.html de fallback).
COPY --from=frontend-build /build/app/static ./app/static

# DATABASE_URL e JWT_SECRET vêm de variáveis de ambiente na
# hora do `docker run` (-e ou --env-file) — nunca copiadas pra dentro da imagem.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
