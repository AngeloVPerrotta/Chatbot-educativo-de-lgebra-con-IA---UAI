import os
import time
import logging
import traceback
from pathlib import Path
from google import genai
from utils.rag import retrieve_context
from utils.analytics import log_interaction

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_system_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "algebra_system_prompt.txt"
    return prompt_path.read_text(encoding="utf-8")


def chat(historial: list, session_id: str = None) -> str:
    try:
        logger.info('=== INICIO CHAT ALGEBRA ===')
        logger.info(f'Session ID: {session_id}')
        logger.info(f'Historial length: {len(historial)}')

        api_key = os.getenv('GEMINI_API_KEY')
        logger.info(f'API Key presente: {"Si" if api_key else "No"}')
        logger.info(f'API Key primeros 10 chars: {api_key[:10] if api_key else "None"}')

        logger.info('Creando cliente Gemini...')
        client = genai.Client(api_key=api_key)
        logger.info('Cliente Gemini creado exitosamente')

        system_prompt = load_system_prompt()
        logger.info(f'System prompt cargado: {len(system_prompt)} caracteres')

        user_messages = [m for m in historial if m.get("role") == "user"]
        if user_messages:
            last_user_message = user_messages[-1].get("content", "")
            context = retrieve_context(last_user_message)
            if context:
                system_prompt = system_prompt + "\n\nCONTEXTO RELEVANTE DE LA CÁTEDRA:\n" + context
                logger.info(f'Contexto RAG agregado: {len(context)} caracteres')

        # Convertir historial al formato Gemini (assistant -> model)
        contents = [
            {"role": "model" if m["role"] == "assistant" else m["role"], "parts": [{"text": m["content"]}]}
            for m in historial
        ]

        logger.info(f'Total mensajes: {len(contents)}')

        logger.info('Llamando a Gemini API...')
        t_start = time.time()
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=contents,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                max_output_tokens=1024,
            )
        )
        response_time_ms = int((time.time() - t_start) * 1000)
        logger.info('Respuesta recibida de Gemini')

        result = response.text
        logger.info(f'Respuesta length: {len(result)} caracteres')

        user_msg_len = len(user_messages[-1].get("content", "")) if user_messages else 0
        try:
            log_interaction(
                session_id=session_id or "",
                topic="algebra",
                user_msg_len=user_msg_len,
                bot_resp_len=len(result),
                response_time_ms=response_time_ms,
            )
        except Exception:
            pass  # No interrumpir el flujo si falla el analytics

        logger.info('=== FIN CHAT ALGEBRA ===')

        return result

    except Exception as e:
        logger.error(f'ERROR EN CHAT: {type(e).__name__}')
        logger.error(f'Mensaje de error: {str(e)}')
        logger.error('Traceback completo:')
        logger.error(traceback.format_exc())
        raise RuntimeError(f'Error al comunicarse con Gemini API: {str(e)}')
