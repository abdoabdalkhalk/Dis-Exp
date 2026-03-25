FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /tmp && chmod 777 /tmp

ENV PORT=10000

ENV PYTHONUNBUFFERED=1
ENV PYTHONMALLOC=malloc

EXPOSE 10000

CMD gunicorn --bind 0.0.0.0:$PORT \
    --workers 1 \
    --threads 4 \
    --timeout 0 \
    --graceful-timeout 0 \
    --keep-alive 75 \
    --worker-class sync \
    --max-requests 100 \
    --max-requests-jitter 10 \
    --worker-tmp-dir /dev/shm \
    discord_uploader:app
