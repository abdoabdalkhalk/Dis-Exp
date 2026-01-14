# استخدام Python 3.11 slim
FROM python:3.11-slim

# تعيين مجلد العمل
WORKDIR /app

# نسخ ملفات المتطلبات
COPY requirements.txt .

# تثبيت المكتبات
RUN pip install --no-cache-dir -r requirements.txt

# نسخ كل الملفات
COPY . .

# إنشاء مجلد tmp للملفات المؤقتة
RUN mkdir -p /tmp

# تعيين متغير البيئة للمنفذ
ENV PORT=10000

# فتح المنفذ
EXPOSE 10000

# تشغيل التطبيق مع timeout 15 دقيقة للملفات الكبيرة
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 900 --keep-alive 5 --graceful-timeout 900 discord_uploader:app
