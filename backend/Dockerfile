# Multi-stage build for the Canary collector + dashboard.
#
# Stage 1 builds the React SPA. Stage 2 installs the Python backend and copies
# the built assets into its static dir, so the single container serves both the
# /v1 API and the dashboard.

# --- stage 1: build the dashboard -------------------------------------------
FROM node:20-slim AS dashboard
WORKDIR /app/dashboard
COPY dashboard/package*.json ./
RUN npm ci
COPY dashboard/ ./
# Emit straight into the location the backend serves from.
RUN npm run build

# --- stage 2: the server ----------------------------------------------------
FROM python:3.12-slim AS server
WORKDIR /app

COPY backend/ /app/backend/
RUN pip install --no-cache-dir /app/backend

# Bring in the compiled SPA.
COPY --from=dashboard /app/backend/src/canary_server/static /app/static
ENV CANARY_STATIC_DIR=/app/static
ENV CANARY_HOST=0.0.0.0 CANARY_PORT=8732
EXPOSE 8732

CMD ["python", "-m", "canary_server"]
