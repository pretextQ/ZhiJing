FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY frontend/src/ ./src/
RUN npm run build

FROM python:3.11-slim-bookworm AS python-deps
WORKDIR /build
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never
RUN python -m pip install --no-cache-dir uv==0.11.7
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.11-slim-bookworm AS runtime
WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ZHIJING_STUDY_DATABASE=/data/study.sqlite3
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin zhijing \
    && install -d -o zhijing -g zhijing /data
COPY --from=python-deps /opt/venv /opt/venv
COPY backend/zhijing/ ./backend/zhijing/
COPY --from=frontend-build /build/dist ./frontend/dist
USER zhijing
EXPOSE 18081
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
    CMD ["python", "-c", "from urllib.request import urlopen; urlopen('http://127.0.0.1:18081/', timeout=2).close()"]
CMD ["python", "-m", "uvicorn", "zhijing.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "18081"]
