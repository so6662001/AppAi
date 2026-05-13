FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev gcc && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e . --root-user-action=ignore

COPY src ./src
ENV TZ=Asia/Shanghai
EXPOSE 8100

CMD ["uvicorn", "report_scheduler.app:app", "--host", "0.0.0.0", "--port", "8100"]
