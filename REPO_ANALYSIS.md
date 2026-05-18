# REPO_ANALYSIS.md — AlgorIA

Análisis completo del repositorio generado el 2026-05-17.

---

## 1. ESTRUCTURA DE ARCHIVOS

### Raíz
| Archivo | Descripción |
|---------|-------------|
| `Dockerfile` | Build de imagen Docker para deploy (Python 3.11 + uvicorn) |
| `docker-compose.yml` | Orquestación con volumen persistente para SQLite |
| `.dockerignore` | Exclusiones del build Docker |
| `.gitignore` | Exclusiones de Git |
| `favicon.png` | Ícono de la aplicación |
| `README.md` | Overview del proyecto |
| `DEPLOYMENT_STATUS.md` | Estado de readiness para deploy |
| `MIGRATION_NOTES.md` | Notas de migración (Anthropic → Groq, planificado) |
| `PROJECT_ANALYSIS.md` | Análisis previo del proyecto |

### Backend (`backend/`)
| Archivo | Descripción |
|---------|-------------|
| `main.py` | Aplicación FastAPI: endpoints, CORS, routing a agentes |
| `requirements.txt` | Dependencias Python del proyecto |
| `.env` | Variables de entorno (local, no comiteado idealmente) |
| `.env.example` | Ejemplo de variables de entorno |
| `agents/__init__.py` | Init del paquete agents |
| `agents/algebra_agent.py` | Agente de Álgebra con RAG + Claude API |
| `agents/calculo_agent.py` | Agente de Cálculo sin RAG + Claude API |
| `utils/__init__.py` | Init del paquete utils |
| `utils/analytics.py` | Gestión de SQLite: usuarios, interacciones, rate limits, feedback |
| `utils/build_chunks.py` | Generador de chunks JSON desde archivos DOCX |
| `utils/knowledge_loader.py` | Cargador de knowledge base (existe pero no se usa) |
| `utils/payments.py` | Integración con Mercado Pago (crear link, webhook) |
| `utils/rag.py` | Retrieval con scoring BM25: busca chunks relevantes |
| `utils/session_manager.py` | Gestión de sesiones en memoria (dict Python) |
| `prompts/algebra_system_prompt.txt` | System prompt del tutor de Álgebra (180 líneas) |
| `prompts/calculo_system_prompt.txt` | System prompt del tutor de Cálculo (22 líneas) |
| `knowledge/algebra_chunks.json` | 70+ chunks semánticos para RAG de Álgebra |
| `knowledge/fuentes/Clase 01.docx` … `Clase 14.docx` | 14 materiales didácticos fuente |

### Frontend (`frontend/`)
| Archivo | Descripción |
|---------|-------------|
| `index.html` | UI principal del chat con KaTeX, sidebar, rate limit |
| `admin.html` | Dashboard de administración con Chart.js |
| `grapher.html` | Graficador de funciones con math.js + canvas |

### Data (`data/`)
| Archivo | Descripción |
|---------|-------------|
| `pdfs/README.md` | Placeholder vacío para PDFs |
| `ejercicios/README.md` | Placeholder vacío para ejercicios |

### Deploy (`deploy/`)
| Archivo | Descripción |
|---------|-------------|
| `hostinger-setup.sh` | Script de instalación completo para VPS Ubuntu |
| `update.sh` | Script de actualización (pull + reinstall + restart) |

---

## 2. STACK TÉCNICO

### Backend
| Componente | Tecnología | Versión |
|------------|-----------|---------|
| Framework | FastAPI | 0.115.0 |
| Servidor ASGI | Uvicorn | 0.32.0 |
| Lenguaje | Python | 3.11 |
| IA | Anthropic SDK → Claude | claude-haiku-4-5-20251001 |
| Base de datos | SQLite | (stdlib) |
| Pagos | Mercado Pago SDK | ≥2.2.0 |
| HTTP Client | httpx | ≥0.28.0 |
| Validación | Pydantic | 2.10.0 |
| Config | python-dotenv | 1.0.1 |
| Docs processing | python-docx | 1.1.0+ |

### Frontend
| Componente | Tecnología | Versión |
|------------|-----------|---------|
| Markup | HTML5 | — |
| Styling | CSS custom (variables, glassmorphism) | — |
| Math rendering | KaTeX | 0.16.11 |
| Charts | Chart.js | 4.4.4 |
| Graficador | math.js | (CDN) |
| Fonts | Google Fonts (DM Sans, JetBrains Mono, Outfit) | — |

### Infraestructura
| Componente | Tecnología |
|------------|-----------|
| Containerización | Docker + Docker Compose |
| Reverse proxy | Nginx |
| SSL | Let's Encrypt (Certbot) |
| Process manager | systemd |
| Targets | Railway (cloud) / Hostinger VPS |

### APIs externas
| API | Uso |
|-----|-----|
| Anthropic Claude API | Generación de respuestas del chatbot |
| Mercado Pago API | Generación de links de pago y webhooks |

---

## 3. ARQUITECTURA

### Flujo de un mensaje (POST /chat)

```
┌──────────────┐     POST /chat          ┌──────────────────────┐
│   Frontend   │ ──────────────────────→  │   FastAPI (main.py)  │
│  index.html  │  {message, materia,      │                      │
│              │   session_id, email}      │  1. Validar input    │
└──────────────┘                          │  2. Check rate limit │
                                          │  3. Routing          │
                                          └──────┬───────────────┘
                                                 │
                              ┌──────────────────┴──────────────────┐
                              │                                     │
                    materia="algebra"                      materia="calculo"
                              │                                     │
                              ▼                                     ▼
                 ┌─────────────────────┐              ┌─────────────────────┐
                 │  algebra_agent.py   │              │  calculo_agent.py   │
                 │                     │              │                     │
                 │ 1. Cargar prompt    │              │ 1. Cargar prompt    │
                 │ 2. RAG: retrieve   │              │ 2. (sin RAG)        │
                 │    top-2 chunks    │              │ 3. Claude API call  │
                 │ 3. Claude API call │              │ 4. Return response  │
                 │ 4. log_interaction │              │ (NO logging)        │
                 │ 5. Return response │              └─────────────────────┘
                 └─────────┬──────────┘
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
    ┌──────────────────┐     ┌───────────────────┐
    │  rag.py          │     │  analytics.py     │
    │  BM25 scoring    │     │  SQLite logging   │
    │  algebra_chunks  │     │  interactions,    │
    │  .json           │     │  chat_history     │
    └──────────────────┘     └───────────────────┘
                                       │
              ┌────────────────────────┘
              ▼
    ┌──────────────────┐          ┌──────────────────┐
    │  Anthropic API   │          │  Response JSON   │
    │  Claude Haiku    │ ───────→ │  {response,      │
    │  max_tokens: 500 │          │   session_id}    │
    └──────────────────┘          └────────┬─────────┘
                                           │
                                           ▼
                                  ┌──────────────┐
                                  │   Frontend   │
                                  │  KaTeX render│
                                  │  + display   │
                                  └──────────────┘
```

### Flujo detallado paso a paso

1. **Frontend** envía `{message, materia, session_id, user_email}` vía POST
2. **main.py** valida: mensaje ≤500 chars, session_id ≤64 chars
3. **Rate limit check**: 15 msgs/24h por (email > device_fp > IP)
4. **Token limit check**: contra `user.token_limit` si hay email
5. Append mensaje del usuario a sesión (in-memory)
6. **Router** selecciona agente según `materia`
7. **Agente** carga system prompt desde archivo `.txt`
8. **RAG** (solo álgebra): `retrieve_context()` devuelve top-2 chunks con score BM25
9. **Claude API call** con system + historial + contexto RAG
10. Append respuesta del asistente a sesión
11. **Log** a SQLite (`interactions` + `chat_history`)
12. Incrementar contador de rate limit
13. Return `{response, session_id}` al frontend
14. **Frontend** renderiza LaTeX con KaTeX

---

## 4. BASE DE DATOS

**Motor:** SQLite  
**Ubicación:** `./analytics.db` (dev) o `/data/analytics.db` (producción Docker)

### Tabla: `users`
| Columna | Tipo | Default | Descripción |
|---------|------|---------|-------------|
| `id` | INTEGER PK | AUTOINCREMENT | ID único |
| `name` | TEXT NOT NULL | — | Nombre del usuario |
| `email` | TEXT UNIQUE | — | Email (identificador principal) |
| `created_at` | DATETIME | `datetime('now')` | Fecha de registro |
| `tokens_used` | INTEGER | 0 | Tokens consumidos acumulados |
| `token_limit` | INTEGER | 50000 | Límite de tokens |
| `role` | TEXT | `'user'` | Rol: `user`, `admin`, `superadmin` |

### Tabla: `interactions`
| Columna | Tipo | Default | Descripción |
|---------|------|---------|-------------|
| `id` | INTEGER PK | AUTOINCREMENT | ID único |
| `timestamp` | DATETIME | `datetime('now')` | Momento de la interacción |
| `session_id` | TEXT | — | ID de sesión |
| `topic` | TEXT | — | Materia: `algebra` o `calculo` |
| `user_message_length` | INTEGER | — | Largo del mensaje del usuario |
| `bot_response_length` | INTEGER | — | Largo de la respuesta |
| `response_time_ms` | INTEGER | — | Tiempo de respuesta en ms |
| `user_email` | TEXT | — | Email del usuario (opcional) |
| `rag_confidence` | TEXT | — | Confianza RAG: `high`, `medium`, `low`, `none` |

### Tabla: `chat_history`
| Columna | Tipo | Default | Descripción |
|---------|------|---------|-------------|
| `id` | INTEGER PK | AUTOINCREMENT | ID único |
| `user_email` | TEXT | — | Email del usuario |
| `session_id` | TEXT | — | ID de sesión |
| `role` | TEXT NOT NULL | — | `user` o `assistant` |
| `content` | TEXT NOT NULL | — | Contenido del mensaje |
| `created_at` | DATETIME | `datetime('now')` | Timestamp |

### Tabla: `feedback`
| Columna | Tipo | Default | Descripción |
|---------|------|---------|-------------|
| `id` | INTEGER PK | AUTOINCREMENT | ID único |
| `user_email` | TEXT | — | Email del usuario |
| `rating` | INTEGER NOT NULL | — | Calificación 1-5 |
| `message` | TEXT | — | Comentario opcional |
| `created_at` | DATETIME | `datetime('now')` | Timestamp |

### Tabla: `rate_limits`
| Columna | Tipo | Default | Descripción |
|---------|------|---------|-------------|
| `id` | INTEGER PK | AUTOINCREMENT | ID único |
| `identifier` | TEXT UNIQUE | — | Email, fingerprint o IP |
| `message_count` | INTEGER | 0 | Mensajes enviados en ventana |
| `window_start` | DATETIME | — | Inicio de la ventana de 24h |
| `created_at` | DATETIME | `datetime('now')` | Timestamp |
| `bonus_messages` | INTEGER | 0 | Mensajes extra por pago |

### Tabla: `error_reports`
| Columna | Tipo | Default | Descripción |
|---------|------|---------|-------------|
| `id` | INTEGER PK | AUTOINCREMENT | ID único |
| `user_email` | TEXT | — | Email del reportante |
| `description` | TEXT | — | Descripción del error |
| `page` | TEXT | — | Página: `chat`, `admin`, `grapher` |
| `created_at` | DATETIME | `datetime('now')` | Timestamp |
| `status` | TEXT | `'pending'` | Estado: `pending`, `resolved` |

### Relaciones
- `chat_history.user_email` → `users.email`
- `feedback.user_email` → `users.email`
- `interactions.user_email` → `users.email`
- `rate_limits.identifier` puede ser `users.email`, fingerprint o IP
- No hay foreign keys explícitas (relaciones implícitas)

---

## 5. ENDPOINTS

### Públicos (sin auth)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/` | Health check: `{"message": "AlgorIA API is running"}` |
| GET | `/health` | Health check: `{"status": "ok"}` |
| POST | `/auth` | Login/registro por email. Body: `{email, name?}` |
| POST | `/chat` | Enviar mensaje al chatbot. Body: `{message, materia, session_id, user_email?, device_fp?}`. Rate limited: 15/24h |
| POST | `/reset` | Limpiar historial de sesión. Body: `{session_id}` |
| GET | `/sessions/{session_id}` | Obtener historial completo de una sesión |
| GET | `/rate-limit?identifier=X` | Consultar estado de rate limit |
| POST | `/feedback` | Enviar calificación. Body: `{user_email, rating, message?}` |
| POST | `/report-error` | Reportar bug. Body: `{description, page, user_email?}` |
| POST | `/debug/fill-rate-limit` | DEBUG: llenar rate limit artificialmente |

### Autenticados por header (X-User-Email)

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/history/{email}` | Listar todas las sesiones de un usuario |
| GET | `/history/{email}/{session_id}` | Obtener mensajes de una sesión específica |

### Admin (requiere email con rol admin + PIN)

| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/admin/verify` | email + pin | Verificar credenciales admin |
| GET | `/admin/check-access` | header X-Admin-Email + X-Admin-Pin | Chequear acceso admin |
| GET | `/admin/stats` | admin | Estadísticas generales del dashboard |
| GET | `/admin/interactions` | admin | Últimas 50 interacciones |
| GET | `/admin/users` | admin | Lista de todos los usuarios |
| POST | `/admin/set-role` | superadmin | Cambiar rol de usuario. Body: `{target_email, role}` |
| GET | `/admin/feedback` | admin | Estadísticas y lista de feedback |
| GET | `/admin/reports` | admin | Lista de reportes de errores |
| POST | `/admin/reports/{id}/resolve` | admin | Marcar reporte como resuelto |

### Pagos (Mercado Pago)

| Método | Ruta | Descripción |
|--------|------|-------------|
| POST | `/payment/create-link` | Crear link de pago. Body: `{email, plan}`. Planes: basico($15), estudiante($60), intensivo($200), apoyo(60 msgs) |
| POST | `/payment/webhook` | Webhook de Mercado Pago (auto-grant bonus messages) |
| GET | `/payment/status?email=X` | Consultar bonus messages del usuario |

---

## 6. FEATURES IMPLEMENTADAS

### Chat educativo
- Chatbot dual: Álgebra (con RAG) y Cálculo (sin RAG)
- Historial de conversación por sesión (in-memory + SQLite)
- System prompts pedagógicos que guían sin dar respuestas directas
- Renderizado de notación matemática LaTeX con KaTeX
- Soporte para bloques de código con syntax highlighting

### RAG (Retrieval Augmented Generation)
- 70+ chunks semánticos extraídos de 14 clases DOCX
- Scoring BM25 con keywords y coincidencia de términos
- Niveles de confianza: high (>5), medium (≥3), low (<3)
- Top-2 chunks inyectados como contexto en el prompt

### Sistema de usuarios
- Registro/login por email (auto-create)
- Roles: `user`, `admin`, `superadmin`
- Tracking de tokens consumidos por usuario
- Historial de chat persistente por email

### Rate limiting y cuotas
- 15 mensajes por ventana de 24 horas
- Identificación por email > device fingerprint > IP
- Cuota de tokens (default 50,000 por usuario)
- Mensajes bonus por compras

### Pagos con Mercado Pago
- 4 planes: Básico ($15), Estudiante ($60), Intensivo ($200), Apoyo (60 consultas)
- Generación de links de checkout
- Webhook automático para otorgar bonus messages
- Consulta de estado de bonus por usuario

### Panel de administración
- Autenticación con PIN + verificación de rol
- Estadísticas: interacciones totales, sesiones únicas, largo promedio de respuesta
- Gráfico de interacciones diarias (últimos 30 días)
- Distribución de temas y confianza RAG
- Gestión de usuarios con barras de uso de tokens
- Analytics de feedback con distribución de estrellas
- Visor de reportes de errores con resolución
- Log de interacciones recientes

### Graficador de funciones
- Evaluación de expresiones matemáticas con math.js
- Renderizado en canvas HTML5
- Gestión de múltiples expresiones simultáneas
- Controles de zoom y pan

### UI/UX
- Tema dark con glassmorphism y acentos cyan/azul
- Diseño responsive (mobile + desktop)
- Sidebar colapsable con historial de chats
- Sugerencias de prompts rápidos en pantalla de bienvenida
- Indicador de rate limit con countdown
- Banner de donaciones con links de pago
- Notificaciones toast
- Indicador de "pensando" con animación
- Badge de usuario con estado online

---

## 7. VARIABLES DE ENTORNO

### Requeridas
| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Clave API de Anthropic para Claude | `sk-ant-api03-...` |
| `ADMIN_PIN` | PIN para acceso al panel de administración | `123456` |

### Opcionales
| Variable | Descripción | Default |
|----------|-------------|---------|
| `PORT` | Puerto del servidor | `8000` |
| `ENVIRONMENT` | Entorno de ejecución | `development` |
| `MP_ACCESS_TOKEN` | Token de Mercado Pago para pagos | (vacío, pagos deshabilitados) |
| `DB_PATH` | Ruta al archivo SQLite | `./analytics.db` |

### Superadmins hardcodeados
Los siguientes emails se crean automáticamente como `superadmin` al iniciar:
- `perrottangelo340@gmail.com`
- `angelovalentin.perrotta@alumnos.uai.edu.ar`

---

## 8. ESTADO ACTUAL

### Funciona correctamente
- Core del chat con Álgebra (RAG + Claude API)
- Core del chat con Cálculo (Claude API, sin RAG)
- Registro y login de usuarios
- Rate limiting con ventana de 24h
- Historial de chat persistente en SQLite
- Panel de admin con estadísticas y gráficos
- Feedback y reportes de errores
- Graficador de funciones
- Deploy scripts para Hostinger VPS
- Dockerfile y docker-compose

### Bugs conocidos / Problemas de configuración
- **`.env.example` contiene una API key real** — riesgo de seguridad, debe rotarse
- **`.env` tiene `OPENROUTER_API_KEY` en vez de `ANTHROPIC_API_KEY`** — el chat no funciona sin corregirlo
- **`ADMIN_PIN` no definido en `.env`** — panel admin devuelve 403
- **CORS wildcard `*.netlify.app`** — cualquier app de Netlify puede hacer requests

### Parcialmente implementado
- **Sesiones in-memory**: funcionan pero se pierden al reiniciar el servidor
- **Agente de Cálculo**: funciona pero no logea interacciones ni usa RAG
- **`knowledge_loader.py`**: existe pero no se usa en ningún lado
- **Directorios `data/pdfs/` y `data/ejercicios/`**: vacíos, sin contenido cargado
- **Migración a Groq**: documentada en MIGRATION_NOTES.md pero no implementada

---

## 9. DEUDA TÉCNICA

### Crítica
1. **API key expuesta en `.env.example`** — rotar inmediatamente y reemplazar con placeholder
2. **Sesiones no persistentes** — se pierden en cada redeploy; migrar a SQLite o Redis
3. **Agente de Cálculo sin logging** — interacciones de cálculo invisibles en analytics

### Alta
4. **Sin foreign keys en SQLite** — relaciones implícitas por email, sin integridad referencial
5. **CORS wildcard en Netlify** — restringir a dominios específicos
6. **Backend URL hardcodeada en frontend** — no configurable sin editar HTML
7. **Dockerfile usa shell form para CMD** — SIGTERM no se propaga correctamente al proceso

### Media
8. **RAG trunca a 800 chars arbitrariamente** — puede cortar contenido a mitad de oración
9. **`docker-compose.yml` version 3.11** — no existe, máximo válido es 3.9
10. **Sin tests** — no hay tests unitarios ni de integración
11. **Sin CI/CD** — no hay pipeline de GitHub Actions
12. **`knowledge_loader.py` sin uso** — código muerto
13. **Sin validación de webhook signature** — Mercado Pago webhooks no verifican autenticidad

### Baja
14. **Inline CSS/JS en HTMLs** — todo el frontend en archivos monolíticos de 500-900+ líneas
15. **Sin minificación** — assets sirven sin optimizar
16. **Sin rate limit en endpoints admin** — posible brute force del PIN

---

## 10. PRÓXIMOS PASOS PENDIENTES

### Prioridad alta (pre-deploy)
1. **Corregir `.env`**: agregar `ANTHROPIC_API_KEY` y `ADMIN_PIN` correctos
2. **Limpiar `.env.example`**: reemplazar API key real con placeholder
3. **Rotar la API key expuesta** en el historial de Git

### Prioridad alta (post-deploy)
4. **Persistir sesiones**: migrar `session_manager.py` de dict in-memory a SQLite
5. **Agregar logging al agente de Cálculo**: llamar `log_interaction()` como hace Álgebra
6. **Crear knowledge base de Cálculo**: generar `calculo_chunks.json` e integrar RAG

### Prioridad media
7. **Agregar tests**: unitarios para agentes, RAG, analytics; integración para endpoints
8. **Configurar CI/CD**: GitHub Actions con lint, test, build Docker
9. **Separar frontend**: extraer CSS/JS inline a archivos separados
10. **Validar webhooks**: verificar firma de Mercado Pago en `/payment/webhook`
11. **Restringir CORS**: quitar wildcard de Netlify, listar dominios específicos

### Prioridad baja
12. **Migración a Groq** (documentada pero no decidida): evaluar costo vs calidad
13. **Agregar contenido a `data/`**: cargar PDFs y ejercicios
14. **Integrar `knowledge_loader.py`** o eliminarlo
15. **Monitoreo**: agregar health checks más detallados, métricas de latencia
16. **Optimizar RAG**: truncamiento inteligente por párrafos, expandir a más de 2 chunks
