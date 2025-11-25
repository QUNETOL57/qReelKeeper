# Используем официальный образ Python последней версии
FROM python:3.13.1-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем необходимые системные зависимости для yt-dlp
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Создаем директорию для скачанных файлов
RUN mkdir -p /app/downloads

# Копируем код бота
COPY main.py .

# Команда для запуска бота
CMD ["python", "main.py"]
