FROM python:3.11-slim

WORKDIR /app

# تثبيت المكتبات المطلوبة
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ ملف البوت
COPY bot.py .

# تشغيل البوت
CMD ["python", "bot.py"]
