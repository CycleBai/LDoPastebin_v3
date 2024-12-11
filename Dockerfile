# 使用 Alpine 基础镜像
FROM python:3.9-alpine

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apk add --no-cache \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev \
    openssl-dev \
    && rm -rf /var/cache/apk/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 创建数据目录
RUN mkdir -p /app/data

# 复制应用代码
COPY . .

# 设置环境变量
ENV FLASK_APP=app.py \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 暴露端口
EXPOSE 8181

# 使用非 root 用户运行应用
RUN adduser -D appuser
RUN chown -R appuser:appuser /app
USER appuser

# 启动命令
CMD ["python", "app.py"] 