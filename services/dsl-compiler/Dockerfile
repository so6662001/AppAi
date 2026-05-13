FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e . --root-user-action=ignore

COPY src ./src
COPY ../../metrics ./metrics

ENV METRICS_DIR=/app/metrics
EXPOSE 8000

CMD ["uvicorn", "dsl_compiler.app:app", "--host", "0.0.0.0", "--port", "8000"]
