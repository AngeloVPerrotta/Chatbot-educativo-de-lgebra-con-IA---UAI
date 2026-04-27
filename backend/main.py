from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os
import logging
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from agents.algebra_agent import chat as algebra_chat
from agents.calculo_agent import chat as calculo_chat
from utils.session_manager import get_session, append_message, get_messages, clear_session
from utils.analytics import get_stats, get_recent_interactions

load_dotenv(override=False)
logger.info(f'ANTHROPIC_API_KEY presente en env: {"Si" if os.getenv("ANTHROPIC_API_KEY") else "No"}')
logger.info(f'OPENROUTER_API_KEY presente en env: {"Si" if os.getenv("OPENROUTER_API_KEY") else "No"}')

app = FastAPI(title="AlgorIA API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'https://blanchedalmond-buffalo-707381.hostingersite.com',
        'https://chatbot-educativo-de-lgebra-con-ia-uai-production.up.railway.app',
        'https://*.netlify.app',  # Permite cualquier dominio de Netlify
        'http://localhost:5500',  # Para desarrollo local
        'http://127.0.0.1:5500'
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Modelos de validación ---

class ChatRequest(BaseModel):
    message: str
    materia: str = "algebra"  # valor por defecto
    session_id: str

class ChatResponse(BaseModel):
    response: str
    session_id: str


# --- Endpoints base ---

@app.get("/")
def read_root():
    return {"message": "AlgorIA API is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


# --- POST /chat ---
# Recibe el mensaje del usuario, selecciona el agente según la materia,
# mantiene el historial de la sesión y retorna la respuesta del modelo.

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    try:
        logger.info(f'=== ENDPOINT /chat ===')
        logger.info(f'Materia: {request.materia}')
        logger.info(f'Session: {request.session_id}')

        # Agregar el mensaje del usuario al historial de la sesión
        append_message(request.session_id, "user", request.message)

        # Obtener el historial completo para enviarlo al agente
        historial = get_messages(request.session_id)

        logger.info(f'Historial: {len(historial)} mensajes')

        # Seleccionar el agente según la materia indicada
        materia = request.materia.lower()
        if materia == "algebra":
            logger.info('Llamando a algebra_chat...')
            respuesta = algebra_chat(historial, session_id=request.session_id)
        elif materia == "calculo":
            logger.info('Llamando a calculo_chat...')
            respuesta = calculo_chat(historial, session_id=request.session_id)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Materia '{request.materia}' no reconocida. Opciones válidas: 'algebra', 'calculo'."
            )

        logger.info(f'Respuesta recibida: {len(respuesta)} chars')

        # Guardar la respuesta del asistente en el historial
        append_message(request.session_id, "assistant", respuesta)

        return ChatResponse(response=respuesta, session_id=request.session_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'ERROR EN ENDPOINT: {type(e).__name__}')
        logger.error(f'Mensaje: {str(e)}')
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error interno del servidor: {str(e)}")


# --- POST /reset ---
# Limpia el historial de conversación de una sesión específica.

@app.post("/reset")
def reset_session(payload: dict):
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=422, detail="Se requiere 'session_id'.")

    clear_session(session_id)
    return {"message": "Sesión reiniciada"}


# --- Admin helpers ---

def _require_admin(request: Request):
    admin_key = os.getenv("ADMIN_KEY", "")
    if not admin_key or request.headers.get("X-Admin-Key") != admin_key:
        raise HTTPException(status_code=403, detail="Forbidden")


# --- GET /admin/stats ---

@app.get("/admin/stats")
def admin_stats(request: Request):
    _require_admin(request)
    return get_stats()


# --- GET /admin/interactions ---

@app.get("/admin/interactions")
def admin_interactions(request: Request):
    _require_admin(request)
    return get_recent_interactions()


# --- GET /sessions/{session_id} ---
# Retorna el historial completo de mensajes de una sesión.

@app.get("/sessions/{session_id}")
def get_session_history(session_id: str):
    try:
        historial = get_messages(session_id)
        return {"session_id": session_id, "messages": historial}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener la sesión: {str(e)}")
