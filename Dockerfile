FROM python:3.10-slim

RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 同时启动 bot.py 和 web.py
CMD ["python", "bot.py"]
