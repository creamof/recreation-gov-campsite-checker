# Trailhead — single-service image: FastAPI serves the API, the watcher
# poller, and the built PWA from one always-on process.
#
# Build from the repo root:   docker build -f app/Dockerfile -t trailhead app
# Run:                        docker run -p 8000:8000 -v trailhead-data:/data trailhead

# --- stage 1: build the frontend ---
FROM node:22-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- stage 2: the service ---
FROM python:3.12-slim
WORKDIR /srv/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /build/dist /srv/frontend/dist

# Watches + push subscriptions persist here — mount a volume at /data.
ENV TRAILHEAD_DATA_DIR=/data \
    FRONTEND_DIST=/srv/frontend/dist \
    PORT=8000
VOLUME /data
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
