FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有代码
COPY . .

# 创建数据目录
RUN mkdir -p /app/data

# 只启动网页版（不启动 Discord）
CMD ["python", "web.py"]
