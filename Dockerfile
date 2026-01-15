FROM python:3.11-slim

WORKDIR /app

# تثبيت المكتبات المطلوبة فقط
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# إنشاء مجلد tmp (لو احتجنا في المستقبل)
RUN mkdir -p /tmp && chmod 777 /tmp

ENV PORT=10000

# تحديد حد الذاكرة للـ Python garbage collector
ENV PYTHONUNBUFFERED=1
ENV PYTHONMALLOC=malloc

EXPOSE 10000

# تشغيل مع إعدادات محسّنة للذاكرة
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
