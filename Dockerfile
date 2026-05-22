FROM python:3.11

WORKDIR /app

# Dependencias del sistema para compilar cmdstan
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    g++ \
    make \
    cmake \
    libtbb-dev \
    libgomp1 \
    curl \
    git \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Pip actualizado
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 1. Instalar cmdstanpy primero (es la dependencia que Prophet necesita)
RUN pip install --no-cache-dir cmdstanpy==1.2.4

# 2. Compilar cmdstan (esto tarda 5-10 min pero solo una vez)
RUN python -c "from cmdstanpy import install_cmdstan; install_cmdstan(verbose=True)"

# 3. Instalar Prophet (ya con cmdstan listo)
RUN pip install --no-cache-dir prophet==1.1.5

# 4. Resto de dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código de la app
COPY . .

# Variables de entorno
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV CMDSTAN=/root/.cmdstan/cmdstan-2.34.1

# Verificar instalación (falla el build si Prophet no funciona)
RUN python -c "from prophet import Prophet; m = Prophet(); print('✓ Prophet OK')"

# Ejecutar
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app