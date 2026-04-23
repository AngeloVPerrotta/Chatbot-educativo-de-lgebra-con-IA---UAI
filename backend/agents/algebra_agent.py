from groq import Groq
import os
from pathlib import Path


def load_system_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "algebra_system_prompt.txt"
    return prompt_path.read_text(encoding="utf-8")


def chat(historial: list, session_id: str = None) -> str:
    client = Groq(api_key=os.getenv('GROQ_API_KEY'))
    system_prompt = load_system_prompt()

    # Groq usa el mismo formato de mensajes que Anthropic
    messages = [{'role': 'system', 'content': system_prompt}] + historial

    try:
        response = client.chat.completions.create(
            model='llama-3.3-70b-versatile',
            messages=messages,
            max_tokens=1024,
            temperature=0.7
        )
        return response.choices[0].message.content

    except Exception as e:
        raise RuntimeError(f'Error al comunicarse con Groq API: {str(e)}')
