FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /tmp && chmod 777 /tmp

ENV PORT=10000

EXPOSE 10000

# بدون timeout - يشتغل بدون حدود
CMD gunicorn --bind 0.0.0.0:$PORT \
    --workers 2 \
    --threads 8 \
    --timeout 0 \
    --graceful-timeout 0 \
    --keep-alive 75 \
    --worker-class sync \
    discord_uploader:app