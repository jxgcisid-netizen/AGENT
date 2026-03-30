# 使用官方 Python 3.11 镜像作为基础
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 将 requirements.txt 复制到容器内并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 将项目所有文件复制到容器内
COPY . .

# 暴露健康检查服务的端口（Koyeb和Fly.io要求）
EXPOSE 8000

# 使用启动脚本，同时运行机器人主程序和健康检查服务器
CMD ["sh", "-c", "python bot.py & python health_server.py"]
