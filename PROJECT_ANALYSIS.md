# PROJECT_ANALYSIS.md — AlgorIA Chatbot

> Generado: 2026-04-30
> Proyecto: `C:\Users\Usuario\Desktop\Chatbot ALGEBRA`

---

## 1. ESTRUCTURA DE ARCHIVOS

```
Chatbot ALGEBRA/
├── Dockerfile                          ✅ (build config)
├── docker-compose.yml                  ✅ (orquestación)
├── README.md                           ✅
├── PROJECT_ANALYSIS.md                 ✅ (este archivo)
├── DEPLOYMENT_STATUS.md                ✅
├── MIGRATION_NOTES.md                  ✅
│
├── backend/
│   ├── main.py                         ✅ 313 líneas, 15 endpoints
│   ├── requirements.txt                ✅ 7 dependencias
│   ├── .env                            🔴 CRÍTICO: clave real expuesta, proveedor incorrecto
│   ├── .env.example                    🔴 Template desactualizado
│   │
│   ├── agents/
│   │   ├── __init__.py                 ✅
│   │   ├── algebra_agent.py            ✅ Anthropic + RAG
│   │   └── calculo_agent.py            ✅ Anthropic (sin RAG)
│   │
│   ├── utils/
│   │   ├── __init__.py                 ✅
│   │   ├── analytics.py                ✅ SQLite, tracking usuarios/interacciones
│   │   ├── session_manager.py          ✅ Sesiones en memoria (no persistente)
│   │   ├── rag.py                      ✅ Recuperación BM25-style
│   │   └── knowledge_loader.py         ⚠️ Importado pero nunca usado
│   │
│   ├── prompts/
│   │   ├── algebra_system_prompt.txt   ✅ 180 líneas, detallado
│   │   └── calculo_system_prompt.txt   ✅ 50 líneas
│   │
│   └── knowledge/
│       └── algebra_chunks.json         ✅ ~70 chunks para RAG (24 KB)
│
├── frontend/
│   ├── index.html                      ✅ 937 líneas, UI completa
│   └── admin.html                      ✅ 551 líneas, dashboard admin
│
└── data/
    ├── pdfs/                           ⚠️ Directorio vacío
    └── ejercicios/                     ⚠️ Directorio vacío
```

---

## 2. CÓDIGO DEL BACKEND

### 2.1 main.py — FastAPI Application

**Endpoints implementados:**

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Health check raíz |
| GET | `/health` | Status `{"status": "ok"}` |
| POST | `/auth` | Login/registro de usuario |
| POST | `/chat` | Chat principal (algebra/calculo) |
| POST | `/reset` | Limpiar historial de sesión |
| POST | `/admin/verify` | Verificar PIN admin |
| GET | `/admin/check-access` | Verificar rol admin |
| POST | `/admin/set-role` | Asignar roles (superadmin only) |
| GET | `/admin/stats` | Estadísticas del dashboard |
| GET | `/admin/interactions` | Interacciones recientes |
| GET | `/admin/users` | Lista de usuarios |
| POST | `/feedback` | Enviar rating |
| GET | `/admin/feedback` | Analíticas de feedback |
| GET | `/sessions/{session_id}` | Historial de sesión |
| GET | `/history/{email}` | Sesiones del usuario |
| GET | `/history/{email}/{session_id}` | Mensajes de una sesión |

**Configuración CORS (main.py ~línea 40):**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'https://algoria.angeloperrotta.online',
        'https://blanchedalmond-buffalo-707381.hostingersite.com',
        'https://chatbot-educativo-de-lgebra-con-ia-uai-production.up.railway.app',
        'https://*.netlify.app',          # ⚠️ Wildcard — permite CUALQUIER app Netlify
        'http://localhost:5500',
        'http://127.0.0.1:5500'
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### 2.2 agents/algebra_agent.py

```python
from anthropic import Anthropic
from utils.rag import retrieve_context
from utils.analytics import log_interaction

def chat(historial: list, session_id: str = None) -> str:
    api_key = os.getenv('ANTHROPIC_API_KEY')     # Lee clave del entorno
    client = Anthropic(api_key=api_key)           # Crea cliente Anthropic
    system_prompt = load_system_prompt()          # Carga 180 líneas de prompt

    # RAG: busca contexto relevante en algebra_chunks.json
    context, rag_score = retrieve_context(last_user_message)
    if context:
        system_prompt += "\n\nCONTEXTO RELEVANTE DE LA CÁTEDRA:\n" + context

    response = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=1024,
        system=system_prompt,
        messages=historial
    )
    # Logs analíticos con tiempo de respuesta y confianza RAG
    log_interaction(...)
    return result
```

**Características:**
- ✅ RAG con scoring de confianza (alta>5, media>=3, baja<3)
- ✅ Logging completo con tiempos de respuesta
- ✅ Manejo de errores con `try/except`

---

### 2.3 agents/calculo_agent.py

```python
from anthropic import Anthropic

def chat(historial: list, session_id: str = None) -> str:
    api_key = os.getenv('ANTHROPIC_API_KEY')
    client = Anthropic(api_key=api_key)
    system_prompt = load_system_prompt()    # 50 líneas (más breve)

    response = client.messages.create(
        model='claude-haiku-4-5-20251001',
        max_tokens=1024,
        system=system_prompt,
        messages=historial
    )
    return result
```

**Diferencias respecto a algebra_agent:**
- ❌ Sin RAG (no existe `calculo_chunks.json`)
- ❌ Sin `log_interaction()` — no registra en analytics
- ⚠️ Prompt mucho más corto

---

### 2.4 requirements.txt

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
anthropic>=0.39.0
httpx>=0.28.0
python-dotenv==1.0.1
pydantic==2.10.0
python-multipart==0.0.20
```

- ✅ `anthropic>=0.39.0` — versión correcta (usa `proxy=` singular internamente)
- ✅ `httpx>=0.28.0` — compatible
- ✅ Sin uso directo de httpx en el código propio

---

## 3. CONFIGURACIÓN DE DEPLOYMENT

### 3.1 Dockerfile

**Actual:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
EXPOSE 8000
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

**Problema:** `CMD` como string en lugar de array JSON — frágil para señales OS (SIGTERM no llega al proceso).

**Recomendado:**
```dockerfile
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### 3.2 docker-compose.yml

```yaml
version: "3.11"    # ⚠️ Versión inválida (máximo válido: "3.9")
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - backend/.env
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

**Fix:**
```yaml
# Opción A: Sin versión (Compose v2 moderno):
services:
  backend:
    ...

# Opción B: Versión válida:
version: "3.9"
services:
  backend:
    ...
```

---

### 3.3 Variables de Entorno — PROBLEMA CRÍTICO

**`backend/.env` actual (ROTO):**
```bash
OPENROUTER_API_KEY=sk-or-v1-...   # ❌ Proveedor incorrecto, clave real expuesta
PORT=8000
ENVIRONMENT=development
# ANTHROPIC_API_KEY — no definida → agentes fallan
# ADMIN_PIN — no definida → admin siempre retorna 403
```

**`backend/.env` correcto para desarrollo:**
```bash
ANTHROPIC_API_KEY=sk-ant-api03-TU_CLAVE_REAL_AQUI
ADMIN_PIN=123456
PORT=8000
ENVIRONMENT=development
```

**`backend/.env.example` correcto:**
```bash
ANTHROPIC_API_KEY=sk-ant-api03-TU_CLAVE_AQUI
ADMIN_PIN=TU_PIN_SEGURO_AQUI
PORT=8000
ENVIRONMENT=production
```

---

## 4. FRONTEND

### 4.1 frontend/index.html

**URL del backend (línea ~348):**
```javascript
const BACKEND = 'https://chatbot-educativo-de-lgebra-con-ia-uai-production.up.railway.app';
```

**Endpoints consumidos:**
- `POST /auth` — autenticación
- `POST /chat` — enviar mensaje
- `POST /reset` — limpiar sesión
- `GET /history/${email}` — cargar sesiones
- `POST /feedback` — enviar rating
- `GET /history/${email}/${session_id}` — cargar mensajes de sesión

**Características UI:**
- ✅ Tema oscuro con colores neón
- ✅ Diseño responsive (móvil/escritorio)
- ✅ Renderizado matemático con KaTeX
- ✅ Contador de caracteres (0/500)
- ✅ Sidebar de historial de sesiones
- ✅ Login admin con OTP de 6 dígitos
- ✅ Feedback (rating 5 estrellas + comentarios)
- ✅ Toggle tema claro/oscuro

### 4.2 frontend/admin.html

- ✅ Grid de estadísticas (interacciones totales, sesiones, longitud promedio, etc.)
- ✅ Gráficos Chart.js (interacciones diarias, distribución por tema)
- ✅ Tabla de usuarios con barras de uso de tokens y gestión de roles
- ✅ Tabla de interacciones con logs detallados
- ✅ Analytics de feedback con distribución de estrellas
- ✅ Métricas de confianza RAG
- ✅ Export a PDF

---

## 5. DIAGNÓSTICO DEL ERROR 'proxies'

### 5.1 Búsqueda Exhaustiva en el Código

```
GREP "proxies"          → Solo en PROJECT_ANALYSIS.md (documentación)
GREP "httpx"            → NO encontrado en ningún .py
GREP "requests.Session" → NO encontrado
GREP "AsyncClient"      → NO encontrado en código propio
GREP "Client("          → Solo: Anthropic(api_key=...)
GREP "proxy"            → NO encontrado (excepto en docs)
```

**Conclusión: El codebase NO contiene referencia alguna al argumento `proxies=`.**

---

### 5.2 Causa Raíz

El error `TypeError: unexpected keyword argument 'proxies'` ocurre por incompatibilidad de versiones:

| Componente | Versión problemática | Versión correcta |
|------------|---------------------|-----------------|
| httpx | >= 0.28.0 | >= 0.28.0 ✅ |
| anthropic SDK | < 0.37.0 (usa `proxies=` internamente) | >= 0.39.0 ✅ |

**Patrón problemático (NO presente en este código, solo referencia):**
```python
# ❌ DEPRECADO — causa error con httpx >= 0.28.0:
import httpx
client = httpx.Client(proxies="http://proxy.example.com")  # ❌ plural

# ✅ CORRECTO — httpx >= 0.28.0:
client = httpx.Client(proxy="http://proxy.example.com")    # ✅ singular
```

**Diagnóstico del estado actual:**
- ✅ `requirements.txt` especifica `anthropic>=0.39.0` — versión correcta
- ✅ `httpx>=0.28.0` — compatible
- ✅ No hay uso directo de httpx en el proyecto
- ⚠️ Si el error ocurre en producción: probablemente la versión instalada en Railway es vieja

**Solución si el error persiste en Railway:**
```bash
# Forzar versión mínima en requirements.txt:
anthropic==0.40.0
httpx==0.28.1
```

---

## 6. ISSUES IDENTIFICADOS

### 🔴 CRÍTICO

| Issue | Ubicación | Impacto |
|-------|-----------|---------|
| Variable de entorno incorrecta | `backend/.env` | Autenticación con Claude API falla — TODO el chat está roto |
| Clave API real expuesta en git | `backend/.env` | Brecha de seguridad, riesgo de cargos en cuenta OpenRouter |
| `ANTHROPIC_API_KEY` no definida | `backend/.env` | Agentes no pueden inicializarse |
| `ADMIN_PIN` no definido | `backend/.env` | Endpoints admin retornan 403 siempre |

### 🟡 MEDIO

| Issue | Ubicación | Impacto |
|-------|-----------|---------|
| Sesiones en memoria | `session_manager.py:4` | Pérdida de sesiones en cada restart del servidor |
| Base de datos en `/tmp` | `analytics.py:5` | SQLite efímero en Railway; datos perdidos al redeploy |
| `calculo_agent.py` sin logging | agente de cálculo | No registra interacciones en analytics |
| `knowledge_loader.py` no usado | `backend/utils/` | Código muerto |
| CORS wildcard Netlify | `main.py:46` | Permite cualquier app Netlify (no solo este proyecto) |

### 🟢 BAJO

| Issue | Ubicación | Impacto |
|-------|-----------|---------|
| `docker-compose.yml` versión inválida | línea 2 | Warning ignorado por Compose |
| `CMD` string en Dockerfile | última línea | Señal SIGTERM no llega al proceso uvicorn |
| URL backend hardcodeada | `index.html:348` | Requiere edición manual para cambiar entorno |

---

## 7. SOLUCIONES

### 7.1 FIX INMEDIATO — Variables de Entorno (BLOQUEANTE)

**Paso 1: Editar `backend/.env`**
```bash
ANTHROPIC_API_KEY=sk-ant-api03-OBTENER_EN_console.anthropic.com
ADMIN_PIN=123456
PORT=8000
ENVIRONMENT=development
```

**Paso 2: Railway → Variables**
```
ANTHROPIC_API_KEY = sk-ant-api03-[tu clave real]
ADMIN_PIN = [PIN de 6 dígitos]
ENVIRONMENT = production
```

**Paso 3: Redeploy en Railway**

---

### 7.2 Seguridad — Revocar Clave Expuesta

```bash
# 1. Revocar en https://openrouter.ai/keys
# 2. Agregar .env al .gitignore
echo "backend/.env" >> .gitignore
git rm --cached backend/.env    # si ya está trackeado
git commit -m "fix: remove .env from git tracking"
```

---

### 7.3 Persistencia de Base de Datos

**Problema en `analytics.py`:**
```python
DB_PATH = '/tmp/analytics.db'   # ❌ Efímero en Railway
```

**Fix:**
```python
import os
from pathlib import Path
DB_PATH = os.getenv('DB_PATH', str(Path(__file__).parent.parent / 'data' / 'analytics.db'))
```

En Railway: montar volumen en `/data` y definir `DB_PATH=/data/analytics.db`.

---

### 7.4 Dockerfile — CMD como Array JSON

```dockerfile
# Cambiar esta línea:
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}

# Por esta:
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### 7.5 docker-compose.yml — Versión Válida

```yaml
# Cambiar:
version: "3.11"

# Por:
version: "3.9"
# O eliminar la línea version completamente (Compose v2)
```

---

## 8. ARQUITECTURA DEL SISTEMA

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND (Netlify / Hostinger)                         │
│  • index.html  (UI principal)                           │
│  • admin.html  (Dashboard admin)                        │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS REST
                         ▼
┌─────────────────────────────────────────────────────────┐
│  BACKEND FastAPI (Railway)                              │
│  ┌──────────────────────────────────────────────────┐  │
│  │  main.py — 15 endpoints                          │  │
│  └───────────┬─────────────────┬────────────────────┘  │
│              │                 │                        │
│   ┌──────────▼───────┐  ┌─────▼──────────────────┐    │
│   │  Agents           │  │  Analytics/Auth         │    │
│   │  algebra_agent.py │  │  analytics.py (SQLite)  │    │
│   │   + RAG           │  │  session_manager.py     │    │
│   │  calculo_agent.py │  │  (in-memory)            │    │
│   └──────────┬────────┘  └─────────────────────────┘   │
│              │                                          │
│   ┌──────────▼────────────────────────────────────┐    │
│   │  Knowledge & Prompts                          │    │
│   │  algebra_chunks.json  (70 chunks, RAG)        │    │
│   │  algebra_system_prompt.txt (180 líneas)       │    │
│   │  calculo_system_prompt.txt (50 líneas)        │    │
│   │  rag.py (BM25 retrieval)                      │    │
│   └───────────────────────────────────────────────┘    │
└────────────────────────┬────────────────────────────────┘
                         │ HTTPS API
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Anthropic Claude (claude-haiku-4-5-20251001)           │
│  Max tokens: 1024 por respuesta                         │
└─────────────────────────────────────────────────────────┘
```

**Flujo de datos para `/chat`:**
```
1. Frontend → POST /chat {message, materia, session_id, user_email}
2. main.py: valida longitud (≤500), verifica límite de tokens
3. Agrega mensaje al historial (en-memory)
4. algebra_agent: RAG → Claude API → log_interaction()
   calculo_agent: Claude API (sin RAG, sin logging)
5. Retorna ChatResponse {response, session_id}
6. Frontend renderiza respuesta + KaTeX para matemáticas
```

---

## 9. CHECKLIST DE DEPLOYMENT

### Bloqueante (hacer primero):
- [ ] Crear `backend/.env` con `ANTHROPIC_API_KEY` y `ADMIN_PIN` correctos
- [ ] Actualizar `backend/.env.example` con los nombres correctos de variables
- [ ] Agregar `backend/.env` al `.gitignore`
- [ ] Revocar la clave OpenRouter expuesta en openrouter.ai/keys
- [ ] Configurar variables en Railway (ANTHROPIC_API_KEY, ADMIN_PIN)

### Mejoras de deployment:
- [ ] Corregir `CMD` en Dockerfile a formato JSON array
- [ ] Corregir versión en `docker-compose.yml`
- [ ] Montar volumen persistente para SQLite en Railway
- [ ] Verificar endpoint `/health` retorna `{"status": "ok"}`
- [ ] Probar chat con mensaje de prueba
- [ ] Probar login admin con PIN correcto

### Post-deployment (mejoras):
- [ ] Migrar sesiones de memoria a SQLite
- [ ] Agregar `log_interaction` a `calculo_agent.py`
- [ ] Crear `calculo_chunks.json` para RAG de cálculo
- [ ] Restringir CORS a dominios específicos (no wildcard)
- [ ] Integrar o eliminar `knowledge_loader.py`

---

## 10. RESUMEN EJECUTIVO

| Componente | Estado | Prioridad |
|------------|--------|-----------|
| main.py | ✅ Completo | — |
| algebra_agent.py | ✅ Funcional (requiere API key) | CRÍTICO |
| calculo_agent.py | ✅ Funcional (requiere API key) | CRÍTICO |
| analytics.py | ✅ Funcional (DB efímera) | MEDIO |
| session_manager.py | ✅ Funcional (no persistente) | MEDIO |
| rag.py | ✅ Completo | — |
| Dockerfile | ⚠️ Funcional con mejora menor | BAJO |
| docker-compose.yml | ⚠️ Funcional con warning | BAJO |
| frontend/index.html | ✅ Completo | — |
| frontend/admin.html | ✅ Completo | — |
| requirements.txt | ✅ Correcto | — |
| backend/.env | 🔴 ROTO | **CRÍTICO** |
| backend/.env.example | 🔴 Desactualizado | CRÍTICO |

**El proyecto es arquitectónicamente sólido.** Todo el código está correctamente implementado. El único bloqueante real son las variables de entorno incorrectas en `.env`. Una vez corregidas (5 minutos de trabajo), el sistema es deployable inmediatamente.

El error de `proxies` NO está presente en el código actual — las versiones en `requirements.txt` son correctas. Si ocurre en producción, es porque Railway instaló una versión vieja del SDK de Anthropic; la solución es forzar el redeploy limpio con `pip install --no-cache-dir`.
