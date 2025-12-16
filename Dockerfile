# Используем официальный Python образ
FROM python:3.10-slim

# Метаданные
LABEL maintainer="UseDesk Backend Team"
LABEL description="UseDesk Backend - Flask app with Telegram integration"
LABEL version="2.1"

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копируем код приложения (новая структура с backend/)
COPY backend/ backend/

# Копируем .env если существует (опционально)
COPY .env* ./

# Создаем пользователя для запуска приложения (безопасность)
RUN useradd -r -u 1000 -m -s /bin/bash appuser

# Создаем директории для кеша и логов с правильными правами
RUN mkdir -p /app/cache /app/logs && \
    chown -R appuser:appuser /app && \
    chmod -R 755 /app/cache /app/logs

# Переключаемся на непривилегированного пользователя
USER appuser

# Expose порт приложения
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:5000/health', timeout=5)" || exit 1

# Запускаем приложение
CMD ["python", "-m", "backend.run"]

