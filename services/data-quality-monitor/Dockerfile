FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e . --root-user-action=ignore
COPY src ./src
ENV TZ=Asia/Shanghai
EXPOSE 8900
CMD ["uvicorn","dq_monitor.app:app","--host","0.0.0.0","--port","8900"]
