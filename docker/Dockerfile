# fabriq backend image, without FreeCAD. The FreeCAD image for online wrap
# jobs comes with the online slice (a FreeCAD AppImage under xvfb-run).
#
#   docker build -f docker/Dockerfile -t fabriq .
#   docker run -p 8765:8765 -v /path/to/machine:/workspace fabriq
FROM node:24-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git git-lfs gh && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY fabriq/ ./fabriq/
COPY --from=frontend /src/fabriq/static/ ./fabriq/static/
RUN uv sync --no-dev --frozen
ENV FABRIQ_HOST=0.0.0.0 FABRIQ_PORT=8765 FABRIQ_NO_BROWSER=1
EXPOSE 8765
VOLUME ["/workspace"]
CMD ["uv", "run", "fabriq", "--root", "/workspace"]
