FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY artifacts/research/jamp_task_scoped_derived_matrix_v2.json ./artifacts/research/jamp_task_scoped_derived_matrix_v2.json
COPY data/projections/pilot_models.json ./data/projections/pilot_models.json
COPY tests/fixtures/runtime_evidence_projection.json ./data/runtime_evidence_projection.json
COPY --from=frontend-build /frontend/dist/ ./frontend-dist/

RUN python -m pip install --no-cache-dir . "uvicorn>=0.30,<1"

ENV PYTHONUNBUFFERED=1
ENV JAMP_EVIDENCE_PATH=/app/data/runtime_evidence_projection.json
ENV JAMP_CAPABILITY_MATRIX_PATH=/app/artifacts/research/jamp_task_scoped_derived_matrix_v2.json
ENV JAMP_PILOT_MODELS_PATH=/app/data/projections/pilot_models.json
ENV JAMP_FRONTEND_DIST=/app/frontend-dist
EXPOSE 8000

CMD ["uvicorn", "jamp.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
