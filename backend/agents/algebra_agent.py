import os
import time
import logging
import traceback
from pathlib import Path
from utils.rag import retrieve_context
from utils.analytics import log_interaction
from utils.llm_router import call_llm

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

        system_prompt = load_system_prompt()
        logger.info(f'System prompt cargado: {len(system_prompt)} caracteres')

        user_messages = [m for m in historial if m.get("role") == "user"]
        rag_confidence = None
        if user_messages:
            last_user_message = user_messages[-1].get("content", "")
            context, rag_score = retrieve_context(last_user_message)
            if context:
                if rag_score > 5:
                    rag_confidence = "high"
                elif rag_score >= 3:
                    rag_confidence = "medium"
                else:
                    rag_confidence = "low"
                logger.info(f'RAG confidence: {rag_confidence} (score={rag_score})')
                system_prompt = system_prompt + "\n\nCONTEXTO RELEVANTE DE LA CÁTEDRA:\n" + context
                logger.info(f'Contexto RAG agregado: {len(context)} caracteres')
            else:
                logger.info('RAG: no context found')

        if len(historial) > 6:
            historial = historial[-6:]
        logger.info(f'Total mensajes (truncado): {len(historial)}')

        total_input = len(system_prompt) + sum(len(m.get('content','')) for m in historial)
        logger.info(f'TOTAL INPUT ESTIMADO: {total_input} caracteres (~{total_input//4} tokens)')

        logger.info('Llamando a LLM API...')
        t_start = time.time()

        result = call_llm(historial, system_prompt)

        response_time_ms = int((time.time() - t_start) * 1000)
        logger.info(f'Respuesta recibida')
        logger.info(f'Respuesta length: {len(result)} caracteres')

        user_msg_len = len(user_messages[-1].get("content", "")) if user_messages else 0
        try:
            log_interaction(
                session_id=session_id or "",
                topic="algebra",
                user_msg_len=user_msg_len,
                bot_resp_len=len(result),
                response_time_ms=response_time_ms,
                rag_confidence=rag_confidence,
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
        raise RuntimeError(f'Error al comunicarse con LLM API: {str(e)}')
