import os
import time
import logging
import traceback
from pathlib import Path

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LLM_PROVIDER = os.getenv('LLM_PROVIDER', 'groq')  # 'groq' o 'anthropic'
logger.info(f'Proveedor LLM: {LLM_PROVIDER}')


def load_system_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "calculo_system_prompt.txt"
    return prompt_path.read_text(encoding="utf-8")


def chat(historial: list, session_id: str = None) -> str:
    try:
        logger.info('=== INICIO CHAT CALCULO ===')
        logger.info(f'Session ID: {session_id}')
        logger.info(f'Historial length: {len(historial)}')
        logger.info(f'Proveedor LLM: {LLM_PROVIDER}')

        system_prompt = load_system_prompt()
        logger.info(f'System prompt cargado: {len(system_prompt)} caracteres')

        if len(historial) > 6:
            historial = historial[-6:]
        logger.info(f'Total mensajes (truncado): {len(historial)}')

        logger.info('Llamando a LLM API...')
        t_start = time.time()

        if LLM_PROVIDER == 'groq':
            from groq import Groq
            client = Groq(api_key=os.getenv('GROQ_API_KEY'))
            response = client.chat.completions.create(
                model='llama-3.3-70b-versatile',
                messages=[{"role": "system", "content": system_prompt}] + historial,
                max_tokens=700,
                temperature=0.7
            )
            result = response.choices[0].message.content
        else:
            from anthropic import Anthropic
            client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
            response = client.messages.create(
                model='claude-haiku-4-5-20251001',
                max_tokens=700,
                system=system_prompt,
                messages=historial
            )
            result = response.content[0].text

        response_time_ms = int((time.time() - t_start) * 1000)
        logger.info(f'Respuesta recibida de {LLM_PROVIDER}')
        logger.info(f'Respuesta length: {len(result)} caracteres')
        logger.info('=== FIN CHAT CALCULO ===')

        return result

    except Exception as e:
        logger.error(f'ERROR EN CHAT: {type(e).__name__}')
        logger.error(f'Mensaje de error: {str(e)}')
        logger.error('Traceback completo:')
        logger.error(traceback.format_exc())
        raise RuntimeError(f'Error al comunicarse con {LLM_PROVIDER} API: {str(e)}')
