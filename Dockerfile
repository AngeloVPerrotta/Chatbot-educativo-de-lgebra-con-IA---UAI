# ── Imagen base: Python 3.11 mínima para reducir tamaño del contenedor ──
FROM python:3.11-slim

# ── Directorio de trabajo dentro del contenedor ──
WORKDIR /app

# ── Copiar solo el archivo de dependencias primero para aprovechar
#    la caché de capas de Docker (si no cambia, no reinstala) ──
COPY backend/requirements.txt .

# ── Instalar dependencias sin guardar caché de pip ──
RUN pip install --no-cache-dir -r requirements.txt

# ── Copiar el resto del código del backend ──
COPY backend/ .

# ── Puerto que expone la aplicación ──
EXPOSE 8000

# ── Comando de inicio: uvicorn con recarga desactivada para producción ──
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
