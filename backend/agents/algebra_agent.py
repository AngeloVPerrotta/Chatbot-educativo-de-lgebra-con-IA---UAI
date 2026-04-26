import os
import logging
import traceback
from pathlib import Path
from anthropic import Anthropic
from utils.rag import retrieve_context

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

        api_key = os.getenv('ANTHROPIC_API_KEY')
        logger.info(f'API Key presente: {"Si" if api_key else "No"}')
        logger.info(f'API Key primeros 10 chars: {api_key[:10] if api_key else "None"}')

        logger.info('Creando cliente Anthropic...')
        client = Anthropic(api_key=api_key)
        logger.info('Cliente Anthropic creado exitosamente')

        system_prompt = load_system_prompt()
        logger.info(f'System prompt cargado: {len(system_prompt)} caracteres')

        user_messages = [m for m in historial if m.get("role") == "user"]
        if user_messages:
            last_user_message = user_messages[-1].get("content", "")
            context = retrieve_context(last_user_message)
            if context:
                system_prompt = system_prompt + "\n\nCONTEXTO RELEVANTE DE LA CÁTEDRA:\n" + context
                logger.info(f'Contexto RAG agregado: {len(context)} caracteres')

        logger.info(f'Total mensajes: {len(historial)}')

        logger.info('Llamando a Anthropic API...')
        response = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=1024,
            system=system_prompt,
            messages=historial
        )
        logger.info('Respuesta recibida de Anthropic')

        result = response.content[0].text
        logger.info(f'Respuesta length: {len(result)} caracteres')
        logger.info('=== FIN CHAT ALGEBRA ===')

        return result

    except Exception as e:
        logger.error(f'ERROR EN CHAT: {type(e).__name__}')
        logger.error(f'Mensaje de error: {str(e)}')
        logger.error('Traceback completo:')
        logger.error(traceback.format_exc())
        raise RuntimeError(f'Error al comunicarse con Anthropic API: {str(e)}')
