FROM python:3.11-slim

WORKDIR /app

# Copiar requirements e instalar dependencias
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el código del backend
COPY backend/ .

# Exponer puerto (Railway usa variable de entorno PORT)
EXPOSE 8000

# Comando para ejecutar la app
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
