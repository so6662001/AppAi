FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY src ./src
COPY ../_shared /opt/shared
ENV PYTHONPATH=/app/src:/opt/shared
RUN pip install --no-cache-dir -e .
EXPOSE 8950
CMD ["uvicorn", "commission_service.app:app", "--host", "0.0.0.0", "--port", "8950"]
