# AlgorIA – Estado de Deploy en Hostinger Cloud Startup
**Fecha de análisis:** 2026-04-22  
**Branch:** main | **Último commit:** `0e7b7ba` – Initial commit

---

## 1. ESTRUCTURA DEL PROYECTO

| Elemento | Estado |
|---|---|
| `backend/` | ✅ Presente |
| `frontend/` | ✅ Presente |
| `data/pdfs/` | ✅ Presente (vacía) |
| `data/ejercicios/` | ✅ Presente (vacía) |
| `backend/requirements.txt` | ✅ Presente |
| `backend/.env.example` | ✅ Presente (⚠️ ver sección 4) |
| `.env.example` en raíz | ❌ No existe (el .env.example está dentro de `backend/`) |
| `requirements.txt` en raíz | ❌ No existe (está en `backend/`) |
| `Dockerfile` | ✅ Presente |
| `docker-compose.yml` | ✅ Presente |

---

## 2. BACKEND (FastAPI)

### `backend/main.py` ✅
- Endpoints implementados: `GET /`, `GET /health`, `POST /chat`, `POST /reset`, `GET /sessions/{session_id}`
- Validación con Pydantic v2 ✅
- Manejo de excepciones HTTP ✅
- Carga de variables de entorno con `dotenv` ✅

### `backend/agents/algebra_agent.py` ⚠️
- Implementado y funcional ✅
- **Modelo desactualizado:** usa `claude-sonnet-4-20250514` en lugar de `claude-sonnet-4-6`
- Manejo de errores de API correctamente implementado ✅

### `backend/agents/calculo_agent.py` ⚠️
- Implementado y funcional ✅
- Usa modelo `claude-sonnet-4-6` ✅
- **Sin manejo de excepciones de API** (a diferencia del agente de álgebra)

### `backend/utils/session_manager.py` ⚠️
- Implementado ✅
- **Usa almacenamiento en memoria (`dict`)** – las sesiones se pierden al reiniciar el servidor y no son compatibles con múltiples workers/procesos. No apto para producción escalable.

### `backend/utils/knowledge_loader.py` ✅
- Lista PDFs y ejercicios correctamente desde `data/`

### `backend/requirements.txt` ✅
```
fastapi==0.115.0
uvicorn[standard]==0.32.0
anthropic==0.40.0
python-dotenv==1.0.1
pydantic==2.10.0
python-multipart==0.0.20
```

### `backend/prompts/`
- `algebra_system_prompt.txt` ✅ Completo y bien estructurado
- `calculo_system_prompt.txt` ✅ Presente (menos detallado que el de álgebra)

---

## 3. FRONTEND

### `frontend/index.html` ⚠️
- Interfaz completa: selector de materia, historial de mensajes, indicador "escribiendo..." ✅
- Tailwind CSS via CDN ✅
- **PROBLEMA CRÍTICO:** URL del backend hardcodeada a `localhost`

```js
// Línea 117 – Debe cambiarse al dominio de Hostinger antes del deploy
const BACKEND = 'http://127.0.0.1:8000';  // ❌ localhost
```

---

## 4. CONFIGURACIÓN

### `.gitignore` ✅
Correctamente excluye:
- `.env` y `*.env` ✅
- `venv/` y `.venv/` ✅
- `__pycache__/` ✅

### `backend/.env.example` 🚨 ALERTA DE SEGURIDAD
El archivo `.env.example` **contiene una API key real de Anthropic**:
```
ANTHROPIC_API_KEY=sk-ant-api03-LPCL95mjNJW0H7DaNSBJMN20KnCSlUw60whqYpLXmrFnU2rikM29fFx...
```
**Acción inmediata requerida:**
1. Revocar esa API key en console.anthropic.com
2. Reemplazar el valor real por un placeholder: `ANTHROPIC_API_KEY=sk-ant-api03-TU_CLAVE_AQUI`
3. Verificar que `backend/.env` no fue commiteado (el `.gitignore` debería protegerlo)

### `docker-compose.yml` ⚠️
- El archivo referencia `env_file: .env` buscando en la raíz del proyecto
- El `.env` real está en `backend/.env` → **discrepancia en la ruta**
- Para Hostinger, las variables de entorno se configuran desde el panel, no desde este archivo

---

## 5. CONOCIMIENTO BASE

| Carpeta | Archivos | Estado |
|---|---|---|
| `data/pdfs/` | Solo `README.md` | ❌ Sin materiales |
| `data/ejercicios/` | Solo `README.md` | ❌ Sin materiales |

Los agentes funcionan sin estos archivos (el `knowledge_loader.py` existe pero **ningún agente lo llama**), pero la base de conocimiento institucional está vacía.

---

## 6. DEPLOYMENT READINESS – Hostinger Cloud Startup

### Dockerfile ✅
- Imagen base `python:3.11-slim` ✅
- Copia `backend/requirements.txt` e instala dependencias ✅
- Expone puerto 8000 ✅
- Comando de producción correcto (sin `--reload`) ✅

### CORS ⚠️
```python
# backend/main.py línea 17
allow_origins=["*"]  # Permite cualquier origen – demasiado permisivo para producción
```
Debería restringirse al dominio de Hostinger antes del deploy.

### Sesiones en memoria ⚠️
Si Hostinger usa múltiples workers o reinicia el contenedor, **todos los historiales de conversación se pierden**. Aceptable para MVP, pero hay que documentarlo.

---

## RESUMEN GENERAL

### ✅ Completo
- Estructura de proyecto backend con FastAPI
- Endpoints REST: `/chat`, `/reset`, `/sessions/{id}`, `/health`
- Agentes de Álgebra y Cálculo funcionales
- Session manager (básico, en memoria)
- Sistema de prompts educativos
- Frontend con UI completa y selector de materia
- Dockerfile de producción
- `.gitignore` correctamente configurado

### ⚠️ Necesita ajustes antes del deploy
- [ ] Actualizar modelo en `algebra_agent.py`: `claude-sonnet-4-20250514` → `claude-sonnet-4-6`
- [ ] Agregar manejo de excepciones en `calculo_agent.py`
- [ ] Cambiar `BACKEND` en `frontend/index.html` al dominio real de Hostinger
- [ ] Restringir CORS de `"*"` al dominio de Hostinger
- [ ] Corregir `env_file` en `docker-compose.yml` (ruta incorrecta)
- [ ] Agregar `requirements.txt` y `.env.example` en la raíz del proyecto (opcional pero recomendado)

### ❌ Falta por hacer
- [ ] **URGENTE: Revocar la API key expuesta en `.env.example` y reemplazarla por placeholder**
- [ ] Cargar materiales en `data/pdfs/` y `data/ejercicios/`
- [ ] Integrar `knowledge_loader.py` en los agentes (actualmente existe pero no se usa)
- [ ] Definir dominio real en Hostinger

---

## 📋 CHECKLIST DE DEPLOY EN HOSTINGER

### Pre-deploy (local)
- [ ] 🚨 Revocar API key real de `backend/.env.example` → reemplazar por `sk-ant-api03-TU_CLAVE_AQUI`
- [ ] Actualizar `const BACKEND` en `frontend/index.html` con el dominio real (ej. `https://algoria.tudominio.com`)
- [ ] Restringir CORS: `allow_origins=["https://algoria.tudominio.com"]`
- [ ] Actualizar modelo en `algebra_agent.py` a `claude-sonnet-4-6`
- [ ] Hacer commit de los cambios

### En Hostinger Cloud
- [ ] Crear proyecto en Hostinger Cloud Startup
- [ ] Conectar repositorio de GitHub
- [ ] Configurar variable de entorno `ANTHROPIC_API_KEY` desde el panel de Hostinger (NO desde `.env`)
- [ ] Configurar variable `PORT=8000` (o el que asigne Hostinger)
- [ ] Configurar variable `ENVIRONMENT=production`
- [ ] Verificar que Hostinger detecte el `Dockerfile` en la raíz
- [ ] Confirmar que el build compile correctamente (`pip install -r requirements.txt`)
- [ ] Hacer deploy y probar el endpoint `GET /health` → debe retornar `{"status": "ok"}`

### Post-deploy
- [ ] Subir materiales a `data/pdfs/` y `data/ejercicios/`
- [ ] Probar flujo completo: enviar mensaje de álgebra y de cálculo
- [ ] Probar `/reset` y que limpie el historial correctamente
- [ ] Revisar logs de Hostinger para detectar errores de inicio

---

> **Nota sobre el frontend:** `frontend/index.html` es un archivo estático. En Hostinger, puede servirse directamente desde el backend FastAPI como archivo estático, o desplegarse en un servicio de hosting estático separado (Netlify, GitHub Pages, etc.). Si se sirve desde FastAPI, agregar `StaticFiles` en `main.py`.
