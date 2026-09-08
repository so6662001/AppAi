FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY src ./src
RUN pip install --no-cache-dir -e .
EXPOSE 8970
CMD ["uvicorn", "role_insight.app:app", "--host", "0.0.0.0", "--port", "8970"]
