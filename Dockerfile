FROM python:3.11-slim

# Метаданные
LABEL maintainer="TgSpyBot Team"
LABEL description="Telegram Chat Parser with Bot Management"
LABEL version="1.0.0"

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Создаём рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Создаём пользователя для безопасности
RUN groupadd -r tgspybot && useradd -r -g tgspybot tgspybot

# Создаём необходимые директории
RUN mkdir -p /app/data /app/logs && \
    chown -R tgspybot:tgspybot /app

# Копируем код приложения
COPY app/ ./app/
COPY main.py ./
COPY mvp_test.py ./

# Устанавливаем правильные права доступа
RUN chown -R tgspybot:tgspybot /app

# Переключаемся на пользователя приложения
USER tgspybot

# Переменные окружения по умолчанию
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Проверка здоровья контейнера
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import redis; r=redis.Redis(host='redis', port=6379); r.ping()" || exit 1

# Порты (если будет веб-интерфейс в будущем)
EXPOSE 8080

# Команда запуска
CMD ["python", "main.py"] 