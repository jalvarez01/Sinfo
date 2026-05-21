FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para Prophet
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Variables de entorno
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Ejecutar con gunicorn (producción)
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
