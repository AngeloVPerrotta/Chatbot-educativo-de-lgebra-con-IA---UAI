from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os

from agents.algebra_agent import chat as algebra_chat
from agents.calculo_agent import chat as calculo_chat
from utils.session_manager import get_session, append_message, get_messages, clear_session

load_dotenv()

app = FastAPI(title="AlgorIA API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
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
        # Agregar el mensaje del usuario al historial de la sesión
        append_message(request.session_id, "user", request.message)

        # Obtener el historial completo para enviarlo al agente
        historial = get_messages(request.session_id)

        # Seleccionar el agente según la materia indicada
        materia = request.materia.lower()
        if materia == "algebra":
            respuesta = algebra_chat(historial, session_id=request.session_id)
        elif materia == "calculo":
            respuesta = calculo_chat(historial, session_id=request.session_id)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Materia '{request.materia}' no reconocida. Opciones válidas: 'algebra', 'calculo'."
            )

        # Guardar la respuesta del asistente en el historial
        append_message(request.session_id, "assistant", respuesta)

        return ChatResponse(response=respuesta, session_id=request.session_id)

    except HTTPException:
        raise
    except Exception as e:
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


# --- GET /sessions/{session_id} ---
# Retorna el historial completo de mensajes de una sesión.

@app.get("/sessions/{session_id}")
def get_session_history(session_id: str):
    try:
        historial = get_messages(session_id)
        return {"session_id": session_id, "messages": historial}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener la sesión: {str(e)}")
