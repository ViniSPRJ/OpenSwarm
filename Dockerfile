FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /app/activity-logs /app/mnt /app/uploads \
    && chmod -R a+rwx /app/activity-logs /app/mnt /app/uploads

COPY . .

EXPOSE 18080

CMD ["python", "-u", "server.py"]
