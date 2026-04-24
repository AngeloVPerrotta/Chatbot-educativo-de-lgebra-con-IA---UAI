import os
import logging
import traceback
from pathlib import Path
from openai import OpenAI

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

        api_key = os.getenv('OPENROUTER_API_KEY')
        logger.info(f'API Key presente: {"Si" if api_key else "No"}')
        logger.info(f'API Key primeros 10 chars: {api_key[:10] if api_key else "None"}')

        logger.info('Creando cliente OpenRouter...')
        client = OpenAI(
            base_url='https://openrouter.ai/api/v1',
            api_key=api_key
        )
        logger.info('Cliente OpenRouter creado exitosamente')

        system_prompt = load_system_prompt()
        logger.info(f'System prompt cargado: {len(system_prompt)} caracteres')

        messages = [{'role': 'system', 'content': system_prompt}] + historial
        logger.info(f'Total mensajes: {len(messages)}')

        logger.info('Llamando a OpenRouter API...')
        response = client.chat.completions.create(
            model='meta-llama/llama-3.3-70b-instruct:free',
            messages=messages,
            max_tokens=1024
        )
        logger.info('Respuesta recibida de OpenRouter')

        result = response.choices[0].message.content
        logger.info(f'Respuesta length: {len(result)} caracteres')
        logger.info('=== FIN CHAT ALGEBRA ===')

        return result

    except Exception as e:
        logger.error(f'ERROR EN CHAT: {type(e).__name__}')
        logger.error(f'Mensaje de error: {str(e)}')
        logger.error('Traceback completo:')
        logger.error(traceback.format_exc())
        raise RuntimeError(f'Error al comunicarse con OpenRouter API: {str(e)}')
