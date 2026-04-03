import anthropic
import os
from pathlib import Path


def load_system_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "algebra_system_prompt.txt"
    return prompt_path.read_text(encoding="utf-8")


def chat(historial: list, session_id: str = None) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    system_prompt = load_system_prompt()

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=historial,
        )
        return response.content[0].text

    except anthropic.AuthenticationError:
        raise RuntimeError("API key de Anthropic inválida o no configurada.")
    except anthropic.RateLimitError:
        raise RuntimeError("Límite de solicitudes alcanzado. Intenta nuevamente en unos segundos.")
    except anthropic.APIError as e:
        raise RuntimeError(f"Error al comunicarse con la API de Anthropic: {str(e)}")
