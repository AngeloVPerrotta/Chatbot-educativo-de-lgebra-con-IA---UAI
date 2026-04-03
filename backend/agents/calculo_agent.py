import anthropic
import os
from pathlib import Path


def load_system_prompt() -> str:
    prompt_path = Path(__file__).parent.parent / "prompts" / "calculo_system_prompt.txt"
    return prompt_path.read_text(encoding="utf-8")


def chat(messages: list[dict], session_id: str = None) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=load_system_prompt(),
        messages=messages,
    )

    return response.content[0].text
