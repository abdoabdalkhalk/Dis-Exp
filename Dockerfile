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

# تشغيل التطبيق باستخدام gunicorn
CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 300 discord_uploader:app
