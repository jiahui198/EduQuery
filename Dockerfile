FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    TZ=Asia/Shanghai

WORKDIR /app

# libgomp1 是 milvus-lite 的运行时依赖；curl 用于容器健康检查
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# 先用依赖清单装包，代码改动时可复用这一层缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

COPY src ./src
COPY frontend ./frontend

RUN mkdir -p /app/data/uploads /app/logs

EXPOSE 8001

CMD ["uvicorn", "eduquery.main:app", "--host", "0.0.0.0", "--port", "8001", "--proxy-headers", "--forwarded-allow-ips", "*"]
