import os
import time
import logging
import traceback
from pathlib import Path
from anthropic import Anthropic

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_system_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "calculo_system_prompt.txt"
    return prompt_path.read_text(encoding="utf-8")


def chat(historial: list, session_id: str = None) -> str:
    try:
        logger.info('=== INICIO CHAT CALCULO ===')
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

        logger.info(f'Total mensajes: {len(historial)}')

        logger.info('Llamando a Anthropic API...')
        t_start = time.time()
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=1024,
            system=system_prompt,
            messages=historial
        )
        response_time_ms = int((time.time() - t_start) * 1000)
        logger.info('Respuesta recibida de Anthropic')

        result = response.content[0].text
        logger.info(f'Respuesta length: {len(result)} caracteres')
        logger.info('=== FIN CHAT CALCULO ===')

        return result

    except Exception as e:
        logger.error(f'ERROR EN CHAT: {type(e).__name__}')
        logger.error(f'Mensaje de error: {str(e)}')
        logger.error('Traceback completo:')
        logger.error(traceback.format_exc())
        raise RuntimeError(f'Error al comunicarse con Anthropic API: {str(e)}')
