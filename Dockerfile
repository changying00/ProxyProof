# ProxyProof 生产镜像：APP_ENV=prod、gevent 起 API、日志直接输出到 stdout（docker logs 看）
# 注意：不要加 `# syntax=docker/dockerfile:1` —— 那会让 BuildKit 去 Docker Hub 拉
# frontend 镜像，auth.docker.io 在国内网络经常不通，构建直接超时。


FROM python:3.12-slim

WORKDIR /app

# 一次性装好依赖并利用层缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 日志不写文件，直接打 stdout——`docker logs` 就能看
ENV APP_ENV=prod \
    ENABLE_LOG_FILE=false \
    PYTHONUNBUFFERED=1

# 非 root 用户运行
RUN useradd -r -u 10001 -g nogroup appuser && \
    mkdir -p /app/logs && \
    chown -R appuser:nogroup /app
USER appuser

EXPOSE 5555

CMD ["python", "run.py"]
