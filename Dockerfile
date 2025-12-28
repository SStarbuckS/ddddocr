FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
RUN pip install --no-cache-dir \
    ddddocr \
    flask \
    gunicorn

# 复制应用代码
COPY app.py .

# 创建模型目录
RUN mkdir -p /app/models

# 暴露端口
EXPOSE 8080

# 启动服务（WORKERS 环境变量可配置 worker 数量，默认 1）
CMD ["sh", "-c", "gunicorn -w ${WORKERS:-1} -b 0.0.0.0:8080 --timeout 60 app:app"]
