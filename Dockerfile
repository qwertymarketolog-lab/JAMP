FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
COPY artifacts/research/jamp_task_scoped_derived_matrix_v2.json ./artifacts/research/jamp_task_scoped_derived_matrix_v2.json
COPY data/projections/pilot_models.json ./data/projections/pilot_models.json
COPY tests/fixtures/runtime_evidence_projection.json ./data/runtime_evidence_projection.json

RUN python -m pip install --no-cache-dir . "uvicorn>=0.30,<1"

ENV PYTHONUNBUFFERED=1
ENV JAMP_EVIDENCE_PATH=/app/data/runtime_evidence_projection.json
ENV JAMP_CAPABILITY_MATRIX_PATH=/app/artifacts/research/jamp_task_scoped_derived_matrix_v2.json
ENV JAMP_PILOT_MODELS_PATH=/app/data/projections/pilot_models.json
EXPOSE 8000

CMD ["uvicorn", "jamp.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
