FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

RUN python -m pip install --no-cache-dir . "uvicorn>=0.30,<1"

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "jamp.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
